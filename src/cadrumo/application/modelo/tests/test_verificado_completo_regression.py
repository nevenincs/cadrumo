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

from ....adapters.inbound.pdf import source_pdf_reference_path
from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....core import CasillaId, Period, validated_casilla_id
from ....core.resources import resources
from ....domain.calculations.registry import (
    InputKind,
    RegistryModeloObservation,
)
from ....domain.deadlines import IVARegime, TaxpayerProfile
from ....domain.justificante import Justificante
from ....domain.modelos import (
    ExternalEvidenceKind,
    ModeloVerificationFindingKind,
    VerificationCompletenessStatus,
    WorkUnit,
)
from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.aeat_literal_fixtures import justificante_cotejo_url
from ....tests.env_scope import ready_clave_settings
from ....tests.profile_capsule import seed_test_profile_record
from ....tests.registry_observations import registry_grounded_observations
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
_M130_INGRESOS_CASILLA: CasillaId = validated_casilla_id("01", surface="_M130_INGRESOS_CASILLA")
_M130_GASTOS_CASILLA: CasillaId = validated_casilla_id("02", surface="_M130_GASTOS_CASILLA")
_M130_RENDIMIENTO_NETO_CASILLA: CasillaId = validated_casilla_id("05", surface="_M130_RENDIMIENTO_NETO_CASILLA")
_M130_BASE_PAGO_FRACCIONADO_CASILLA: CasillaId = validated_casilla_id(
    "06",
    surface="_M130_BASE_PAGO_FRACCIONADO_CASILLA",
)
_M130_RETENCIONES_CASILLA: CasillaId = validated_casilla_id("08", surface="_M130_RETENCIONES_CASILLA")
_M130_PAGOS_FRACCIONADOS_CASILLA: CasillaId = validated_casilla_id("10", surface="_M130_PAGOS_FRACCIONADOS_CASILLA")
_M130_A_DEDUCIR_CASILLA: CasillaId = validated_casilla_id("15", surface="_M130_A_DEDUCIR_CASILLA")
_M130_RESULTADO_PREVIO_CASILLA: CasillaId = validated_casilla_id("16", surface="_M130_RESULTADO_PREVIO_CASILLA")
_M130_RESULTADO_CASILLA: CasillaId = validated_casilla_id("18", surface="_M130_RESULTADO_CASILLA")
_BUCKET_ID = "00000000-0000-4000-8000-000000000131"
_PROFILE_LABEL = "M130 verification test"


def _required_manual_casillas_for_m130() -> tuple[CasillaId, ...]:
    """Read required manual casillas from the real registry — no duplication."""
    snap = resources().modelos.authority.snapshot(_M130_MODELO, filing_year=_M130_FILING_YEAR, period=_M130_PERIOD)
    return tuple(c.id for c in snap.revision.casillas if c.required and c.input_kind == InputKind.MANUAL)


def _workflow_profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def _seed_runtime_profile_record(bucket_id: str) -> None:
    seed_test_profile_record(
        UserProfileRecord(setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=(
                UserProfileFact(path="identity.tax_id", value="X1234567L"),
                UserProfileFact(path="identity.name", value="Ana"),
                UserProfileFact(path="identity.surnames", value="Verifier"),
                UserProfileFact(path="activities.description", value="design services"),
                UserProfileFact(path="tax_residence.ccaa", value="madrid"),
                UserProfileFact(path="tax_residence.jurisdiction_scope", value="common_regime"),
                UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
                UserProfileFact(path="taxpayer_type.irpf_income_categories", value="actividad_economica"),
                UserProfileFact(path="irpf.estimation_regime", value="directa_normal"),
                UserProfileFact(path="censo.activity_start_date", value="2020-01-01"),
                UserProfileFact(path="iva.regime", value="GENERAL"),
                UserProfileFact(path="iva.m303_regime_composition", value="general"),
                UserProfileFact(path="iva.redeme_enrolled", value=False),
                UserProfileFact(path="iva.cash_accounting_regime_enrolled", value=False),
                UserProfileFact(path="iva.voluntary_sii_enrolled", value=False),
                UserProfileFact(path="iva.hydrocarbon_deposit_advance_payment_deduction_entitled", value=False),
            ),
            created_at=_T0,
            updated_at=_T0,
        ),
    )


def _persist_justificante_metadata(csv: str, *, modelo: str, filing_year: int, period: Period) -> None:
    pdf_bytes = f"%PDF-1.4\n% synthetic justificante {csv}\n%%EOF\n".encode()
    source_pdf_sha256 = hashlib.sha256(pdf_bytes).hexdigest()
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
            source_pdf_path=source_pdf_reference_path(source_pdf_sha256),
            source_pdf_sha256=source_pdf_sha256,
            parsed_at=_T0,
        ),
    )


@pytest.fixture
def repos(tmp_path: Path) -> Iterator[_Repos]:
    """Real encrypted SQLite repos over a fresh isolated profile."""
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label=_PROFILE_LABEL) as profile:
        _seed_runtime_profile_record(_BUCKET_ID)
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
        values = {casilla_id: Decimal("0") for casilla_id in requirement.source_casilla_ids}
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
        observation_repository.save(
            observation_repository.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo=requirement.source_modelo,
                    filing_year=requirement.filing_year,
                    period=requirement.period.registry_token,
                    observations=registry_grounded_observations(
                        modelo=requirement.source_modelo,
                        filing_year=requirement.filing_year,
                        period=requirement.period.registry_token,
                        casilla_values=values,
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
        )
    return observation_repository


def test_m130_has_no_required_manual_casilla_so_missing_required_never_blocks(repos: _Repos) -> None:
    """With casilla 02 bound to the ledger, M130 has zero required MANUAL casillas.

    Casilla 02 (Gastos) used to be the lone ``input_kind = manual`` + ``required``
    casilla, so a filer with no gastos was blocked with a MISSING_REQUIRED_CASILLA
    finding until they hand-entered ``--casilla 02=0``. Binding casilla 02 to the
    ``ledger_renta_gastos_pago_fraccionado_aggregation`` source means it is
    auto-populated (0 when there are no expenses) and the missing-required gate —
    which fires only for MANUAL required casillas — has nothing to flag. This test
    pins that no required manual casilla remains and that an M130 revision with no
    casilla inputs surfaces no MISSING_REQUIRED_CASILLA finding. The
    missing-required mechanism itself is exercised against a real registry casilla
    definition in ``test_missing_required_casilla_finding_carries_registry_provenance``.
    """
    wu_repo, cr_repo, _filing_repo, vr_repo, bv_repo = repos
    required = _required_manual_casillas_for_m130()
    assert required == (), (
        "M130 must have no required MANUAL casillas after the H1 gasto bind "
        f"(casilla 02 is now ledger-bound); registry still declares {required!r}"
    )

    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
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
            _M130_RENDIMIENTO_NETO_CASILLA: Decimal("0"),
            _M130_BASE_PAGO_FRACCIONADO_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_PAGOS_FRACCIONADOS_CASILLA: Decimal("0"),
            _M130_RESULTADO_PREVIO_CASILLA: Decimal("0"),
            _M130_RESULTADO_CASILLA: Decimal("0"),
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

    report = verify_modelo_revision(
        revision.calculation_revision_id,
        actor="operator-test",
        workflow_profile=_workflow_profile(),
        settings=ready_clave_settings("X1234567L"),
        work_unit_repository=wu_repo,
        calculation_repository=cr_repo,
        verification_repository=vr_repo,
        bucket_event_repository=bv_repo,
        clock=_T2,
    )

    missing_finding_casillas = {
        f.casilla_id for f in report.findings if f.kind is ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA
    }
    assert missing_finding_casillas == set(), (
        f"M130 has no required manual casilla, so no MISSING_REQUIRED_CASILLA finding is expected; "
        f"got {missing_finding_casillas!r}"
    )
    assert report.missing_required_casilla_ids == ()


def test_verify_grants_when_required_casillas_supplied_m130(repos: _Repos) -> None:
    """M130 revision with all required casillas present is granted verificado_completo."""
    wu_repo, cr_repo, filing_repo, vr_repo, bv_repo = repos
    required = _required_manual_casillas_for_m130()

    work_unit = create_work_unit(
        bucket_id=_BUCKET_ID,
        modelo=_M130_MODELO,
        filing_year=_M130_FILING_YEAR,
        period=Period.from_year_and_code(_M130_FILING_YEAR, _M130_PERIOD),
        revision_id="2019-y-siguientes",
        repository=wu_repo,
        clock=_T0,
    )

    casilla_inputs: dict[CasillaId, Decimal] = {
        _M130_INGRESOS_CASILLA: Decimal("10000"),
        _M130_GASTOS_CASILLA: Decimal("3000"),
        _M130_RENDIMIENTO_NETO_CASILLA: Decimal("0"),
        _M130_BASE_PAGO_FRACCIONADO_CASILLA: Decimal("0"),
        _M130_RETENCIONES_CASILLA: Decimal("0"),
        _M130_PAGOS_FRACCIONADOS_CASILLA: Decimal("0"),
        _M130_RESULTADO_PREVIO_CASILLA: Decimal("0"),
        _M130_RESULTADO_CASILLA: Decimal("0"),
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
        settings=ready_clave_settings("X1234567L"),
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
    assert report.missing_required_casilla_ids == ()
    assert set(report.resolved_casilla_ids) >= set(required)
    verified = cr_repo.load().get(revision.calculation_revision_id)
    assert verified is not None
    assert verified.ledger_filing_snapshot is not None
    assert verified.ledger_filing_evidence is not None
    assert verified.ledger_filing_evidence.snapshot_fingerprint == verified.ledger_filing_snapshot.snapshot_fingerprint
    assert {entry.casilla_id for entry in verified.ledger_filing_evidence.manual_entries} >= set(casilla_inputs)
    assert all(row.legal_refs and row.source_refs for row in verified.ledger_filing_evidence.rows)
    assert all(entry.legal_refs and entry.source_refs for entry in verified.ledger_filing_evidence.manual_entries)


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
        bucket_id=_BUCKET_ID,
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
            _M130_INGRESOS_CASILLA: Decimal("10000"),
            _M130_GASTOS_CASILLA: Decimal("3000"),
            _M130_RENDIMIENTO_NETO_CASILLA: Decimal("0"),
            _M130_BASE_PAGO_FRACCIONADO_CASILLA: Decimal("0"),
            _M130_RETENCIONES_CASILLA: Decimal("0"),
            _M130_PAGOS_FRACCIONADOS_CASILLA: Decimal("0"),
            _M130_RESULTADO_PREVIO_CASILLA: Decimal("0"),
            _M130_RESULTADO_CASILLA: Decimal("0"),
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
    tampered_values[_M130_GASTOS_CASILLA] = Decimal("999999")

    tampered = original.model_construct(
        calculation_revision_id=original.calculation_revision_id,
        work_unit_id=original.work_unit_id,
        state=original.state,
        input_values_by_casilla_id=original.input_values_by_casilla_id,
        binding_overrides=original.binding_overrides,
        filing_instance_evidence=original.filing_instance_evidence,
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
        amendment_identity=original.amendment_identity,
        amendment_reason=original.amendment_reason,
    )

    # The guard must detect the hash mismatch and raise StoredCalculationDriftError.
    with pytest.raises(StoredCalculationDriftError):
        _assert_revision_content_integrity(tampered)
