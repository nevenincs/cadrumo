"""Agent-specific, typed modelo binding and readiness projections.

The canonical readers remain in query_read_operation. This module validates
caller values against the same pinned declaration and publishes only closed
result fields whose disclosure was authorized for the MCP destination.
"""

from __future__ import annotations

import asyncio
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, Field, TypeAdapter, ValidationError, model_validator

from ...core.aggregation import BindingTypedEnumKind
from ...core.async_cleanup import await_cancellation_complete
from ...core.errors.hierarchy import CadrumoError
from ...core.external_constants import OutputLanguage
from ...core.identity.digest import ContentDigest
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.operations import OperationEffect
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.binding_selector_utils import boolean_binding_encoded_values
from ...domain.calculations.registry.binding_value_contract import BindingDataType, BindingValueChannel
from ...domain.calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue
from ...domain.calculations.registry.censo_modelos import CensoModeloEventKind
from ...domain.calculations.registry.entity_type import resolve_entity_vocabulary
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.rental_reduction import resolve_rental_reduction_art232_tier_catalogue
from ...domain.calculations.registry.schema import BindingDefinition, RegistrySnapshot
from ...domain.calculations.registry.schema_scalars import CalendarDate, DecimalValue, validate_registry_text_scalar
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from ..ledger.preflight import LedgerPreflightIssueReason
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.models import OperationRequest
from ..operations.owner import OperationExecutorContext
from ..operations.public_period import PublicPeriod
from ..operations.registry import (
    OperationDefinition,
    OperationExecutorFactory,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..operator_actions.preconditions import PROFILE_SETUP_DECLARED_COMPLETE_CONDITION
from ..state_projection import ModeloProfileRefusalCause, ModeloRegistryRefusalCause
from ..user_profile.access_contracts import AccessDenialCode, DisclosureCategory
from ..user_profile.access_errors import ProfileAccessRefusedError
from .query_read_operation import (
    ModeloBindingRowV1,
    ModeloBindingsResolveProjection,
    ModeloBindingsResolveRequest,
    ModeloQueryReadPortsFactory,
    ModeloReadinessMissingBindingV1,
    ModeloReadinessOperationRequest,
    ModeloReadinessProjection,
    modelo_query_read_capabilities,
    read_modelo_bindings_resolve,
    read_modelo_readiness,
    require_modelo_query_worker_identity,
    resolve_modelo_query_read_access,
)

MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID = "modelo.bindings.resolve.typed"
MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID = "modelo.readiness.summary"

_DECIMAL = TypeAdapter[Decimal](DecimalValue)
_CALENDAR_DATE = TypeAdapter[str](CalendarDate)
_VALUE_MAX = 16_384


class ModeloBindingValueContractUnsupportedError(CadrumoError):
    """The pinned binding lacks an official grammar for agent value disclosure."""

    def __init__(self, *, binding_id: str = "", channel: BindingValueChannel | None = None) -> None:
        """Carry only the fixed unsupported-contract refusal text."""
        self.binding_id = binding_id
        self.channel = channel
        super().__init__("modelo binding value contract unsupported")


class ModeloBindingValueInvalidError(CadrumoError):
    """The caller value does not satisfy its pinned official value contract."""

    def __init__(self, *, binding_id: str = "", channel: BindingValueChannel | None = None) -> None:
        """Carry only the fixed invalid-value refusal text."""
        self.binding_id = binding_id
        self.channel = channel
        super().__init__("modelo binding value invalid")


class ModeloTypedBindingValue(BaseModel):
    """Exact canonical override value with its declared legal type and channel."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    binding_id: Annotated[str, Field(min_length=1, max_length=128)]
    data_type: BindingDataType
    channel: BindingValueChannel
    value: Annotated[str, Field(min_length=1, max_length=_VALUE_MAX, repr=False)]


class ModeloBindingsResolveTypedProjection(BaseModel):
    """Complete pinned binding preview with only contract-validated values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.bindings.resolve.typed"] = MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID
    authority_generation: ContentDigest
    profile_id: UUID
    modelo: str
    revision: str
    filing_year: int | None
    period: str | None
    override_count: int
    binding_count: int
    bindings: tuple[ModeloBindingRowV1, ...]
    validated_overrides: tuple[ModeloTypedBindingValue, ...]

    @model_validator(mode="after")
    def _all_values_present(self) -> Self:
        if self.override_count != len(self.validated_overrides) or self.binding_count != len(self.bindings):
            raise ValueError("binding preview count mismatch")
        overrides = {row.binding_id: row.value for row in self.validated_overrides}
        if len(overrides) != self.override_count:
            raise ValueError("duplicate validated binding override")
        if {row.binding_id: row.override for row in self.bindings if row.override is not None} != overrides:
            raise ValueError("binding preview omits a validated override")
        return self


class ModeloReadinessSafeRecovery(BaseModel):
    """Allowlisted recovery identity for the canonical setup-incomplete limb."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    failed_condition_id: Literal["profile.setup.declared_complete"]
    action_id: Literal["operator.profile.complete_setup"]
    missing_argument_names: tuple[str, ...]


class ModeloReadinessSafeLedgerIssue(BaseModel):
    """Transaction address and closed reason without freeform detail."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    transaction_id: str
    reason: LedgerPreflightIssueReason


class ModeloReadinessSafeMissingRequirement(BaseModel):
    """One missing profile field identified by canonical schema keys."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    section_key: Annotated[str, Field(min_length=1, max_length=64)]
    field_key: Annotated[str, Field(min_length=1, max_length=128)]
    legal_refs: tuple[str, ...]
    modelos: tuple[str, ...]


class ModeloReadinessSummaryProjection(BaseModel):
    """Every canonical readiness axis, with typed causes and bounded facts."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    result_version: Literal[1] = 1
    operation: Literal["modelo.readiness.summary"] = MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID
    authority_generation: ContentDigest
    profile_id: UUID
    language: OutputLanguage
    modelo: str
    revision_id: str
    filing_year: int
    period: PublicPeriod
    ready: bool
    profile_ready: bool
    per_operation_requirements_assessed: bool
    profile_refusal_cause: ModeloProfileRefusalCause | None
    profile_recovery: ModeloReadinessSafeRecovery | None
    registry_ready: bool
    registry_refusal_cause: ModeloRegistryRefusalCause | None
    binding_ready: bool
    missing: tuple[ModeloReadinessSafeMissingRequirement, ...]
    missing_bindings: tuple[ModeloReadinessMissingBindingV1, ...]
    ledger_preflight_required: bool
    ledger_ready: bool | None
    ledger_period: PublicPeriod | None
    ledger_checked_transaction_count: int
    ledger_issues: tuple[ModeloReadinessSafeLedgerIssue, ...]


def _bound_targets(snapshot: RegistrySnapshot, binding_id: str) -> tuple[CasillaDefinition, ...]:
    return tuple(
        row for row in snapshot.revision.casillas if row.binding == binding_id or binding_id in row.alternate_bindings
    )


def _validate_typed_enum(
    binding: BindingDefinition,
    raw: str,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date | None,
) -> None:
    kind = binding.value.typed_enum
    if kind is None:
        if binding.value.channel is BindingValueChannel.ENUM:
            raise ModeloBindingValueContractUnsupportedError()
        return
    try:
        if kind is BindingTypedEnumKind.CENSO_EVENT_KIND:
            if binding.value.channel is not BindingValueChannel.ENUM:
                raise ModeloBindingValueContractUnsupportedError()
            CensoModeloEventKind(raw)
        elif kind is BindingTypedEnumKind.CCAA:
            if binding.value.channel is not BindingValueChannel.ENUM:
                raise ModeloBindingValueContractUnsupportedError()
            if effective_date is None:
                raise ModeloBindingValueContractUnsupportedError()
            try:
                catalogue = resolve_ccaa_catalogue(effective_date=effective_date, authority=operation)
            except (RegistrySnapshotError, RegistryValidationError):
                raise ModeloBindingValueContractUnsupportedError() from None
            if str(catalogue.require(raw)) != raw:
                raise ModeloBindingValueInvalidError()
        elif kind is BindingTypedEnumKind.LEGAL_ENTITY_FORM:
            if binding.value.channel is not BindingValueChannel.ENUM:
                raise ModeloBindingValueContractUnsupportedError()
            if effective_date is None:
                raise ModeloBindingValueContractUnsupportedError()
            try:
                vocabulary = resolve_entity_vocabulary(effective_date=effective_date, authority=operation)
            except (RegistrySnapshotError, RegistryValidationError):
                raise ModeloBindingValueContractUnsupportedError() from None
            if str(vocabulary.require_legal_entity_form(raw)) != raw:
                raise ModeloBindingValueInvalidError()
        elif kind is BindingTypedEnumKind.RENTAL_REDUCTION_ART_23_2_TIER:
            if binding.value.channel is not BindingValueChannel.ENUM:
                raise ModeloBindingValueContractUnsupportedError()
            if effective_date is None:
                raise ModeloBindingValueContractUnsupportedError()
            try:
                catalogue = resolve_rental_reduction_art232_tier_catalogue(
                    effective_date=effective_date, authority=operation
                )
            except (RegistrySnapshotError, RegistryValidationError):
                raise ModeloBindingValueContractUnsupportedError() from None
            if str(catalogue.require(raw)) != raw:
                raise ModeloBindingValueInvalidError()
        elif kind is BindingTypedEnumKind.ESTIMACION_DIRECTA_MODALIDAD:
            if binding.value.channel not in {BindingValueChannel.BOOLEAN, BindingValueChannel.DECIMAL}:
                raise ModeloBindingValueContractUnsupportedError()
            encoded = boolean_binding_encoded_values(binding)
            if not encoded:
                raise ModeloBindingValueContractUnsupportedError()
            if raw not in {row.encoded_value for row in encoded}:
                raise ModeloBindingValueInvalidError()
        else:
            raise ModeloBindingValueContractUnsupportedError()
    except RegistrySnapshotError:
        raise ModeloBindingValueContractUnsupportedError() from None
    except (RegistryValidationError, ValueError):
        raise ModeloBindingValueInvalidError() from None


def _validated_value(
    binding: BindingDefinition,
    raw: str,
    snapshot: RegistrySnapshot,
    *,
    operation: PinnedAuthorityOperation,
    effective_date: date | None,
) -> ModeloTypedBindingValue:
    contract = binding.value
    if contract.channel is BindingValueChannel.ROW_SET:
        raise ModeloBindingValueContractUnsupportedError()
    if not raw or len(raw) > _VALUE_MAX:
        raise ModeloBindingValueInvalidError()
    targets = _bound_targets(snapshot, binding.id)
    _validate_typed_enum(binding, raw, operation=operation, effective_date=effective_date)
    try:
        if contract.channel is BindingValueChannel.DECIMAL:
            if len(raw) > 128:
                raise ModeloBindingValueInvalidError()
            number = _DECIMAL.validate_python(raw)
            if not number.is_finite():
                raise ModeloBindingValueInvalidError()
            decimal_parts = number.as_tuple()
            if not isinstance(decimal_parts.exponent, int) or abs(decimal_parts.exponent) > 128:
                raise ModeloBindingValueInvalidError()
            if len(decimal_parts.digits) > 128:
                raise ModeloBindingValueInvalidError()
            if len(format(number, "f")) > 128:
                raise ModeloBindingValueInvalidError()
            encoded = boolean_binding_encoded_values(binding)
            if encoded and raw not in {row.encoded_value for row in encoded}:
                raise ModeloBindingValueInvalidError()
            for target in targets:
                constraints = target.constraints
                if constraints is not None and constraints.violates(number) is not None:
                    raise ModeloBindingValueInvalidError()
        elif contract.channel is BindingValueChannel.INTEGER:
            if len(raw) > 64 or not raw.lstrip("-").isdigit() or raw.startswith("+"):
                raise ModeloBindingValueInvalidError()
            canonical_integer = str(int(raw))
            for target in targets:
                constraints = target.constraints
                if constraints is not None and constraints.violates(Decimal(canonical_integer)) is not None:
                    raise ModeloBindingValueInvalidError()
        elif contract.channel is BindingValueChannel.BOOLEAN:
            encoded = boolean_binding_encoded_values(binding)
            allowed = {row.encoded_value for row in encoded} if encoded else {"true", "false"}
            if raw not in allowed:
                raise ModeloBindingValueInvalidError()
        elif contract.channel is BindingValueChannel.DATE:
            declared = _CALENDAR_DATE.validate_python(raw)
            if len(declared) == 8 and declared.isdigit():
                date(int(declared[4:]), int(declared[2:4]), int(declared[:2]))
            else:
                date.fromisoformat(declared)
        elif contract.channel in {BindingValueChannel.ENUM, BindingValueChannel.TEXT}:
            official = contract.channel is BindingValueChannel.ENUM and contract.typed_enum is not None
            for target in targets:
                if target.data_type.value != "text":
                    if target.data_type.value == "nif":
                        raise ModeloBindingValueContractUnsupportedError()
                    if validate_registry_text_scalar(target.data_type.value, raw) != raw:
                        raise ModeloBindingValueInvalidError()
                    official = True
                constraints = target.constraints
                if constraints is not None and (constraints.enum is not None or constraints.pattern is not None):
                    official = True
                    if constraints.violates_text(raw) is not None:
                        raise ModeloBindingValueInvalidError()
            if not official:
                raise ModeloBindingValueContractUnsupportedError()
        else:
            raise ModeloBindingValueContractUnsupportedError()
    except ModeloBindingValueContractUnsupportedError:
        raise
    except (RegistryValidationError, ValidationError, ValueError, OverflowError):
        raise ModeloBindingValueInvalidError() from None
    return ModeloTypedBindingValue(
        binding_id=binding.id, data_type=contract.data_type, channel=contract.channel, value=raw
    )


def _typed_resolve(
    payload: ModeloBindingsResolveRequest, operation: PinnedAuthorityOperation
) -> ModeloBindingsResolveTypedProjection:
    period = payload.period.to_period()
    snapshot = operation.snapshot(
        payload.modelo, filing_year=period.filing_year, period=period.registry_token, on=payload.as_of
    )
    declarations = {row.id: row for row in snapshot.revision.bindings}
    for override in payload.overrides:
        if override.binding_id not in declarations:
            raise ModeloBindingValueInvalidError()
    try:
        human: ModeloBindingsResolveProjection = read_modelo_bindings_resolve(payload, operation=operation)
    except RegistryValidationError:
        raise ModeloBindingValueInvalidError() from None
    if snapshot.revision.id != human.revision:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    validated_rows: list[ModeloTypedBindingValue] = []
    for override in payload.overrides:
        declaration = declarations.get(override.binding_id)
        if declaration is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        try:
            validated_rows.append(
                _validated_value(
                    declaration,
                    override.value,
                    snapshot,
                    operation=operation,
                    effective_date=payload.as_of or (period.end_date if period.has_date_span() else None),
                )
            )
        except (ModeloBindingValueContractUnsupportedError, ModeloBindingValueInvalidError) as error:
            raise type(error)(binding_id=declaration.id, channel=declaration.value.channel) from None
    validated = tuple(validated_rows)
    canonical = {row.binding_id: row.value for row in validated}
    rows = tuple(row.model_copy(update={"override": canonical.get(row.binding_id)}) for row in human.bindings)
    return ModeloBindingsResolveTypedProjection(
        authority_generation=human.authority_generation,
        profile_id=payload.profile_id,
        modelo=human.modelo,
        revision=human.revision,
        filing_year=human.filing_year,
        period=human.period,
        override_count=human.override_count,
        binding_count=human.binding_count,
        bindings=rows,
        validated_overrides=validated,
    )


def _readiness_summary(
    payload: ModeloReadinessOperationRequest,
    factory: ModeloQueryReadPortsFactory,
    operation: PinnedAuthorityOperation,
) -> ModeloReadinessSummaryProjection:
    # The canonical reader constructs all axes once. Its human prose stays in
    # worker memory and never enters the agent result operand.
    source = read_modelo_readiness(payload, factory, operation=operation)
    if (source.profile_refusal and source.profile_refusal_cause is None) or (
        source.registry_refusal and source.registry_refusal_cause is None
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    report = ModeloReadinessProjection.from_report(
        payload.profile_id,
        source,
        language=payload.language,
        authority_generation=operation.generation.logical_generation,
    )
    verdict = report.profile_precondition_verdict
    if verdict is not None and source.profile_refusal_cause is not ModeloProfileRefusalCause.SETUP_INCOMPLETE:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if verdict is not None and (
        verdict.failed_condition_id != PROFILE_SETUP_DECLARED_COMPLETE_CONDITION
        or verdict.action_id != "operator.profile.complete_setup"
        or verdict.missing_argument_names
        or verdict.argument_bindings
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return ModeloReadinessSummaryProjection(
        authority_generation=report.authority_generation,
        profile_id=report.profile_id,
        language=report.language,
        modelo=report.modelo,
        revision_id=report.revision_id,
        filing_year=report.filing_year,
        period=report.period,
        ready=report.ready,
        profile_ready=report.profile_ready,
        per_operation_requirements_assessed=report.per_operation_requirements_assessed,
        profile_refusal_cause=source.profile_refusal_cause,
        profile_recovery=(
            ModeloReadinessSafeRecovery(
                failed_condition_id="profile.setup.declared_complete",
                action_id="operator.profile.complete_setup",
                missing_argument_names=(),
            )
            if verdict is not None
            else None
        ),
        registry_ready=report.registry_ready,
        registry_refusal_cause=source.registry_refusal_cause,
        binding_ready=report.binding_ready,
        missing=tuple(
            ModeloReadinessSafeMissingRequirement(
                section_key=row.section_key,
                field_key=row.field_key,
                legal_refs=row.legal_refs,
                modelos=row.modelos,
            )
            for row in source.missing
        ),
        missing_bindings=report.missing_bindings,
        ledger_preflight_required=report.ledger_preflight_required,
        ledger_ready=report.ledger_ready,
        ledger_period=report.ledger_period,
        ledger_checked_transaction_count=report.ledger_checked_transaction_count,
        ledger_issues=tuple(
            ModeloReadinessSafeLedgerIssue(transaction_id=row.transaction_id, reason=row.reason)
            for row in source.ledger_issues
        ),
    )


class ModeloBindingsResolveTypedExecutor:
    """Capture validated exact override values through the retained pin."""

    async def execute(
        self, request: OperationRequest[ModeloBindingsResolveRequest], context: OperationExecutorContext
    ) -> str:
        """Capture the validated preview inside the admitted worker."""
        require_modelo_query_worker_identity(
            MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(_typed_resolve, request.payload, context.authority_operation)
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-bindings-resolve-typed")


class ModeloReadinessSummaryExecutor:
    """Capture safe readiness causes without diagnostic strings."""

    def __init__(self, factory: ModeloQueryReadPortsFactory) -> None:
        """Retain the exact-profile readiness read-port factory."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloReadinessOperationRequest], context: OperationExecutorContext
    ) -> str:
        """Capture all canonical readiness axes with safe typed causes."""
        require_modelo_query_worker_identity(
            MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(
                _readiness_summary, request.payload, self._factory, context.authority_operation
            )
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-readiness-summary")


def build_modelo_bindings_resolve_typed_definition() -> OperationDefinition:
    """Define the agent-only validated binding preview."""
    return OperationDefinition(
        definition_id=MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID,
        request_type=ModeloBindingsResolveRequest,
        result_type=ModeloBindingsResolveTypedProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloBindingsResolveRequest,
            executor_type=ModeloBindingsResolveTypedExecutor,
            build=ModeloBindingsResolveTypedExecutor,
        ),
        phase_codes=(MODELO_BINDINGS_RESOLVE_TYPED_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=modelo_query_read_capabilities(sensitive=True),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.MCP}),
    )


def build_modelo_readiness_summary_definition(factory: ModeloQueryReadPortsFactory) -> OperationDefinition:
    """Define the agent-only readiness summary."""
    return OperationDefinition(
        definition_id=MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID,
        request_type=ModeloReadinessOperationRequest,
        result_type=ModeloReadinessSummaryProjection,
        executor_factory=OperationExecutorFactory(
            request_type=ModeloReadinessOperationRequest,
            executor_type=ModeloReadinessSummaryExecutor,
            build=lambda: ModeloReadinessSummaryExecutor(factory),
        ),
        phase_codes=(MODELO_READINESS_SUMMARY_OPERATION_DEFINITION_ID,),
        interaction_kinds=frozenset(),
        capabilities=modelo_query_read_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset({OperationFrontendProjection.MCP}),
    )


def _registration(
    definition: OperationDefinition, request_type: type[BaseModel], result_type: type[BaseModel]
) -> OperationPublicDefinitionRegistrationV1:
    def resolve(request: OperationRequest[BaseModel], context: OperationAccessContext, /) -> ResolvedOperationAccess:
        if context.frontend is not OperationFrontendProjection.MCP:
            raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
        return resolve_modelo_query_read_access(
            request,
            context,
            definition_id=definition.definition_id,
            payload_type=request_type,
            result_category=DisclosureCategory.TAX_VALUES,
        )

    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=request_type
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=result_type
        ),
        access_resolver=resolve,
    )


def build_modelo_bindings_resolve_typed_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the closed typed preview and its exact result grant."""
    return _registration(definition, ModeloBindingsResolveRequest, ModeloBindingsResolveTypedProjection)


def build_modelo_readiness_summary_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the closed readiness summary and its all-period rule."""
    return _registration(definition, ModeloReadinessOperationRequest, ModeloReadinessSummaryProjection)
