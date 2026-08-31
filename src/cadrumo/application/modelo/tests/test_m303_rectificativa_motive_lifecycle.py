"""Real authority and encrypted-persistence proofs for M303 rectificativa motive state."""

from __future__ import annotations

from datetime import UTC, date, datetime
from functools import lru_cache
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.persistence.profile.justificante import JustificanteRepository
from ....adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ....adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ....adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ....application.filing import (
    AmendmentEvidence,
    FilingElectionFacts,
    FilingProducerSnapshotError,
    Modelo111ProfileFacts,
    PresenterIdentity,
    TaxpayerIdentityFacts,
    build_filing_producer_snapshot,
    m303_rectificativa_motive_producer_values,
)
from ....core import FilingProducerKey, PaymentElection, PriorDomiciliationElection, RefundElection
from ....core.result_disposition import ResultDisposition
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.m303_orden_manifest import load_m303_annual_orden_authority
from ....domain.calculations.registry.m303_orden_projection_models import M303RegimenSimplificadoSnapshot
from ....domain.calculations.registry.m303_orden_resolution import m303_annual_orden_snapshot_from_projection
from ....domain.calculations.registry.schema import RegistrySnapshot
from ....domain.deadlines.models import IVARegime, TaxpayerProfile
from ....domain.iva.regimen_simplificado_rows import M303RegimenSimplificadoScope, M303RegimenSimplificadoScopeDecision
from ....domain.justificante import Justificante
from ....domain.modelos.calculation_revision_aggregate import CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY, CalculationRevisionAggregateContext
from ....domain.modelos.calculation_revision_amendment import m303_rectificativa_motive_is_applicable, m303_rectificativa_record_design_from_snapshot
from ....domain.modelos.filing_record import ExternalEvidence, ExternalEvidenceKind, ModeloRecord, ModeloRecordCatalogue, derive_filing_record_id
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ....domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionAmendmentIdentity, CalculationRevisionAmendmentKind, CalculationRevisionCatalogue, CalculationRevisionState, derive_calculation_revision_id
from ....domain.modelos.calculation_revision_amendment import M303RectificativaMotive
from ....tests.aeat_literal_fixtures import SEDE_ROOT_URL_FIXTURE
from ....tests.cli_runner import invoke_cached_cli
from ....tests.filing_evidence import general_m303_filing_evidence_from_regimen_snapshot
from ....tests.secure_sql import isolated_runtime_profile
from .._action_errors import AmendmentM303RectificativaMotiveError
from .._amendment_actions import amend_modelo_revision
from .._export import (
    ModeloExportCommand,
    ModeloExportError,
    export_modelo_revision,
)
from .._export_amendment_evidence import resolve_persisted_amendment_export_evidence

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BUCKET_ID = "0479178a-6678-4c43-8b7d-46fba6483f11"  # was 'm303-rectificativa-motive'
_TAX_ID = "X1234567L"
_CSV = "S92RECTIFICA2025"
_RECEIPT = "1234567890123"
_NOW = datetime(2026, 8, 14, 8, 0, 0, tzinfo=UTC)


@lru_cache(maxsize=1)
def _snapshot() -> RegistrySnapshot:
    return bundled_authority().snapshot(Modelo.M303.value, filing_year=2025, period="1T")


@lru_cache(maxsize=1)
def _filing_evidence():
    authority = bundled_authority()
    snapshot = _snapshot()
    record_design = m303_rectificativa_record_design_from_snapshot(snapshot)
    assert record_design is not None
    compilation = load_m303_annual_orden_authority(
        authority.root,
        source_root=authority.source_root,
        modelos=authority.modelos,
        sources=authority.catalogues.sources,
    )
    projection = compilation.authority.require_projection(
        ejercicio=2025,
        registry_revision_id=snapshot.revision.id,
    )
    scope = M303RegimenSimplificadoScopeDecision(
        scope=M303RegimenSimplificadoScope.REGIMEN_SIMPLIFICADO_NOT_CLAIMED,
    )
    regimen_snapshot = M303RegimenSimplificadoSnapshot(
        filing_year=2025,
        registry_revision_id=snapshot.revision.id,
        scope_decision=scope,
        orden=m303_annual_orden_snapshot_from_projection(projection),
        record_design=record_design,
    )
    return general_m303_filing_evidence_from_regimen_snapshot(
        Period.from_year_and_code(2025, "1T"),
        reference="test:s92:general-scope",
        regimen_snapshot=regimen_snapshot,
    )


def _authorities(*, motive: M303RectificativaMotive = M303RectificativaMotive.RECTIFICACIONES):
    period = Period.from_year_and_code(2025, "1T")
    snapshot = _snapshot()
    work_unit_id = derive_work_unit_id(
        bucket_id=_BUCKET_ID,
        modelo=Modelo.M303.value,
        filing_year=2025,
        period=period,
        revision_id=snapshot.revision.id,
    )
    work_unit = WorkUnit(
        work_unit_id=work_unit_id,
        bucket_id=_BUCKET_ID,
        modelo=Modelo.M303,
        filing_year=2025,
        period=period,
        revision_id=snapshot.revision.id,
        name="M303 S92",
        created_at=_NOW,
        updated_at=_NOW,
    )
    evidence = _filing_evidence()
    baseline_revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=evidence,
        source_provenance=(),
    )
    baseline_revision = CalculationRevision(
        calculation_revision_id=baseline_revision_id,
        work_unit_id=work_unit_id,
        state=CalculationRevisionState.BORRADOR,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=evidence,
        created_at=_NOW,
        updated_at=_NOW,
        source_provenance=(),
    )
    filing_record_id = derive_filing_record_id(
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision_id,
        filed_by="aeat-import",
    )
    target = ModeloRecord(
        filing_record_id=filing_record_id,
        work_unit_id=work_unit_id,
        calculation_revision_id=baseline_revision_id,
        bucket_id=_BUCKET_ID,
        modelo=Modelo.M303,
        filing_year=2025,
        period=period,
        filed_at=_NOW,
        filed_by="aeat-import",
        aeat_accepted=True,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id=_CSV,
            imported_at=_NOW,
        ),
    )
    receipt = Justificante(
        csv=_CSV,
        modelo=Modelo.M303.value,
        ejercicio="2025",
        period=period,
        presentation_id=_RECEIPT,
        presented_at=_NOW,
        tax_id=_TAX_ID,
        verification_url=SEDE_ROOT_URL_FIXTURE,
        source_pdf_path=Path("sha256/s92-justificante.pdf"),
        source_pdf_sha256="a" * 64,
        parsed_at=_NOW,
    )
    work_units = WorkUnitCatalogue.from_work_units((work_unit,))
    filing_records = ModeloRecordCatalogue(records={target.filing_record_id: target})
    context = CalculationRevisionAggregateContext(
        work_units=work_units,
        filing_records=filing_records,
        justificantes=(receipt,),
        registry_snapshots={work_unit_id: snapshot},
        expected_taxpayer_tax_id=_TAX_ID,
    )
    identity = CalculationRevisionAmendmentIdentity(
        kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
        amends_filing_record_id=target.filing_record_id,
        m303_rectificativa_motive=motive,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit_id,
        input_values_by_casilla_id={},
        binding_overrides={},
        casilla_values={},
        filing_instance_evidence=evidence,
        amendment_identity=identity,
        source_provenance=(),
    )
    revision = CalculationRevision.model_validate(
        {
            "calculation_revision_id": revision_id,
            "work_unit_id": work_unit_id,
            "state": CalculationRevisionState.BORRADOR,
            "input_values_by_casilla_id": {},
            "binding_overrides": {},
            "casilla_values": {},
            "source_provenance": (),
            "filing_instance_evidence": evidence,
            "created_at": _NOW,
            "updated_at": _NOW,
            "amendment_identity": identity,
            "amendment_reason": "operator explanation only",
        },
        context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: context},
    )
    return work_unit, baseline_revision, target, receipt, context, revision


def _profile() -> TaxpayerProfile:
    return TaxpayerProfile(
        tax_id=_TAX_ID,
        iva_regime=IVARegime.GENERAL,
        activity_start_date=date(2000, 1, 1),
        has_employees=False,
        pays_rent_with_retencion=False,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )


def test_closed_enum_refuses_free_text_and_every_identity_axis_diverges() -> None:
    _, _, target, _, _, revision = _authorities()
    with pytest.raises(ValidationError):
        CalculationRevisionAmendmentIdentity(
            kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            amends_filing_record_id=target.filing_record_id,
            m303_rectificativa_motive="other",  # type: ignore[arg-type]
        )
    identities = (
        revision.amendment_identity,
        CalculationRevisionAmendmentIdentity(
            kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            amends_filing_record_id=target.filing_record_id,
            m303_rectificativa_motive=M303RectificativaMotive.DISCREPANCIA_CRITERIO_ADMINISTRATIVO,
        ),
        CalculationRevisionAmendmentIdentity(
            kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            amends_filing_record_id=target.filing_record_id,
            m303_rectificativa_motive=None,
        ),
        CalculationRevisionAmendmentIdentity(
            kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            amends_filing_record_id="f" * 64,
            m303_rectificativa_motive=M303RectificativaMotive.RECTIFICACIONES,
        ),
    )
    revision_ids = {
        derive_calculation_revision_id(
            work_unit_id=revision.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=revision.filing_instance_evidence,
            amendment_identity=identity,
            source_provenance=(),
        )
        for identity in identities
    }
    assert len(revision_ids) == 4


def test_context_free_missing_and_cross_context_rectificativa_refuse() -> None:
    _, _, target, _, context, revision = _authorities()
    payload = revision.model_dump(mode="python")
    with pytest.raises(ValidationError, match="context-bound aggregate"):
        CalculationRevision.model_validate(payload)

    amendment_identity = revision.amendment_identity
    assert amendment_identity is not None
    missing_motive = amendment_identity.model_copy(update={"m303_rectificativa_motive": None})
    missing_payload = {
        **payload,
        "amendment_identity": missing_motive,
        "amendment_reason": "rectificaciones",
        "calculation_revision_id": derive_calculation_revision_id(
            work_unit_id=revision.work_unit_id,
            input_values_by_casilla_id={},
            binding_overrides={},
            casilla_values={},
            filing_instance_evidence=revision.filing_instance_evidence,
            amendment_identity=missing_motive,
            source_provenance=(),
        ),
    }
    with pytest.raises(ValidationError, match="requires exactly one persisted motive"):
        CalculationRevision.model_validate(
            missing_payload,
            context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: context},
        )

    wrong_period_target = target.model_copy(update={"period": Period.from_year_and_code(2025, "2T")})
    cross_context = context.model_copy(
        update={"filing_records": ModeloRecordCatalogue(records={target.filing_record_id: wrong_period_target})}
    )
    with pytest.raises(ValidationError, match="crosses its WorkUnit filing coordinate"):
        CalculationRevision.model_validate(
            payload,
            context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: cross_context},
        )


def test_every_persisted_target_and_justificante_join_refusal_is_biting() -> None:
    work_unit, _, target, receipt, context, revision = _authorities()
    payload = revision.model_dump(mode="python")
    empty_records = ModeloRecordCatalogue(records={})
    with pytest.raises(ValidationError, match="external filing evidence must carry AEAT acceptance"):
        ModeloRecord.model_validate({**target.model_dump(mode="python"), "aeat_accepted": False})
    with pytest.raises(ValidationError, match="AEAT-accepted filing record must carry external evidence"):
        ModeloRecord.model_validate({**target.model_dump(mode="python"), "external_evidence": None})
    variants = (
        (
            context.model_copy(update={"work_units": WorkUnitCatalogue.from_work_units(())}),
            "no authoritative parent WorkUnit",
        ),
        (
            context.model_copy(update={"registry_snapshots": {}}),
            "lacks exact registry snapshot context",
        ),
        (
            context.model_copy(update={"filing_records": empty_records}),
            "filing target does not resolve",
        ),
        (context.model_copy(update={"justificantes": ()}), "exactly one justificante"),
        (context.model_copy(update={"justificantes": (receipt, receipt)}), "exactly one justificante"),
        (
            context.model_copy(update={"justificantes": (receipt.model_copy(update={"tax_id": "12345678Z"}),)}),
            "disagrees with the taxpayer or filing coordinate",
        ),
        (
            context.model_copy(update={"justificantes": (receipt.model_copy(update={"modelo": "130"}),)}),
            "disagrees with the taxpayer or filing coordinate",
        ),
        (
            context.model_copy(update={"justificantes": (receipt.model_copy(update={"ejercicio": "2024"}),)}),
            "disagrees with the taxpayer or filing coordinate",
        ),
        (
            context.model_copy(
                update={
                    "justificantes": (receipt.model_copy(update={"period": Period.from_year_and_code(2025, "2T")}),)
                }
            ),
            "disagrees with the taxpayer or filing coordinate",
        ),
        (
            context.model_copy(update={"justificantes": (receipt.model_copy(update={"presentation_id": None}),)}),
            "requires the original AEAT receipt number",
        ),
    )
    assert work_unit.modelo == Modelo.M303.value
    for variant, message in variants:
        with pytest.raises(ValidationError, match=message):
            CalculationRevision.model_validate(
                payload,
                context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: variant},
            )


def test_encrypted_persistence_reloads_and_revalidates_joined_authority(tmp_path: Path) -> None:
    work_unit, baseline_revision, target, receipt, context, revision = _authorities()
    assert work_unit.modelo == Modelo.M303.value
    assert work_unit.modelo is not Modelo.M303
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="S92") as runtime:
        objects = runtime.repository
        work_repo = WorkUnitCatalogueRepository(objects=objects)
        filing_repo = ModeloRecordCatalogueRepository(objects=objects)
        justificante_repo = JustificanteRepository(objects=objects)
        calculation_repo = CalculationRevisionCatalogueRepository(
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=_TAX_ID,
        )
        work_repo.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        filing_repo.save(ModeloRecordCatalogue(records={target.filing_record_id: target}))
        justificante_repo.save(receipt)
        calculation_repo.save(
            CalculationRevisionCatalogue.model_validate(
                {
                    "revisions": {
                        baseline_revision.calculation_revision_id: baseline_revision,
                        revision.calculation_revision_id: revision,
                    }
                },
                context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: context},
            )
        )
        loaded = calculation_repo.load().get(revision.calculation_revision_id)
        assert loaded is not None
        assert loaded.amendment_identity == revision.amendment_identity

        wrong_target = target.model_copy(update={"period": Period.from_year_and_code(2025, "2T")})
        filing_repo.save(ModeloRecordCatalogue(records={target.filing_record_id: wrong_target}))
        with pytest.raises(ValidationError, match="crosses its WorkUnit filing coordinate"):
            calculation_repo.load()

        filing_repo.save(ModeloRecordCatalogue(records={target.filing_record_id: target}))
        without_taxpayer_authority = CalculationRevisionCatalogueRepository(objects=objects)
        with pytest.raises(ValidationError, match="authoritative taxpayer tax id"):
            without_taxpayer_authority.load()


def test_public_amend_service_refuses_missing_motive_before_identity_with_real_persistence(tmp_path: Path) -> None:
    """Free text and a rectificativa kind cannot default the content-addressed motive."""
    work_unit, baseline_revision, target, receipt, _, _ = _authorities()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="S92 service") as runtime:
        objects = runtime.repository
        work_repo = WorkUnitCatalogueRepository(objects=objects)
        filing_repo = ModeloRecordCatalogueRepository(objects=objects)
        justificante_repo = JustificanteRepository(objects=objects)
        calculation_repo = CalculationRevisionCatalogueRepository(
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=_TAX_ID,
        )
        work_repo.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        filing_repo.save(ModeloRecordCatalogue(records={target.filing_record_id: target}))
        justificante_repo.save(receipt)
        calculation_repo.save(
            CalculationRevisionCatalogue(revisions={baseline_revision.calculation_revision_id: baseline_revision})
        )

        with pytest.raises(AmendmentM303RectificativaMotiveError):
            amend_modelo_revision(
                from_filing_record_id=target.filing_record_id,
                overrides={},
                amendment_kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
                m303_rectificativa_motive=None,
                reason="rectificaciones and a lower result are only operator prose",
                actor="operator",
                work_unit_repository=work_repo,
                calculation_repository=calculation_repo,
                filing_repository=filing_repo,
                justificante_repository=justificante_repo,
            )


@pytest.mark.parametrize(
    ("filing_year", "period", "expected_revision_id"),
    (
        (2023, "1T", None),
        (2024, "2T", None),
        (2024, "3T", "2024-desde-09-y-3t"),
        (2025, "1T", "2025"),
        (2026, "1T", "2026-y-siguientes"),
    ),
)
def test_motive_capability_is_selected_only_from_exact_registry_evidence(
    filing_year: int,
    period: str,
    expected_revision_id: str | None,
) -> None:
    snapshot = bundled_authority().snapshot(Modelo.M303.value, filing_year=filing_year, period=period)
    record_design = m303_rectificativa_record_design_from_snapshot(snapshot)
    if expected_revision_id is None:
        assert record_design is None
        return
    assert snapshot.revision.id == expected_revision_id
    assert record_design is not None
    assert m303_rectificativa_motive_is_applicable(
        registry_revision_id=snapshot.revision.id,
        record_design=record_design,
    )


@pytest.mark.parametrize(
    ("field", "replacement"),
    (
        ("id", "aeat-dr-303-future"),
        ("sha256", "f" * 64),
        ("record_design_epoch", "2027"),
    ),
)
def test_motive_capability_refuses_source_digest_and_epoch_inference(field: str, replacement: str) -> None:
    evidence = _filing_evidence()
    record_design = evidence.m303.regimen_simplificado.regimen_snapshot.record_design
    mutated = record_design.model_copy(update={field: replacement})
    assert not m303_rectificativa_motive_is_applicable(
        registry_revision_id="2025",
        record_design=mutated,
    )


@pytest.mark.parametrize(
    ("motive", "expected"),
    (
        (M303RectificativaMotive.RECTIFICACIONES, (True, False)),
        (M303RectificativaMotive.DISCREPANCIA_CRITERIO_ADMINISTRATIVO, (False, True)),
        (None, (None, None)),
    ),
)
def test_two_motive_producer_keys_have_the_complete_truth_table(
    motive: M303RectificativaMotive | None,
    expected: tuple[bool | None, bool | None],
) -> None:
    evidence = (
        AmendmentEvidence(
            kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            m303_rectificativa_motive=motive,
            original_aeat_receipt=_RECEIPT,
        )
        if motive is not None
        else None
    )
    values = m303_rectificativa_motive_producer_values(evidence)
    assert set(values) == {
        FilingProducerKey.AMENDMENT_M303_MOTIVE_RECTIFICACIONES,
        FilingProducerKey.AMENDMENT_M303_MOTIVE_DISCREPANCIA_CRITERIO_ADMINISTRATIVO,
    }
    assert tuple(values.values()) == expected


def test_export_refuses_command_substitution_and_derives_persisted_receipt(tmp_path: Path) -> None:
    work_unit, _, target, receipt, _, revision = _authorities()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="S92") as runtime:
        objects = runtime.repository
        work_repo = WorkUnitCatalogueRepository(objects=objects)
        filing_repo = ModeloRecordCatalogueRepository(objects=objects)
        work_repo.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        filing_repo.save(ModeloRecordCatalogue(records={target.filing_record_id: target}))
        JustificanteRepository(objects=objects).save(receipt)
        justificante_repo = JustificanteRepository(objects=objects)
        exact = AmendmentEvidence(
            kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
            m303_rectificativa_motive=M303RectificativaMotive.RECTIFICACIONES,
            original_aeat_receipt=_RECEIPT,
        )
        command = ModeloExportCommand(
            calculation_revision_id=revision.calculation_revision_id,
            output_path=tmp_path / "s92.303",
            actor="operator",
            amendment_evidence=exact,
        )
        derived_command = command.model_copy(update={"amendment_evidence": None})
        assert (
            resolve_persisted_amendment_export_evidence(
                derived_command,
                revision,
                work_unit=work_unit,
                workflow_profile=_profile(),
                work_unit_repository=work_repo,
                filing_repository=filing_repo,
                justificante_repository=justificante_repo,
            )
            == exact
        )
        assert (
            resolve_persisted_amendment_export_evidence(
                command,
                revision,
                work_unit=work_unit,
                workflow_profile=_profile(),
                work_unit_repository=work_repo,
                filing_repository=filing_repo,
                justificante_repository=justificante_repo,
            )
            == exact
        )

        substitutions = (
            exact.model_copy(
                update={
                    "m303_rectificativa_motive": M303RectificativaMotive.DISCREPANCIA_CRITERIO_ADMINISTRATIVO,
                }
            ),
            exact.model_copy(update={"original_aeat_receipt": "9999999999999"}),
            exact.model_copy(update={"kind": CalculationRevisionAmendmentKind.SUSTITUTIVA}),
        )
        for replacement in substitutions:
            substituted = command.model_copy(update={"amendment_evidence": replacement})
            with pytest.raises(ModeloExportError):
                resolve_persisted_amendment_export_evidence(
                    substituted,
                    revision,
                    work_unit=work_unit,
                    workflow_profile=_profile(),
                    work_unit_repository=work_repo,
                    filing_repository=filing_repo,
                    justificante_repository=justificante_repo,
                )


def test_export_amendment_gate_refuses_missing_injected_justificante_authority(tmp_path: Path) -> None:
    """Export amendment authority cannot infer a receipt repository at the application boundary."""
    work_unit, _, target, _, _, revision = _authorities()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="S92 export gate") as runtime:
        objects = runtime.repository
        work_repo = WorkUnitCatalogueRepository(objects=objects)
        filing_repo = ModeloRecordCatalogueRepository(objects=objects)
        work_repo.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        filing_repo.save(ModeloRecordCatalogue(records={target.filing_record_id: target}))
        command = ModeloExportCommand(
            calculation_revision_id=revision.calculation_revision_id,
            output_path=tmp_path / "s92.303",
            actor="operator",
        )

        with pytest.raises(ModeloExportError) as raised:
            resolve_persisted_amendment_export_evidence(
                command,
                revision,
                work_unit=work_unit,
                workflow_profile=_profile(),
                work_unit_repository=work_repo,
                filing_repository=filing_repo,
                justificante_repository=None,
            )

        assert raised.value.context is not None
        assert raised.value.context["cause"] == "amendment export requires injected justificante repository authority"


def test_public_export_requires_injected_persisted_justificante_authority(tmp_path: Path) -> None:
    """Persisted receipt state does not bypass the application port boundary."""
    work_unit, baseline_revision, target, receipt, context, revision = _authorities()
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID, label="S92 public export") as runtime:
        objects = runtime.repository
        work_repo = WorkUnitCatalogueRepository(objects=objects)
        filing_repo = ModeloRecordCatalogueRepository(objects=objects)
        calculation_repo = CalculationRevisionCatalogueRepository(
            objects=objects,
            m303_rectificativa_taxpayer_tax_id=_TAX_ID,
        )
        work_repo.save(WorkUnitCatalogue.from_work_units((work_unit,)))
        filing_repo.save(ModeloRecordCatalogue(records={target.filing_record_id: target}))
        JustificanteRepository(objects=objects).save(receipt)
        calculation_repo.save(
            CalculationRevisionCatalogue.model_validate(
                {
                    "revisions": {
                        baseline_revision.calculation_revision_id: baseline_revision,
                        revision.calculation_revision_id: revision,
                    }
                },
                context={CALCULATION_REVISION_AGGREGATE_CONTEXT_KEY: context},
            )
        )

        with pytest.raises(ModeloExportError) as raised:
            export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=revision.calculation_revision_id,
                    output_path=tmp_path / "public-default.303",
                    actor="operator",
                ),
                workflow_profile=_profile(),
                work_unit_repository=work_repo,
                calculation_repository=calculation_repo,
                filing_repository=filing_repo,
            )

        assert raised.value.context is not None
        assert raised.value.context["cause"] == "amendment export requires injected justificante repository authority"


def test_m303_motive_is_refused_for_another_modelo_snapshot() -> None:
    with pytest.raises(FilingProducerSnapshotError, match="valid only for modelo 303"):
        build_filing_producer_snapshot(
            modelo=Modelo.M111,
            taxpayer_tax_id="12345678Z",
            taxpayer_identity=TaxpayerIdentityFacts(
                legal_name=None,
                given_name="Ana",
                surnames="Prueba",
                full_name="Ana Prueba",
            ),
            presenter=PresenterIdentity(tax_id="00000000T", full_name="Gestoría Prueba"),
            model_profile=Modelo111ProfileFacts(colegio_concertado=False),
            elections=FilingElectionFacts(
                result_disposition=ResultDisposition.NEGATIVA,
                payment=PaymentElection.INGRESO,
                refund=RefundElection.COMPENSAR,
                prior_domiciliation=PriorDomiciliationElection.KEEP,
            ),
            amendment_evidence=AmendmentEvidence(
                kind=CalculationRevisionAmendmentKind.RECTIFICATIVA,
                m303_rectificativa_motive=M303RectificativaMotive.RECTIFICACIONES,
                original_aeat_receipt=_RECEIPT,
            ),
            refund_account=None,
            charge_account=None,
            m303_filing_facts=None,
        )


def test_non_rectificativa_motive_state_refuses() -> None:
    with pytest.raises(ValidationError, match="valid only for amendment kind rectificativa"):
        CalculationRevisionAmendmentIdentity(
            kind=CalculationRevisionAmendmentKind.COMPLEMENTARIA,
            amends_filing_record_id="f" * 64,
            m303_rectificativa_motive=M303RectificativaMotive.RECTIFICACIONES,
        )


def test_public_work_amend_parser_refuses_free_text_motive() -> None:
    result = invoke_cached_cli(
        [
            "app",
            "modelo",
            "work",
            "amend",
            "--from-filing-record",
            "f" * 64,
            "--kind",
            "rectificativa",
            "--m303-rectificativa-motive",
            "operator prose",
            "--reason",
            "operator prose",
            "--set",
            "07=1.00",
        ]
    )
    assert result.exit_code != 0
    assert "Traceback" not in result.output
