"""Amending an in-force pending correction chains to the latest confirmed declaration."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.adapters.persistence.profile.calculation_observations import CalculationObservationRepository
from cadrumo.application.calculations.observations_repository import ObservationSourceKind
from cadrumo.application.modelo.action_errors import AmendmentEvidenceMissingError
from cadrumo.application.modelo.amendment_actions import amend_modelo_revision
from cadrumo.core.casilla_id import validated_casilla_id
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.schema_references import RegistrySnapshotRef
from cadrumo.domain.modelos.calculation_repository import upsert_calculation_revision
from cadrumo.domain.modelos.calculation_revision import (
    CalculationRevision,
    CalculationRevisionState,
    derive_calculation_revision_id,
)
from cadrumo.domain.modelos.calculation_revision_operator_layer import CalculationOperatorLayer
from cadrumo.domain.modelos.filing_record import (
    AeatConfirmationState,
    ExternalEvidence,
    ExternalEvidenceKind,
    FilingDeclarationKind,
    FilingOrigin,
    ModeloRecord,
    ModeloRecordStatus,
    derive_filing_record_id,
)
from cadrumo.domain.modelos.filing_repository import upsert_filing_record
from cadrumo.entrypoints.adapter_composition_work_ports import build_amendment_action_ports
from cadrumo.entrypoints.tests.profile_persistence.import_flow_support import (
    IMPORT_INCOME_CASILLA,
    T1,
    T2,
    T3,
    TAX_ID,
    Repos,
    import_external_filing,
    persist_matching_justificante,
    repos,
    seed_work_unit,
)

__all__ = ["repos"]

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _amend(work_unit_bucket_id: str, record_id: str, income: str, *, operation: PinnedAuthorityOperation, clock):
    return amend_modelo_revision(
        ports=build_amendment_action_ports(bucket_id=work_unit_bucket_id, operation=operation),
        from_filing_record_id=record_id,
        overrides={IMPORT_INCOME_CASILLA: Decimal(income)},
        amendment_kind=FilingDeclarationKind.COMPLEMENTARIA,
        reason="revenue correction",
        actor="operator-A",
        clock=clock,
        operation=operation,
    )


def _seed_operation_backed_original(repos: Repos, *, operation: PinnedAuthorityOperation):
    """Persist a confirmed 130 source with its actual engine inputs and binding channels."""
    wu_repo, cr_repo, fr_repo, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, bv_repo, operation=operation)
    snapshot = operation.snapshot("130", filing_year=work_unit.filing_year, period=work_unit.period.registry_token)
    inputs = {
        IMPORT_INCOME_CASILLA: Decimal("1500"),
        validated_casilla_id("gastos-deducibles-previos"): Decimal("300"),
        validated_casilla_id("05"): Decimal("0"),
        validated_casilla_id("06"): Decimal("0"),
        validated_casilla_id("16"): Decimal("0"),
        validated_casilla_id("18"): Decimal("0"),
        validated_casilla_id("rendimiento-neto-reducible-art-32-1"): Decimal("0"),
    }
    bindings = {
        "modelo-130-actividad-economica-ingresos-cumulative": Decimal("1500"),
        "modelo-130-actividad-economica-gastos-cumulative": Decimal("300"),
        "modelo-130-volumen-ingresos-agrario": Decimal("0"),
        "modelo-130-retenciones-agrarias": Decimal("0"),
        "modelo-130-pagos-fraccionados-anteriores": Decimal("0"),
        "modelo-130-resultados-negativos-anteriores": Decimal("0"),
        "irpf.previous_year_economic_activity_net_income": Decimal("0"),
    }
    enum_bindings = {"modelo-130-estimacion-directa-modalidad": "directa_simplificada"}
    result = calculate_registry_snapshot(
        snapshot,
        inputs=inputs,
        binding_values=bindings,
        enum_binding_values=enum_bindings,
        date_context={},
    )
    saved_inputs = {key: str(value) for key, value in inputs.items()}
    saved_bindings = {key: str(value) for key, value in bindings.items()} | enum_bindings
    operator_layer = CalculationOperatorLayer(
        decimal_casilla_inputs=saved_inputs,
        binding_overrides=saved_bindings,
    )
    revision_id = derive_calculation_revision_id(
        work_unit_id=work_unit.work_unit_id,
        input_values_by_casilla_id=saved_inputs,
        binding_overrides=saved_bindings,
        operator_layer=operator_layer,
        casilla_values=result.values,
        source_provenance=(),
        filing_instance_evidence=None,
    )
    revision = CalculationRevision(
        calculation_revision_id=revision_id,
        work_unit_id=work_unit.work_unit_id,
        registry_snapshot_ref=RegistrySnapshotRef(
            modelo=work_unit.modelo,
            revision_id=work_unit.revision_id,
            modelo_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
        ),
        state=CalculationRevisionState.PRESENTADO,
        input_values_by_casilla_id=saved_inputs,
        binding_overrides=saved_bindings,
        operator_layer=operator_layer,
        casilla_values=result.values,
        observations=result.observations,
        source_provenance=(),
        filing_instance_evidence=None,
        created_at=T1,
        updated_at=T1,
        verified_at=T1,
        verified_by="aeat-import",
        filed_at=T1,
        filed_by="aeat-import",
    )
    cr_repo.save(upsert_calculation_revision(cr_repo.load(), revision))
    record_id = derive_filing_record_id(
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        filed_by="aeat-import",
    )
    record = ModeloRecord(
        filing_record_id=record_id,
        work_unit_id=work_unit.work_unit_id,
        calculation_revision_id=revision_id,
        bucket_id=work_unit.bucket_id,
        modelo=work_unit.modelo,
        filing_year=work_unit.filing_year,
        period=work_unit.period,
        filed_at=T1,
        filed_by="aeat-import",
        notes=None,
        origin=FilingOrigin.AEAT,
        confirmation=AeatConfirmationState.CONFIRMADA,
        declaration_kind=FilingDeclarationKind.ORIGINAL,
        status=ModeloRecordStatus.VIGENTE,
        external_evidence=ExternalEvidence(
            kind=ExternalEvidenceKind.AEAT_JUSTIFICANTE_PDF,
            reference_id="JUSTCHAIN0001",
            imported_at=T1,
        ),
    )
    fr_repo.save(upsert_filing_record(fr_repo.load(), record))
    return work_unit, record


def test_amending_a_pending_correction_discards_it_and_amends_the_confirmed_declaration(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    _wu_repo, _cr_repo, fr_repo, _, _bv_repo = repos
    work_unit, imported = _seed_operation_backed_original(repos, operation=operation)

    first = _amend(work_unit.bucket_id, imported.filing_record_id, "1600", operation=operation, clock=T2)
    second = _amend(work_unit.bucket_id, first.filing_record_id, "1700", operation=operation, clock=T3)

    catalogue = fr_repo.load()
    discarded = catalogue.records[first.filing_record_id]
    confirmed = catalogue.records[imported.filing_record_id]
    in_force = catalogue.records[second.filing_record_id]
    assert discarded.confirmation is AeatConfirmationState.DESCARTADA
    assert discarded.status is ModeloRecordStatus.SUPERSEDIDO
    assert discarded.superseded_by_filing_record_id == second.filing_record_id
    assert in_force.status is ModeloRecordStatus.VIGENTE
    assert in_force.confirmation is AeatConfirmationState.PENDIENTE
    assert in_force.declaration_kind is FilingDeclarationKind.COMPLEMENTARIA
    assert in_force.amends_filing_record_id == imported.filing_record_id
    assert confirmed.superseded_by_filing_record_id == second.filing_record_id
    assert (
        catalogue.latest_confirmed_for(
            bucket_id=work_unit.bucket_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
        )
        == confirmed
    )

    layers = CalculationObservationRepository().load_observation_layers(work_unit.modelo, work_unit.period)
    assert layers.pending_local is not None
    assert layers.pending_local.source_kind is ObservationSourceKind.APP_FILING
    assert layers.pending_local.observation.casilla_values[IMPORT_INCOME_CASILLA] == Decimal("1700")


def test_amending_without_a_confirmed_declaration_is_refused(
    repos: Repos, *, operation: PinnedAuthorityOperation
) -> None:
    wu_repo, _cr_repo, fr_repo, _, bv_repo = repos
    work_unit = seed_work_unit(wu_repo, bv_repo, operation=operation)
    persist_matching_justificante("JUSTCHAIN0002", work_unit, captured_at=T1)
    imported = import_external_filing(
        repos,
        work_unit,
        casilla_values={IMPORT_INCOME_CASILLA: Decimal("1500")},
        evidence_reference_id="JUSTCHAIN0002",
        expected_tax_id=TAX_ID,
        clock=T1,
    )
    pending = _amend(work_unit.bucket_id, imported.filing_record_id, "1600", operation=operation, clock=T2)
    catalogue = fr_repo.load()
    unconfirmed = catalogue.records[imported.filing_record_id].model_copy(
        update={
            "origin": catalogue.records[pending.filing_record_id].origin,
            "confirmation": AeatConfirmationState.DESCARTADA,
            "external_evidence": None,
            "aeat_register": None,
        },
    )
    fr_repo.save(
        catalogue.model_copy(update={"records": {**catalogue.records, unconfirmed.filing_record_id: unconfirmed}})
    )

    with pytest.raises(AmendmentEvidenceMissingError):
        _amend(work_unit.bucket_id, pending.filing_record_id, "1700", operation=operation, clock=T3)
