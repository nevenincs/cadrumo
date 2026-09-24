"""Focused proofs for the value-free Modelo Edit Contract admission producer."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import override

import pytest

from ....core.authority_grade import RegistryAuthorityGrade
from ....core.modelo import Modelo
from ....core.period import Period
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.ids import RevisionId
from ....domain.calculations.registry.ledger_renta_income_bindings import LedgerRentaIncomeProvider
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.schema import (
    BindingDefinition,
    ModeloDefinition,
    ModeloRevision,
    RegistrySnapshot,
)
from ....domain.calculations.registry.schema_base import CasillaDataType
from ....domain.calculations.registry.schema_input_kind import InputKind
from ....domain.calculations.registry.schema_surfaces import CasillaDefinition
from ....domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ....domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, derive_work_unit_id
from ...operations.registry import (
    OperationPublicContractSetV1,
    OperationPublicDefinitionContractV1,
    OperationSchemaIdentityV1,
)
from ..edit_admission import admit_modelo_edit_baseline
from ..edit_models import (
    ModeloEditAdmittedV1,
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditRefusalCode,
    ModeloEditRefusedV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_NOW = datetime(2026, 9, 21, 10, 0, tzinfo=UTC)
_DIGEST = "a" * 64


def _recording_operation(prepared: RegistrySnapshot) -> tuple[PinnedAuthorityOperation, list[dict[str, object]]]:
    """Return a pinned operation serving ``prepared``, and the coordinates it is asked for."""
    calls: list[dict[str, object]] = []

    class _RecordingOperation(PinnedAuthorityOperation):
        @override
        def snapshot(
            self,
            modelo_id: str | Modelo,
            *,
            filing_year: int,
            period: str,
            on: date | None = None,
            revision_id: RevisionId | None = None,
            grade: RegistryAuthorityGrade = RegistryAuthorityGrade.FILING,
        ) -> RegistrySnapshot:
            calls.append(
                {
                    "modelo_id": modelo_id,
                    "filing_year": filing_year,
                    "period": period,
                    "on": on,
                    "revision_id": revision_id,
                    "grade": grade,
                }
            )
            return prepared

    return _RecordingOperation.__new__(_RecordingOperation), calls


def _casilla(casilla_id: str, input_kind: InputKind, data_type: CasillaDataType) -> CasillaDefinition:
    return CasillaDefinition.model_construct(id=casilla_id, input_kind=input_kind, data_type=data_type)


def _manual_binding(binding_id: str) -> BindingDefinition:
    return BindingDefinition.model_construct(id=binding_id, provider=ManualInputProvider.model_construct())


def _ledger_binding(binding_id: str) -> BindingDefinition:
    return BindingDefinition.model_construct(id=binding_id, provider=LedgerRentaIncomeProvider.model_construct())


def _modelo_100_snapshot(
    casillas: tuple[CasillaDefinition, ...],
    bindings: tuple[BindingDefinition, ...],
) -> RegistrySnapshot:
    revision = ModeloRevision.model_construct(
        id="2025-y-siguientes",
        casillas=casillas,
        bindings=bindings,
        completeness_manifest=None,
    )
    return RegistrySnapshot.model_construct(modelo=ModeloDefinition.model_construct(id="100"), revision=revision)


def _work_unit(*, current_calculation_revision_id: str | None = None) -> WorkUnit:
    period = Period.from_year_and_code(2025, "0A")
    return WorkUnit(
        work_unit_id=derive_work_unit_id(
            bucket_id="income-edit-bucket",
            modelo="100",
            filing_year=2025,
            period=period,
            revision_id="2025-y-siguientes",
        ),
        bucket_id="income-edit-bucket",
        modelo="100",
        filing_year=2025,
        period=period,
        revision_id="2025-y-siguientes",
        name="Income 2025",
        created_at=_NOW,
        updated_at=_NOW,
        current_calculation_revision_id=current_calculation_revision_id,
    )


def _snapshot() -> RegistrySnapshot:
    return _modelo_100_snapshot(
        casillas=(
            _casilla("0001", InputKind.MANUAL, CasillaDataType.TEXT),
            _casilla("0171", InputKind.COMPUTED, CasillaDataType.MONEY),
        ),
        bindings=(
            _manual_binding("renta-manual"),
            _ledger_binding("renta-ledger"),
        ),
    )


def _contracts(*, include_edit: bool = True) -> OperationPublicContractSetV1:
    schema = OperationSchemaIdentityV1(
        schema_id="modelo.edit.apply.request", schema_version=1, schema_fingerprint=_DIGEST
    )
    contract = OperationPublicDefinitionContractV1.model_construct(
        manifest_version=1,
        definition_id="modelo.edit.apply",
        request_schema=schema,
        result_schema=OperationSchemaIdentityV1(
            schema_id="modelo.edit.apply.result", schema_version=1, schema_fingerprint="b" * 64
        ),
        review_projection_schema=None,
        workspace_refresh_target_schema=OperationSchemaIdentityV1(
            schema_id="modelo.workspace.refresh-target", schema_version=1, schema_fingerprint="c" * 64
        ),
        definition_contract_digest="d" * 64,
    )
    return OperationPublicContractSetV1.model_construct(
        definitions=(contract,) if include_edit else (),
        contract_set_digest="e" * 64,
    )


def _admit(
    *,
    current_calculation_revision_id: str | None = None,
    contracts: OperationPublicContractSetV1 | None = None,
    snapshot: RegistrySnapshot | None = None,
):
    work_unit = _work_unit(current_calculation_revision_id=current_calculation_revision_id)
    operation, calls = _recording_operation(_snapshot() if snapshot is None else snapshot)
    outcome = admit_modelo_edit_baseline(
        work_unit_id=work_unit.work_unit_id,
        work_catalogue=WorkUnitCatalogue(work_units={work_unit.work_unit_id: work_unit}),
        calculation_catalogue=CalculationRevisionCatalogue(),
        operation=operation,
        operation_contracts=_contracts() if contracts is None else contracts,
        issued_at=_NOW,
    )
    return outcome, calls


def _sized_snapshot(*, casillas: int, bindings: int) -> RegistrySnapshot:
    return _modelo_100_snapshot(
        casillas=tuple(
            _casilla(f"{index:04d}", InputKind.COMPUTED, CasillaDataType.MONEY) for index in range(1, casillas + 1)
        ),
        bindings=tuple(_manual_binding(f"renta-surface-{index}") for index in range(bindings)),
    )


def test_published_2025_modelo_100_surface_size_is_admitted_without_dropping_entries() -> None:
    outcome, _ = _admit(snapshot=_sized_snapshot(casillas=2249, bindings=71))

    assert isinstance(outcome, ModeloEditAdmittedV1)
    assert len(outcome.baseline.permitted_surface) == 2320
    assert (
        sum(
            isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1)
            for entry in outcome.baseline.permitted_surface
        )
        == 71
    )


def test_oversized_edit_surface_refuses_at_admission_before_model_validation() -> None:
    from ..edit_models import MAX_MODELO_EDIT_SURFACE_ENTRIES

    outcome, _ = _admit(snapshot=_sized_snapshot(casillas=MAX_MODELO_EDIT_SURFACE_ENTRIES + 1, bindings=0))

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.code is ModeloEditRefusalCode.REGISTRY_SCHEMA_CONFLICT
    assert outcome.refusal.facts == ("edit_surface_exceeds_contract_limit",)


def test_admission_re_resolves_the_work_and_pinned_authority_into_a_value_free_five_minute_baseline() -> None:
    outcome, calls = _admit()

    assert isinstance(outcome, ModeloEditAdmittedV1)
    baseline = outcome.baseline
    assert baseline.issued_at == _NOW
    assert baseline.expires_at == _NOW + timedelta(minutes=5)
    assert baseline.law_selected_revision_id == "2025-y-siguientes"
    assert baseline.compatibility.operation_definition_id == "modelo.edit.apply"
    assert calls == [
        {
            "modelo_id": "100",
            "filing_year": 2025,
            "period": "0A",
            "on": None,
            "revision_id": "2025-y-siguientes",
            "grade": RegistryAuthorityGrade.FILING,
        }
    ]
    assert not any("value" in field for field in baseline.model_dump(mode="json"))
    assert any(
        isinstance(entry, ModeloEditWritableScalarSurfaceEntryV1) and entry.casilla_id == "0001"
        for entry in baseline.permitted_surface
    )
    assert any(
        isinstance(entry, ModeloEditNonWritableScalarSurfaceEntryV1) and entry.casilla_id == "0171"
        for entry in baseline.permitted_surface
    )
    assert any(
        isinstance(entry, ModeloEditWritableBindingOverrideSurfaceEntryV1) and entry.binding_id == "renta-manual"
        for entry in baseline.permitted_surface
    )
    assert any(
        isinstance(entry, ModeloEditNonWritableBindingOverrideSurfaceEntryV1) and entry.binding_id == "renta-ledger"
        for entry in baseline.permitted_surface
    )


def test_admission_refuses_a_missing_current_calculation_head_without_reusing_a_workspace_read() -> None:
    outcome, _ = _admit(current_calculation_revision_id="f" * 64)

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.code == "calculation_head_conflict"


def test_admission_refuses_when_the_required_public_operation_contract_is_not_composed() -> None:
    outcome, _ = _admit(contracts=_contracts(include_edit=False))

    assert isinstance(outcome, ModeloEditRefusedV1)
    assert outcome.refusal.kind == "unsupported_compatibility"
