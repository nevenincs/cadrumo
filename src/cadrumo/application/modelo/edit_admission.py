"""Application-owned admission for the Modelo Edit Contract V1.

This producer reads the selected work unit, its current calculation head, the
authority snapshot pinned to the caller's operation, and the public operation
contract set.  It deliberately accepts no workspace projection and no taxpayer
value: an edit baseline is a fresh compare-and-swap coordinate, never a copy of
what a renderer happened to display.

Core types:
:class:`~cadrumo.domain.calculations.registry.schema.RegistrySnapshot`.

See Also:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas, formulas, bindings and layout metadata.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Annotated, Final, Literal

from pydantic import Field

from ...core.aggregation import BindingSourceKind
from ...core.authority_grade import RegistryAuthorityGrade
from ...core.casilla_id import CasillaId
from ...core.hashing import content_hash_hex
from ...core.time.clock import now as clock_now
from ...domain.calculations.registry.casilla_membership import row_field_template_records_by_casilla
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision, RegistrySnapshot
from ...domain.calculations.registry.schema_base import CasillaDataType
from ...domain.calculations.registry.schema_input_kind import InputKind
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ...domain.modelos.calculation_revision import CalculationRevision, CalculationRevisionCatalogue
from ...domain.modelos.work_unit import WorkUnit, WorkUnitCatalogue, WorkUnitState
from ..operations.registry import OperationPublicContractSetV1
from .calculation_source_policy import BUCKET_AGGREGATION_LOCK_SOURCES, CALLER_OVERRIDABLE_CARRY_SOURCES
from .edit_contract import EditModel, ModeloEditCompatibilityTupleV1, ModeloEditMutationFamily
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
    ModeloEditStaleBaselineRefusalV1,
    ModeloEditWritableBindingOverrideSurfaceEntryV1,
    ModeloEditWritableScalarSurfaceEntryV1,
)
from .edit_services import calculation_head_digest, work_unit_record_digest
from .edit_value_grammar import binding_value_grammar, casilla_value_grammar

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
    if contract.transient_financial_operand is None:
        return _compatibility_refusal("financial_operand_schema", "compose the typed edit operand before admission")
    financial_operand_schema = contract.transient_financial_operand.operand_schema
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


def _scalar_entry(
    casilla: CasillaDefinition,
    *,
    row_field_casilla_ids: frozenset[CasillaId],
) -> ModeloEditPermittedSurfaceEntryV1:
    """Classify one casilla: writable only when an operator value can reach the engine as a scalar."""
    if casilla.input_kind is not InputKind.MANUAL:
        return ModeloEditNonWritableScalarSurfaceEntryV1(
            casilla_id=casilla.id,
            reason=(
                ModeloEditNonWritableReason.COMPUTED_BY_FORMULA
                if casilla.input_kind is InputKind.COMPUTED
                else ModeloEditNonWritableReason.SCHEMA_DECLARED_READ_ONLY
            ),
        )
    if casilla.id in row_field_casilla_ids:
        # A row-field template stands for one field of every repeated row; the
        # calculation refuses a scalar value for it.
        return ModeloEditNonWritableScalarSurfaceEntryV1(
            casilla_id=casilla.id, reason=ModeloEditNonWritableReason.ROW_FIELD_TEMPLATE
        )
    grammar = casilla_value_grammar(casilla)
    if not grammar.writable:
        return ModeloEditNonWritableScalarSurfaceEntryV1(
            casilla_id=casilla.id, reason=ModeloEditNonWritableReason.VALUE_CHANNEL_UNAVAILABLE
        )
    return ModeloEditWritableScalarSurfaceEntryV1(
        casilla_id=casilla.id,
        data_type=CasillaDataType(casilla.data_type),
        allowed_intents=(
            ModeloEditScalarIntentKind.SET_TYPED_VALUE,
            ModeloEditScalarIntentKind.CLEAR_DECLARED_VALUE,
            ModeloEditScalarIntentKind.RESTORE_SOURCE_VALUE,
        ),
        grammar=grammar,
    )


def _binding_entry(binding: BindingDefinition, *, revision: ModeloRevision) -> ModeloEditPermittedSurfaceEntryV1:
    """Classify one binding's override by its source's grounded override policy.

    A manual-input binding and a carry source of the caller-override
    precedence ladder take an operator override; a deterministic source the
    ladder locks does not, because the declaration would stop reflecting the
    records it adds up. Every other source kind has no grounded override
    policy yet and stays read-only as undecided rather than guessed.
    """
    source = binding.source
    if source in BUCKET_AGGREGATION_LOCK_SOURCES:
        return ModeloEditNonWritableBindingOverrideSurfaceEntryV1(
            binding_id=binding.id, reason=ModeloEditNonWritableReason.SOURCE_LOCKED
        )
    if source is not BindingSourceKind.MANUAL_INPUT and source not in CALLER_OVERRIDABLE_CARRY_SOURCES:
        return ModeloEditNonWritableBindingOverrideSurfaceEntryV1(
            binding_id=binding.id, reason=ModeloEditNonWritableReason.OVERRIDE_POLICY_UNDECIDED
        )
    grammar = binding_value_grammar(binding, revision=revision)
    if not grammar.writable:
        return ModeloEditNonWritableBindingOverrideSurfaceEntryV1(
            binding_id=binding.id, reason=ModeloEditNonWritableReason.VALUE_CHANNEL_UNAVAILABLE
        )
    return ModeloEditWritableBindingOverrideSurfaceEntryV1(
        binding_id=binding.id,
        allowed_intents=(
            ModeloEditBindingIntentKind.SET_OVERRIDE_VALUE,
            ModeloEditBindingIntentKind.REMOVE_OVERRIDE,
        ),
        grammar=grammar,
    )


def _permitted_surface(snapshot: RegistrySnapshot) -> tuple[ModeloEditPermittedSurfaceEntryV1, ...]:
    """Classify every casilla and binding of the revision as writable or read-only with its reason."""
    revision = snapshot.revision
    row_field_casilla_ids = frozenset(row_field_template_records_by_casilla(revision))
    entries: list[ModeloEditPermittedSurfaceEntryV1] = [
        _scalar_entry(casilla, row_field_casilla_ids=row_field_casilla_ids) for casilla in revision.casillas
    ]
    entries.extend(_binding_entry(binding, revision=revision) for binding in revision.bindings)

    def address_key(entry: ModeloEditPermittedSurfaceEntryV1) -> tuple[str, str]:
        if isinstance(entry, (ModeloEditWritableScalarSurfaceEntryV1, ModeloEditNonWritableScalarSurfaceEntryV1)):
            return "scalar", str(entry.casilla_id)
        if isinstance(
            entry, (ModeloEditWritableBindingOverrideSurfaceEntryV1, ModeloEditNonWritableBindingOverrideSurfaceEntryV1)
        ):
            return "binding", str(entry.binding_id)
        raise TypeError("the admission producer emitted an unsupported edit surface entry")

    return tuple(sorted(entries, key=address_key))


def _calculation_grade_snapshot(
    work_unit: WorkUnit,
    *,
    operation: PinnedAuthorityOperation,
) -> RegistrySnapshot | ModeloEditRefusedV1:
    """Select the rung of authority an edit needs: the one that computes amounts.

    An edit recalculates in memory exactly as the calculate path does, so a
    revision that honestly declares calculation grade is admitted; one below
    it (applicability only) cannot be calculated at all and is refused here
    rather than raising out of admission.
    """
    try:
        return operation.snapshot(
            str(work_unit.modelo),
            filing_year=work_unit.filing_year,
            period=work_unit.period.registry_token,
            grade=RegistryAuthorityGrade.CALCULATION,
        )
    except RegistryValidationError:
        return _refused(
            ModeloEditRefusalCode.ADMISSION_DENIED,
            "edit a modelo revision whose registry authority reaches calculation grade",
            "registry_authority_grade",
        )


def _current_edit_calculation_head(
    work_unit: WorkUnit, calculation_catalogue: CalculationRevisionCatalogue, current_revision_id: str | None
) -> CalculationRevision | ModeloEditRefusedV1 | None:
    """Refuse a missing or foreign current head before selecting authority."""
    head = None
    if current_revision_id is not None:
        head = calculation_catalogue.get(current_revision_id)
        if head is None or head.work_unit_id != work_unit.work_unit_id:
            return _refused(
                ModeloEditRefusalCode.CALCULATION_HEAD_CONFLICT,
                "refresh the selected work unit and calculation catalogue before admission",
                "current_calculation_revision_id",
            )
    return head


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
    later registry revision. The concurrency coordinates are the edited work
    unit's own record and its current calculation head, so work on any other
    declaration of the profile does not stale this baseline. Every
    precondition failure is a typed refusal, never an exception.
    """
    work_unit = work_catalogue.get(work_unit_id)
    if work_unit is None:
        return _refused(ModeloEditRefusalCode.TARGET_ABSENT, "select an existing work unit", "work_unit_absent")
    if work_unit.state is WorkUnitState.DESCARTADO:
        return _refused(ModeloEditRefusalCode.ADMISSION_DENIED, "select an active work unit", "work_unit_discarded")
    current_revision_id = work_unit.current_calculation_revision_id
    head = _current_edit_calculation_head(work_unit, calculation_catalogue, current_revision_id)
    if isinstance(head, ModeloEditRefusedV1):
        return head
    snapshot = _calculation_grade_snapshot(work_unit, operation=operation)
    if isinstance(snapshot, ModeloEditRefusedV1):
        return snapshot
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
    record_digest = work_unit_record_digest(work_unit)
    head_digest = calculation_head_digest(head)
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
            "work_unit_record_digest": record_digest,
            "calculation_head_digest": head_digest,
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
            work_unit_record_digest=record_digest,
            calculation_head_digest=head_digest,
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


#: Every baseline coordinate a renewal must find unchanged before it may adopt
#: the fresh admission silently. Issue time, expiry and the baseline identity
#: derived from them are deliberately absent: they are the lifetime, not a fact
#: about the declaration.
_RENEWAL_COORDINATES: Final = (
    "compatibility",
    "bucket_id",
    "modelo",
    "filing_year",
    "period",
    "work_unit_id",
    "work_unit_record_digest",
    "calculation_head_digest",
    "current_calculation_revision_id",
    "law_selected_revision_id",
    "schema_identity",
    "schema_version",
    "permitted_surface_digest",
    "mutation_family",
)


class ModeloEditRenewedV1(EditModel):
    """A renewal that found nothing but the baseline's lifetime changed."""

    outcome: Literal["renewed"] = "renewed"
    baseline: ModeloEditBaselineV1


type ModeloEditRenewalResultV1 = Annotated[
    ModeloEditRenewedV1 | ModeloEditRefusedV1,
    Field(discriminator="outcome"),
]


def renew_modelo_edit_baseline(
    baseline: ModeloEditBaselineV1,
    *,
    work_catalogue: WorkUnitCatalogue,
    calculation_catalogue: CalculationRevisionCatalogue,
    operation: PinnedAuthorityOperation,
    operation_contracts: OperationPublicContractSetV1,
    issued_at: datetime | None = None,
) -> ModeloEditRenewalResultV1:
    """Re-admit ``baseline`` and adopt the result only when nothing but its lifetime changed.

    An editor renews at review and again just before submitting, so the
    five-minute lifetime never surfaces while nothing has happened. When any
    real coordinate moved -- the work unit's record, its calculation head, the
    authority revision, the schema or the permitted surface -- the renewal is
    refused as a stale baseline naming every coordinate that moved. It never
    rebases the operator's staged edits onto the new state.
    """
    admission = admit_modelo_edit_baseline(
        work_unit_id=baseline.work_unit_id,
        work_catalogue=work_catalogue,
        calculation_catalogue=calculation_catalogue,
        operation=operation,
        operation_contracts=operation_contracts,
        issued_at=issued_at,
    )
    if isinstance(admission, ModeloEditRefusedV1):
        return admission
    fresh = admission.baseline
    moved = tuple(name for name in _RENEWAL_COORDINATES if getattr(fresh, name) != getattr(baseline, name))
    if moved:
        return ModeloEditRefusedV1(
            refusal=ModeloEditStaleBaselineRefusalV1(
                baseline_id=baseline.baseline_id,
                mismatching_coordinates=moved[:8],
                responsible_owner=RESPONSIBLE_OWNER,
                reconsideration_condition="review the staged edits against the declaration's new state",
            )
        )
    return ModeloEditRenewedV1(baseline=fresh)


__all__ = [
    "MODELO_EDIT_APPLY_DEFINITION_ID",
    "RESPONSIBLE_OWNER",
    "ModeloEditRenewalResultV1",
    "ModeloEditRenewedV1",
    "admit_modelo_edit_baseline",
    "renew_modelo_edit_baseline",
]
