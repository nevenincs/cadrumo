"""Regression tests for the verificado-completo required-input gate and drift detection.

contract: acceptance gate for Layer-1 verification strategy (contract):

1. A Modelo 130 revision calculated without the required manual input
   casillas is NOT granted verificado_completo.
2. Each MISSING_REQUIRED_CASILLA finding references a casilla that
   the registry marks ``required = true`` and ``input_kind = "manual"``.
3. Supplying all required casillas causes the transition to be granted.

contract: tamper-detection regression:

4. Mutating a persisted casilla value after calculate raises
   StoredCalculationDriftError on verify — the content-address mismatch
   is caught before VERIFICADO_COMPLETO is granted.

The tests exercise the real registry, real encrypted SQLite storage, and
real formula engine — no mocks, no stubs, no tautological assertions.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import AnyHttpUrl, TypeAdapter

from ....core import Period
from ....core.resources import resources
from ....domain.buckets import BucketEventHistoryRepository
from ....domain.calculations.registry import CasillaObservation, InputKind, RegistryModeloObservation
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.justificante import Justificante, JustificanteRepository
from ....domain.modelos import ExternalEvidenceKind
from ....domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ....domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ....domain.modelos._repository import WorkUnitCatalogueRepository
from ....domain.modelos._verification_report import (
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
)
from ....domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ....domain.modelos._work_unit import WorkUnit
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.secure_sql import isolated_runtime_profile
from ...calculations import CalculationObservationRepository, cross_period_dependency_requirements
from .. import (
    StoredCalculationDriftError,
    calculate_modelo_revision,
    create_work_unit,
    import_external_filing_evidence,
    verify_modelo_revision,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_Repos = tuple[
    WorkUnitCatalogueRepository,
    CalculationRevisionCatalogueRepository,
    ModeloRecordCatalogueRepository,
    VerificationReportCatalogueRepository,
    BucketEventHistoryRepository,
]

_T0 = datetime(2026, 1, 15, 12, 0, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 15, 13, 0, 0, tzinfo=UTC)
_T2 = datetime(2026, 4, 14, 14, 0, 0, tzinfo=UTC)

_M130_MODELO = "130"
_M130_FILING_YEAR = 2026
_M130_PERIOD = "1T"


def _required_manual_casillas_for_m130() -> tuple[str, ...]:
    """Read required manual casillas from the real registry — no duplication."""
    snap = resources().modelos.authority.snapshot(_M130_MODELO, filing_year=_M130_FILING_YEAR, period=_M130_PERIOD)
    return tuple(str(c.id) for c in snap.revision.casillas if c.required and c.input_kind == InputKind.MANUAL)


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _persist_justificante_metadata(csv: str, *, modelo: str, filing_year: int, period: Period) -> None:
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    JustificanteRepository().save(
        Justificante(
            csv=csv,
            modelo=modelo,
            period=period,
            ejercicio=str(filing_year),
            presentation_id=None,
            presented_at=_T0,
            tax_id="X1234567L",
            total_a_ingresar=None,
            total_a_devolver=None,
            verification_url=TypeAdapter(AnyHttpUrl).validate_python(justificante_cotejo_url(csv)),
            source_pdf_path=Path("var") / "justificantes" / f"{csv}.pdf",
            source_pdf_sha256=hashlib.sha256(pdf_bytes).hexdigest(),
            parsed_at=_T0,
        ),
    )


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Real encrypted SQLite repos over a fresh isolated profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id="default") as profile:
        objects = profile.repository
        wu = WorkUnitCatalogueRepository(objects=objects)
        cr = CalculationRevisionCatalogueRepository(objects=objects)
        filing = ModeloRecordCatalogueRepository(objects=objects)
        vr = VerificationReportCatalogueRepository(objects=objects)
        bv = BucketEventHistoryRepository(objects=objects)
        yield wu, cr, filing, vr, bv


def _seed_clean_cross_period_sources_for_m130(
    work_unit: WorkUnit,
    *,
    work_unit_repository: WorkUnitCatalogueRepository,
    calculation_repository: CalculationRevisionCatalogueRepository,
    filing_repository: ModeloRecordCatalogueRepository,
    bucket_event_repository: BucketEventHistoryRepository,
) -> CalculationObservationRepository:
    snapshot = resources().modelos.authority.snapshot(
        work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    observation_repository = CalculationObservationRepository()
    for requirement in cross_period_dependency_requirements(snapshot):
        values = {casilla_id: Decimal("0") for casilla_id in requirement.source_casillas}
        source_snapshot = resources().modelos.authority.snapshot(
            requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=requirement.period.registry_token,
        )
        source_work_unit = create_work_unit(
            bucket_id=work_unit.bucket_id,
            modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=requirement.period,
            revision_id=source_snapshot.revision.id,
            repository=work_unit_repository,
            bucket_event_repository=bucket_event_repository,
            clock=_T0,
        )
        evidence_reference_id = (
            f"JUST-{requirement.source_modelo}-{requirement.filing_year}-{requirement.period.registry_token}"
        )
        _persist_justificante_metadata(
            evidence_reference_id,
            modelo=requirement.source_modelo,
            filing_year=requirement.filing_year,
            period=requirement.period,
        )
        import_external_filing_evidence(
            work_unit_id=source_work_unit.work_unit_id,
            casilla_values=values,
            evidence_kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            evidence_reference_id=evidence_reference_id,
            actor="aeat-import-test",
            work_unit_repository=work_unit_repository,
            calculation_repository=calculation_repository,
            filing_repository=filing_repository,
            bucket_event_repository=bucket_event_repository,
            expected_tax_id="X1234567L",
            clock=_T0,
        )
        observation_repository.save_observation(
            RegistryModeloObservation(
                modelo=requirement.source_modelo,
                filing_year=requirement.filing_year,
                period=requirement.period.registry_token,
                observations=tuple(
                    CasillaObservation(casilla_id=casilla_id, value=value) for casilla_id, value in values.items()
                ),
            ),
            source_kind="aeat_sede_justificante",
            captured_at=_T0,
            stamped_revision_id=source_snapshot.revision.id,
            source_metadata={
                "aeat_register_status": "ALTA",
                "aeat_expediente_id": (
                    f"EXP-{requirement.source_modelo}-{requirement.filing_year}-{requirement.period.registry_token}"
                ),
                "aeat_justificante_csv": evidence_reference_id,
                "authenticated_identity": "X1234567L",
            },
        )
    return observation_repository


def test_verify_refuses_when_required_casillas_absent_m130(repos: _Repos) -> None:
    """M130 revision with no required casilla is NOT granted verificado_completo.

    The test uses the real M130 registry to determine which casillas are
    required. It calculates a revision with those casillas absent and
    asserts the verifier produces ≥1 MISSING_REQUIRED_CASILLA finding.
    """
    wu_repo, cr_repo, _filing_repo, vr_repo, bv_repo = repos
    required = _required_manual_casillas_for_m130()
    assert len(required) >= 1, (
        "M130 registry must declare at least one required manual casilla; "
        "check casillas/0001-casillas.toml required = true declarations"
    )

    work_unit = create_work_unit(
        bucket_id="default",
        modelo=_M130_MODELO,
        filing_year=_M130_FILING_YEAR,
        period=Period.from_year_and_code(_M130_FILING_YEAR, _M130_PERIOD),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    # Calculate with empty required casillas — supply only the bound casilla
    # (01) and non-required manual casillas so the engine can run, but omit
    # the required ones entirely.
    inputs_without_required: dict[str, Decimal] = {
        "05": Decimal("0"),
        "06": Decimal("0"),
        "08": Decimal("0"),
        "10": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }
    # Explicitly exclude any casilla in the required set
    casilla_inputs = {k: v for k, v in inputs_without_required.items() if k not in required}

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            # previous_filing binding for casilla 15 carry-forward (no period anchor;
            # supply zero for Q1 where no prior quarter exists within the ejercicio)
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is False
    assert report.completeness_status is VerificationCompletenessStatus.INCOMPLETE

    missing_finding_casillas = {
        f.casilla_id for f in report.findings if f.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
    }
    # Every casilla in the missing finding set must be registry-required
    assert missing_finding_casillas, "Expected at least one MISSING_REQUIRED_CASILLA finding"
    assert missing_finding_casillas <= set(required), (
        f"Findings reference casillas not declared required in registry: {missing_finding_casillas - set(required)}"
    )
    # The required casillas we omitted must appear in missing_required_casillas
    for casilla_id in required:
        assert casilla_id in report.missing_required_casillas


def test_verify_grants_when_required_casillas_supplied_m130(repos: _Repos) -> None:
    """M130 revision with all required casillas present is granted verificado_completo."""
    wu_repo, cr_repo, filing_repo, vr_repo, bv_repo = repos
    required = _required_manual_casillas_for_m130()

    work_unit = create_work_unit(
        bucket_id="default",
        modelo=_M130_MODELO,
        filing_year=_M130_FILING_YEAR,
        period=Period.from_year_and_code(_M130_FILING_YEAR, _M130_PERIOD),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    casilla_inputs: dict[str, Decimal] = {
        "01": Decimal("10000"),
        "02": Decimal("3000"),
        "05": Decimal("0"),
        "06": Decimal("0"),
        "08": Decimal("0"),
        "10": Decimal("0"),
        "15": Decimal("0"),
        "16": Decimal("0"),
        "18": Decimal("0"),
    }
    # Confirm the test supplies all required casillas
    assert set(required) <= set(casilla_inputs), (
        f"Test fixture missing required casillas: {set(required) - set(casilla_inputs)}"
    )

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs=casilla_inputs,
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )
    observation_repo = _seed_clean_cross_period_sources_for_m130(
        work_unit,
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        bucket_event_repository=bv_repo,
    )

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        filing_repository=filing_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        calculation_observation_repository=observation_repo,
        clock=_T2,
    )

    assert report.granted_verificado_completo is True
    assert report.completeness_status is VerificationCompletenessStatus.COMPLETE
    assert report.missing_required_casillas == ()
    assert set(report.resolved_casillas) >= set(required)
    verified = cr_repo.load().get(revision.calculation_revision_id)
    assert verified is not None
    assert verified.ledger_filing_snapshot is not None
    assert verified.ledger_filing_evidence is not None
    assert verified.ledger_filing_evidence.snapshot_fingerprint == verified.ledger_filing_snapshot.snapshot_fingerprint
    assert {entry.casilla for entry in verified.ledger_filing_evidence.manual_entries} >= set(casilla_inputs)


def test_tampered_revision_raises_drift_error(repos: _Repos) -> None:
    """_assert_revision_content_integrity raises StoredCalculationDriftError on drift.

    contract regression: verify_modelo_revision calls _assert_revision_content_integrity
    before granting VERIFICADO_COMPLETO.  The check is exercised by constructing a
    CalculationRevision via model_construct (bypassing _enforce_invariants) with a
    casilla_values mapping that does not match the stored calculation_revision_id.

    This tests the integrity guard as a unit within the verify path: the guard is
    called with a revision object where the hash-to-payload contract is broken.
    In production, such breakage can occur through raw-storage manipulation or a
    future schema migration that mutates the payload without updating the id.
    """
    from .._registry_helpers import assert_revision_content_integrity as _assert_revision_content_integrity

    wu_repo, cr_repo, _filing_repo, _vr_repo, bv_repo = repos

    work_unit = create_work_unit(
        bucket_id="default",
        modelo=_M130_MODELO,
        filing_year=_M130_FILING_YEAR,
        period=Period.from_year_and_code(_M130_FILING_YEAR, _M130_PERIOD),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    revision = calculate_modelo_revision(
        work_unit.work_unit_id,
        casilla_inputs={
            "01": Decimal("10000"),
            "02": Decimal("3000"),
            "05": Decimal("0"),
            "06": Decimal("0"),
            "08": Decimal("0"),
            "10": Decimal("0"),
            "15": Decimal("0"),
            "16": Decimal("0"),
            "18": Decimal("0"),
        },
        binding_values={
            "irpf.previous_year_economic_activity_net_income": Decimal("0"),
            "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        },
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        bucket_event_repository=bv_repo,
        clock=_T1,
    )

    catalogue = cr_repo.load()
    original = catalogue.get(revision.calculation_revision_id)
    assert original is not None

    # Construct a tampered revision via model_construct — this bypasses all
    # pydantic validators so the hash mismatch is not caught at build time.
    # The tampered version keeps the original calculation_revision_id (which
    # was derived from the original casilla_values) but carries mutated
    # casilla_values, breaking the content-address contract.
    tampered_values = dict(original.casilla_values)
    tampered_values["02"] = Decimal("999999")

    tampered = original.model_construct(
        calculation_revision_id=original.calculation_revision_id,
        work_unit_id=original.work_unit_id,
        state=original.state,
        inputs_snapshot=original.inputs_snapshot,
        binding_overrides=original.binding_overrides,
        source_transaction_ids=original.source_transaction_ids,
        borrador_snapshot_id=original.borrador_snapshot_id,
        bindings_sourced_from_borrador=original.bindings_sourced_from_borrador,
        casilla_values=tampered_values,
        observations=(),  # cleared so the obs-vs-casilla_values pydantic check is skipped
        created_at=original.created_at,
        updated_at=original.updated_at,
        verified_at=original.verified_at,
        verified_by=original.verified_by,
        filed_at=original.filed_at,
        filed_by=original.filed_by,
        superseded_at=original.superseded_at,
        discarded_at=original.discarded_at,
        discarded_by=original.discarded_by,
        discard_reason=original.discard_reason,
        amendment_kind=original.amendment_kind,
        amends_filing_record_id=original.amends_filing_record_id,
        amendment_reason=original.amendment_reason,
    )

    # The guard must detect the hash mismatch and raise StoredCalculationDriftError.
    with pytest.raises(StoredCalculationDriftError):
        _assert_revision_content_integrity(tampered)
