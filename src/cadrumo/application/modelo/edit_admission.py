"""Application-owned admission for the Modelo Edit Contract V1.

This producer reads the selected work unit, its current calculation head, the
authority snapshot pinned to the caller's operation, and the public operation
contract set.  It deliberately accepts no workspace projection and no taxpayer
value: an edit baseline is a fresh compare-and-swap coordinate, never a copy of
what a renderer happened to display.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from ...core.aggregation import BindingSourceKind
from ...core.hashing import content_hash_hex
from ...core.time.clock import now as clock_now
from ...domain.calculations.registry.schema import RegistrySnapshot
from ...domain.calculations.registry.schema_base import CasillaDataType
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.modelos.calculation_revision import CalculationRevisionCatalogue
from ...domain.modelos.work_unit import WorkUnitCatalogue, WorkUnitState
from ..operations.financial_operand import OperationTransientFinancialOperandRequirement
from ..operations.registry import OperationPublicContractSetV1, OperationSchemaIdentityV1
from .edit_contract import ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
from .edit_models import (
    MAX_MODELO_EDIT_SURFACE_ENTRIES,
    ModeloEditAdmissionResultV1,
    ModeloEditAdmittedV1,
    ModeloEditBaselineV1,
    ModeloEditBindingIntentKind,
    ModeloEditCompatibilityRefusalV1,
    ModeloEditDomainRefusalV1,
    ModeloEditNonWritableBindingOverrideSurfaceEntryV1,
    ModeloEditNonWritableReason,
    ModeloEditNonWritableScalarSurfaceEntryV1,
    ModeloEditPermittedSurfaceEntryV1,
    ModeloEditRefusalCode,
    ModeloEditRefusedV1,
    ModeloEditScalarIntentKind,
    ModeloEditSchemaIdentityV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation


RESPONSIBLE_OWNER = "modelo.edit"
"""Owner recorded on every admission refusal this producer returns."""

MODELO_EDIT_APPLY_DEFINITION_ID = "modelo.edit.apply"
_BASELINE_LIFETIME = timedelta(minutes=5)


def _refused(code: ModeloEditRefusalCode, condition: str, *facts: str) -> ModeloEditRefusedV1:
    return ModeloEditRefusedV1(
        refusal=ModeloEditDomainRefusalV1(
            code=code,
            facts=facts,
            responsible_owner=RESPONSIBLE_OWNER,
            reconsideration_condition=condition,
        )
    )


def _compatibility_refusal(axis: str, condition: str) -> ModeloEditRefusedV1:
    return ModeloEditRefusedV1(
        refusal=ModeloEditCompatibilityRefusalV1(
            requested_axis=axis,
            responsible_owner=RESPONSIBLE_OWNER,
            reconsideration_condition=condition,
        )
    )


def _operation_compatibility(
    contracts: OperationPublicContractSetV1,
) -> ModeloEditCompatibilityTupleV1 | ModeloEditRefusedV1:
    """Resolve every public operation axis the edit baseline must pin exactly."""
    contract = next(
        (item for item in contracts.definitions if item.definition_id == MODELO_EDIT_APPLY_DEFINITION_ID), None
    )
    if contract is None:
        return _compatibility_refusal(
            "operation_definition_id", "compose the modelo.edit.apply public operation contract before admission"
        )
    if contract.result_schema is None:
        return _compatibility_refusal("result_schema", "compose the edit operation result schema before admission")
    if contract.workspace_refresh_target_schema is None:
        return _compatibility_refusal(
            "workspace_refresh_target_schema", "compose the edit operation refresh-target schema before admission"
        )
    financial_operand_schema = OperationSchemaIdentityV1.from_model(
        schema_id="operation.financial-operand.requirement",
        schema_version=1,
        model_type=OperationTransientFinancialOperandRequirement,
    )
    return ModeloEditCompatibilityTupleV1(
        contract_set_digest=contracts.contract_set_digest,
        operation_definition_id=contract.definition_id,
        definition_contract_digest=contract.definition_contract_digest,
        request_schema=contract.request_schema,
        result_schema=contract.result_schema,
        review_projection_contract_version=(1 if contract.review_projection_schema is not None else None),
        review_schema=contract.review_projection_schema,
        workspace_refresh_target_schema=contract.workspace_refresh_target_schema,
        financial_operand_schema=financial_operand_schema,
    )


def _schema_identity(snapshot: RegistrySnapshot) -> ModeloEditSchemaIdentityV1:
    revision = snapshot.revision
    return ModeloEditSchemaIdentityV1(
        schema_id=f"modelo-{snapshot.modelo.id}-{revision.id}".lower(),
        schema_fingerprint=content_hash_hex(
            {
                "casilla_ids": sorted(str(casilla.id) for casilla in revision.casillas),
                "binding_ids": sorted(str(binding.id) for binding in revision.bindings),
            }
        ),
        completeness_manifest_digest=content_hash_hex(
            {"completeness_manifest": None}
            if revision.completeness_manifest is None
            else revision.completeness_manifest.model_dump(mode="json")
        ),
    )


def _permitted_surface(snapshot: RegistrySnapshot) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
    """Project writable manual inputs and explicitly expose every other input as read-only."""
    revision = snapshot.revision
    entries: list[ModeloEditPermittedSurfaceEntryV1] = []
    for casilla in revision.casillas:
        if casilla.input_kind is InputKind.MANUAL:
            entries.append(
                ModeloEditWritableScalarSurfaceEntryV1(
                    casilla_id=casilla.id,
                    data_type=CasillaDataType(casilla.data_type),
                    allowed_intents=(
                        ModeloEditScalarIntentKind.SET_TYPED_VALUE,
                        ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE,
                    ),
                )
            )
            continue
        entries.append(
            ModeloEditNonWritableScalarSurfaceEntryV1(
                casilla_id=casilla.id,
                reason=(
                    ModeloEditNonWritableReason.COMPUTED_BY_FORMULA
                    if casilla.input_kind is InputKind.COMPUTED
                    else ModeloEditNonWritableReason.SCHEMA_DECLARED_READ_ONLY
                ),
            )
        )
    for binding in revision.bindings:
        if binding.source is BindingSourceKind.MANUAL_INPUT:
            entries.append(
                ModeloEditWritableBindingOverrideSurfaceEntryV1(
                    binding_id=binding.id,
                    allowed_intents=(
                        ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
                        ModeloEditBindingIntentKind.REMOVE_OVERRIDE,
                    ),
                )
            )
            continue
        entries.append(
            ModeloEditNonWritableBindingOverrideSurfaceEntryV1(
                binding_id=binding.id,
                reason=ModeloEditNonWritableReason.SCHEMA_DECLARED_READ_ONLY,
            )
        )

    def address_key(entry: ModeloEditPermittedSurfaceEntryV1) -> tuple[str, str]:
        if isinstance(entry, (ModeloEditWritableScalarSurfaceEntryV1, ModeloEditNonWritableScalarSurfaceEntryV1)):
            return "scalar", str(entry.casilla_id)
        if isinstance(
            entry, (ModeloEditWritableBindingOverrideSurfaceEntryV1, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
        ):
            return "binding", str(entry.binding_id)
        raise TypeError("the admission producer emitted an unsupported edit surface entry")

    return tuple(sorted(entries, key=address_key))


def admit_modelo_edit_baseline(
    *,
    work_unit_id: str,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    operation: PinnedAuthorityOperation,
    operation_contracts: OperationPublicContractSetV1,
    issued_at: datetime | None = None,
) -> ModeloEditAdmissionResultV1:
    """Produce a five-minute, value-free edit baseline from live authoritative state.

    The supplied ``work_unit_id`` is resolved from the catalogue afresh.  The
    authority snapshot is selected from that unit's complete coordinate and
    fixed revision, so an unpinned workspace read cannot redirect an edit to a
    later registry revision.
    """
    work_unit = work_catalogue.get(work_unit_id)
    if work_unit is None:
        return _refused(ModeloEditRefusalCode.TARGET_ABSENT, "select an existing work unit", "work_unit_absent")
    if work_unit.state is WorkUnitState.DESCARTADO:
        return _refused(ModeloEditRefusalCode.ADMISSION_DENIED, "select an active work unit", "work_unit_discarded")
    current_revision_id = work_unit.current_calculation_revision_id
    if current_revision_id is not None:
        current_revision = calculation_catalogue.get(current_revision_id)
        if current_revision is None or current_revision.work_unit_id != work_unit.work_unit_id:
            return _refused(
                ModeloEditRefusalCode.CALCULATION_HEAD_CONFLICT,
                "refresh the selected work unit and calculation catalogue before admission",
                "current_calculation_revision_id",
            )
    snapshot = operation.snapshot(
        str(work_unit.modelo),
        filing_year=work_unit.filing_year,
        period=work_unit.period.registry_token,
    )
    if snapshot.revision.id != work_unit.revision_id:
        return _refused(
            ModeloEditRefusalCode.REGISTRY_SCHEMA_CONFLICT,
            "refresh the selected work unit against its pinned authority revision",
            "law_selected_revision_id",
        )
    compatibility = _operation_compatibility(operation_contracts)
    if isinstance(compatibility, ModeloEditRefusedV1):
        return compatibility
    issue_time = issued_at if issued_at is not None else clock_now()
    surface = _permitted_surface(snapshot)
    if len(surface) > MAX_MODELO_EDIT_SURFACE_ENTRIES:
        return _refused(
            ModeloEditRefusalCode.REGISTRY_SCHEMA_CONFLICT,
            "publish a supported modelo edit surface within the operation contract bound",
            "edit_surface_exceeds_contract_limit",
        )
    schema_identity = _schema_identity(snapshot)
    work_catalogue_revision = content_hash_hex(work_catalogue.model_dump(mode="json"))
    calculation_catalogue_revision = content_hash_hex(calculation_catalogue.model_dump(mode="json"))
    permitted_surface_digest = content_hash_hex([entry.model_dump(mode="json") for entry in surface])
    expires_at = issue_time + _BASELINE_LIFETIME
    baseline_id = content_hash_hex(
        {
            "compatibility": compatibility.model_dump(mode="json"),
            "bucket_id": work_unit.bucket_id,
            "modelo": str(work_unit.modelo),
            "filing_year": work_unit.filing_year,
            "period": work_unit.period.model_dump(mode="json"),
            "work_unit_id": work_unit.work_unit_id,
            "work_catalogue_revision": work_catalogue_revision,
            "calculation_catalogue_revision": calculation_catalogue_revision,
            "current_calculation_revision_id": current_revision_id,
            "law_selected_revision_id": work_unit.revision_id,
            "schema_identity": schema_identity.model_dump(mode="json"),
            "schema_version": 1,
            "permitted_surface_digest": permitted_surface_digest,
            "mutation_family": ModeloEditMutationFamily.CALCULATE,
            "issued_at": issue_time.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
    )
    return ModeloEditAdmittedV1(
        baseline=ModeloEditBaselineV1(
            compatibility=compatibility,
            bucket_id=work_unit.bucket_id,
            modelo=work_unit.modelo,
            filing_year=work_unit.filing_year,
            period=work_unit.period,
            work_unit_id=work_unit.work_unit_id,
            work_catalogue_revision=work_catalogue_revision,
            calculation_catalogue_revision=calculation_catalogue_revision,
            current_calculation_revision_id=current_revision_id,
            law_selected_revision_id=work_unit.revision_id,
            schema_identity=schema_identity,
            schema_version=1,
            permitted_surface=surface,
            permitted_surface_digest=permitted_surface_digest,
            mutation_family=ModeloEditMutationFamily.CALCULATE,
            issued_at=issue_time,
            expires_at=expires_at,
            baseline_id=baseline_id,
        )
    )


__all__ = ["MODELO_EDIT_APPLY_DEFINITION_ID", "RESPONSIBLE_OWNER", "admit_modelo_edit_baseline"]
