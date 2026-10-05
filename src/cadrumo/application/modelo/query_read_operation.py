"""Registered exact-profile modelo binding and readiness reads.

The registry and state-projection services remain the only authorities for
these answers. This module owns their operation custody and public wire form.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import date
from uuid import UUID

from pydantic import BaseModel

from ...core.async_cleanup import await_cancellation_complete
from ...core.config import override_settings
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.period import Period
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistrySnapshotError, RegistryValidationError
from ...domain.calculations.registry.query_reports import ModeloBindingsReport
from ...domain.user_profile.errors import ProfileNotFoundError
from ..operations.access_resolution import (
    ADMISSION_REPLAY_ACTIONS,
    OperationAccessContext,
    ResolvedOperationAccess,
    require_admitted_submission,
)
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.frontend_requests import OPERATION_OBSERVATION_PROJECTION_ID
from ..operations.models import OperationRequest
from ..operations.operation_definition import OperationDefinition, build_single_phase_definition
from ..operations.owner import OperationExecutorContext
from ..operations.profile_guard import require_operation_profile
from ..operations.registry import (
    ALL_OPERATION_FRONTENDS,
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationSchemaBindingV1,
)
from ..state_projection import (
    ModeloReadinessRequest,
    ProjectionModeloReadiness,
    build_modelo_readiness_reports,
)
from ..user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    Availability,
    DisclosureCategory,
    DisclosurePermission,
    OperationAccessPolicy,
    OperationAccessRequest,
)
from ..user_profile.access_errors import ProfileAccessRefusedError
from .binding_readiness import profile_resolvable_binding_ids
from .data_inventory import data_inventory_checklist
from .query_read_contracts import (
    ModeloBindingRowV1,
    ModeloBindingsListProjection,
    ModeloBindingsListRequest,
    ModeloBindingsResolveProjection,
    ModeloBindingsResolveRequest,
    ModeloQueryReadPortsFactory,
    ModeloReadinessOperationRequest,
    ModeloReadinessProjection,
    ModeloRequiresProjection,
    ModeloRequiresRequest,
)
from .registry_discovery import (
    registry_bindings,
    registry_bindings_for_scope,
    registry_bindings_for_year,
    registry_modelo_codes,
)
from .work_addressing import law_selected_revision_for_work_target

MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID = "modelo.bindings.list"
MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID = "modelo.bindings.resolve"
MODELO_REQUIRES_OPERATION_DEFINITION_ID = "modelo.requires"
MODELO_READINESS_OPERATION_DEFINITION_ID = "modelo.readiness"


def require_modelo_query_worker_identity[PayloadT: BaseModel](
    definition_id: str, profile_id: UUID, request: OperationRequest[PayloadT], context: OperationExecutorContext
) -> str:
    """Require one exact-profile subject and active bucket for a query executor."""
    bucket_id = str(profile_id)
    if request.definition_id != definition_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    require_operation_profile(request, context, profile_id)
    return bucket_id


def _binding_report(
    modelo: str,
    *,
    year: int | None,
    period_code: str | None,
    as_of: date | None,
    operation: PinnedAuthorityOperation,
) -> ModeloBindingsReport:
    if year is not None and period_code is not None:
        return registry_bindings_for_scope(
            modelo, period=Period.from_year_and_code(year, period_code), as_of=as_of, operation=operation
        )
    if year is not None:
        return registry_bindings_for_year(modelo, filing_year=year, as_of=as_of, operation=operation)
    return registry_bindings(modelo, period=period_code, as_of=as_of, operation=operation)


def _listing_report(
    modelo: str,
    payload: ModeloBindingsListRequest,
    *,
    operation: PinnedAuthorityOperation,
) -> ModeloBindingsReport | None:
    try:
        return _binding_report(
            modelo,
            year=payload.year,
            period_code=payload.period_code,
            as_of=payload.as_of,
            operation=operation,
        )
    except (RegistrySnapshotError, RegistryValidationError):
        if payload.modelo is not None:
            raise
        return None


def _resolved_listing_binding_ids(
    payload: ModeloBindingsListRequest,
    report: ModeloBindingsReport,
    *,
    operation: PinnedAuthorityOperation,
) -> frozenset[str]:
    if not payload.missing or report.filing_year is None:
        return frozenset[str]()
    try:
        return profile_resolvable_binding_ids(
            modelo=report.code,
            bucket_id=str(payload.profile_id),
            filing_year=report.filing_year,
            period=report.filing_period,
            as_of=payload.as_of,
            revision_id=report.revision,
            operation=operation,
        )
    except (RegistrySnapshotError, RegistryValidationError, ProfileNotFoundError):
        return frozenset[str]()


def _listing_rows_for_report(
    payload: ModeloBindingsListRequest,
    report: ModeloBindingsReport,
    *,
    operation: PinnedAuthorityOperation,
) -> tuple[ModeloBindingRowV1, ...]:
    resolved = _resolved_listing_binding_ids(payload, report, operation=operation)
    return tuple(
        ModeloBindingRowV1.from_report_row(report, row)
        for row in report.rows
        if not payload.missing or (row.operator_input_required and row.binding_id not in resolved)
    )


def _read_bindings_list(
    payload: ModeloBindingsListRequest, *, operation: PinnedAuthorityOperation
) -> ModeloBindingsListProjection:
    known_codes = registry_modelo_codes(operation=operation)
    if payload.catalogue_only:
        return ModeloBindingsListProjection(
            authority_generation=operation.generation.logical_generation,
            profile_id=payload.profile_id,
            modelo_filter=None,
            year_filter=None,
            period_filter=None,
            missing_filter=False,
            catalogue_only=True,
            known_modelos=known_codes,
            binding_count=0,
            bindings=(),
        )
    if payload.modelo is not None and payload.modelo not in known_codes:
        raise RegistryValidationError(
            f"modelo {payload.modelo!r} is not in the calculation registry; accepted: {', '.join(known_codes)}",
            translated_message="errors.error.error_calculations_registry_validation",
            context={"modelo": payload.modelo, "accepted": ", ".join(known_codes)},
        )
    rows: list[ModeloBindingRowV1] = []
    for modelo in (payload.modelo,) if payload.modelo is not None else known_codes:
        report = _listing_report(modelo, payload, operation=operation)
        if report is not None:
            rows.extend(_listing_rows_for_report(payload, report, operation=operation))
    return ModeloBindingsListProjection(
        authority_generation=operation.generation.logical_generation,
        profile_id=payload.profile_id,
        modelo_filter=payload.modelo,
        year_filter=payload.year,
        period_filter=payload.period_code,
        missing_filter=payload.missing,
        catalogue_only=False,
        known_modelos=known_codes,
        binding_count=len(rows),
        bindings=tuple(rows),
    )


def read_modelo_bindings_resolve(
    payload: ModeloBindingsResolveRequest, *, operation: PinnedAuthorityOperation
) -> ModeloBindingsResolveProjection:
    """Read the complete canonical unsaved binding preview once."""
    report = registry_bindings_for_scope(
        payload.modelo, period=payload.period.to_period(), as_of=payload.as_of, operation=operation
    )
    overrides = {row.binding_id: row.value for row in payload.overrides}
    if set(overrides) - {row.binding_id for row in report.rows}:
        unknown = sorted(set(overrides) - {row.binding_id for row in report.rows})
        accepted = ", ".join(row.binding_id for row in report.rows)
        raise RegistryValidationError(
            f"unknown binding overrides: {', '.join(unknown)}; accepted: {accepted}",
            translated_message="errors.error.error_calculations_registry_validation",
            context={
                "modelo": report.code,
                "revision": report.revision,
                "period": report.period or "",
                "unknown": ", ".join(unknown),
                "accepted": accepted,
            },
        )
    rows = tuple(
        ModeloBindingRowV1.from_report_row(report, row, override=overrides.get(row.binding_id)) for row in report.rows
    )
    return ModeloBindingsResolveProjection(
        authority_generation=operation.generation.logical_generation,
        profile_id=payload.profile_id,
        modelo=report.code,
        revision=report.revision,
        filing_year=report.filing_year,
        period=report.period,
        override_count=len(overrides),
        binding_count=len(rows),
        bindings=rows,
    )


def _read_requires(payload: ModeloRequiresRequest, *, operation: PinnedAuthorityOperation) -> ModeloRequiresProjection:
    with override_settings(cadrumo_output_language=payload.language):
        checklist = data_inventory_checklist(
            modelo=payload.modelo,
            filing_year=payload.period.filing_year,
            period=payload.period.to_period(),
            bucket_id=str(payload.profile_id),
            operation=operation,
        )
    return ModeloRequiresProjection.from_checklist(
        payload.profile_id,
        checklist,
        language=payload.language,
        authority_generation=operation.generation.logical_generation,
    )


def read_modelo_readiness(
    payload: ModeloReadinessOperationRequest,
    factory: ModeloQueryReadPortsFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> ProjectionModeloReadiness:
    """Evaluate one canonical readiness report under the retained authority pin."""
    bucket_id = str(payload.profile_id)
    ports = factory(bucket_id=bucket_id, operation=operation)
    if ports.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    profile = ports.read_ports.profile.read_profile(profile_id=bucket_id)
    if profile is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    if profile.bucket_id != bucket_id:
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    period = payload.period.to_period() if payload.period is not None else None
    with override_settings(cadrumo_output_language=payload.language):
        revision_id = law_selected_revision_for_work_target(
            modelo=payload.modelo,
            filing_year=payload.filing_year,
            period=period or Period.from_year_and_code(payload.filing_year, "0A"),
            requested_revision_id=payload.revision_id,
            operation=operation,
        )
        reports = build_modelo_readiness_reports(
            (
                ModeloReadinessRequest(
                    modelo=payload.modelo,
                    revision_id=revision_id,
                    filing_year=payload.filing_year,
                    period=period,
                ),
            ),
            active_profile_id=bucket_id,
            read_ports=ports.read_ports,
            operation=operation,
        )
    if len(reports) != 1:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_DENIED)
    return reports[0]


class ModeloBindingsListExecutor:
    """Capture a complete ordered binding listing in encrypted custody."""

    async def execute(
        self, request: OperationRequest[ModeloBindingsListRequest], context: OperationExecutorContext
    ) -> str:
        """Read through the retained authority and publish a NONE-effect result."""
        require_modelo_query_worker_identity(
            MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(
                _read_bindings_list, request.payload, operation=context.authority_operation
            )
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-bindings-list")


class ModeloBindingsResolveExecutor:
    """Capture a temporary exact-scope binding preview."""

    async def execute(
        self, request: OperationRequest[ModeloBindingsResolveRequest], context: OperationExecutorContext
    ) -> str:
        """Read the preview without saving its temporary values."""
        require_modelo_query_worker_identity(
            MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(
                read_modelo_bindings_resolve, request.payload, operation=context.authority_operation
            )
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-bindings-resolve")


class ModeloRequiresExecutor:
    """Capture the canonical one-period data inventory."""

    async def execute(self, request: OperationRequest[ModeloRequiresRequest], context: OperationExecutorContext) -> str:
        """Read one canonical inventory without a write section."""
        require_modelo_query_worker_identity(
            MODELO_REQUIRES_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_REQUIRES_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            result = await asyncio.to_thread(_read_requires, request.payload, operation=context.authority_operation)
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-requires")


class ModeloReadinessExecutor:
    """Capture all canonical profile, registry, binding and ledger axes."""

    def __init__(self, factory: ModeloQueryReadPortsFactory) -> None:
        """Bind a profile-specific state projection reader."""
        self._factory = factory

    async def execute(
        self, request: OperationRequest[ModeloReadinessOperationRequest], context: OperationExecutorContext
    ) -> str:
        """Read every readiness axis under the retained authority pin."""
        require_modelo_query_worker_identity(
            MODELO_READINESS_OPERATION_DEFINITION_ID, request.payload.profile_id, request, context
        )
        await context.events.phase(MODELO_READINESS_OPERATION_DEFINITION_ID)

        async def capture() -> str:
            report = await asyncio.to_thread(
                read_modelo_readiness, request.payload, self._factory, operation=context.authority_operation
            )
            result = ModeloReadinessProjection.from_report(
                request.payload.profile_id,
                report,
                language=request.payload.language,
                authority_generation=context.authority_operation.generation.logical_generation,
            )
            ref = await context.operands.put(result, written_at=now())
            await context.events.effect(OperationEffect.NONE)
            return ref

        return await await_cancellation_complete(capture(), task_name="modelo-readiness")


def modelo_query_read_capabilities(*, sensitive: bool = False) -> OperationCapabilities:
    """Keep all read-only modelo query custody and effect guarantees aligned."""
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.NONE,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=(
            OperationRequestStoragePolicy.SECURE_REFERENCE
            if sensitive
            else OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL
        ),
        sensitive_input=(
            OperationSensitiveInputPolicy.SECURE_REFERENCE if sensitive else OperationSensitiveInputPolicy.NONE
        ),
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset(),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _read_definition(
    definition_id: str,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    executor_type: type[object],
    build_executor: Callable[[], object],
    *,
    sensitive: bool = False,
    public_error_detail: bool = False,
    permitted_frontends: frozenset[OperationFrontendProjection] = frozenset(
        {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI}
    ),
) -> OperationDefinition:
    return build_single_phase_definition(
        definition_id=definition_id,
        request_type=request_type,
        result_type=result_type,
        executor_type=executor_type,
        build=build_executor,
        capabilities=modelo_query_read_capabilities(sensitive=sensitive),
        permitted_frontends=permitted_frontends,
        public_error_detail=public_error_detail,
    )


def build_modelo_bindings_list_definition() -> OperationDefinition:
    """Define the read-only bindings list operation."""
    return _read_definition(
        MODELO_BINDINGS_LIST_OPERATION_DEFINITION_ID,
        ModeloBindingsListRequest,
        ModeloBindingsListProjection,
        ModeloBindingsListExecutor,
        ModeloBindingsListExecutor,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_modelo_bindings_resolve_definition() -> OperationDefinition:
    """Define the unsaved binding preview operation."""
    return _read_definition(
        MODELO_BINDINGS_RESOLVE_OPERATION_DEFINITION_ID,
        ModeloBindingsResolveRequest,
        ModeloBindingsResolveProjection,
        ModeloBindingsResolveExecutor,
        ModeloBindingsResolveExecutor,
        sensitive=True,
    )


def build_modelo_requires_definition() -> OperationDefinition:
    """Define the read-only data inventory operation."""
    return _read_definition(
        MODELO_REQUIRES_OPERATION_DEFINITION_ID,
        ModeloRequiresRequest,
        ModeloRequiresProjection,
        ModeloRequiresExecutor,
        ModeloRequiresExecutor,
        permitted_frontends=ALL_OPERATION_FRONTENDS,
    )


def build_modelo_readiness_definition(factory: ModeloQueryReadPortsFactory) -> OperationDefinition:
    """Define the read-only canonical readiness operation."""
    return _read_definition(
        MODELO_READINESS_OPERATION_DEFINITION_ID,
        ModeloReadinessOperationRequest,
        ModeloReadinessProjection,
        ModeloReadinessExecutor,
        lambda: ModeloReadinessExecutor(factory),
        public_error_detail=True,
    )


def _requested_scope(payload: BaseModel) -> tuple[frozenset[Period], bool, bool]:
    """Return exact period, independence and all-period requirement."""
    if type(payload) is ModeloBindingsListRequest:
        if payload.year is not None and payload.period_code is not None:
            return frozenset({Period.from_year_and_code(payload.year, payload.period_code)}), False, False
        return frozenset[Period](), True, payload.missing
    if type(payload) is ModeloBindingsResolveRequest or type(payload) is ModeloRequiresRequest:
        return frozenset({payload.period.to_period()}), False, False
    if type(payload) is ModeloReadinessOperationRequest:
        if payload.period is not None:
            return frozenset({payload.period.to_period()}), False, False
        return frozenset[Period](), True, True
    raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)


def _validated_access_payload(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[BaseModel],
) -> BaseModel:
    payload = request.payload
    if (
        request.definition_id != definition_id
        or context.contract.definition_id != definition_id
        or type(payload) is not payload_type
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if not isinstance(
        payload,
        (
            ModeloBindingsListRequest,
            ModeloBindingsResolveRequest,
            ModeloRequiresRequest,
            ModeloReadinessOperationRequest,
        ),
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    if payload.profile_id != context.profile_id or request.subject_ref != profile_operation_subject(
        str(payload.profile_id)
    ):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    return payload


def _authorized_query_scope(
    payload: BaseModel,
    context: OperationAccessContext,
    definition_id: str,
) -> tuple[frozenset[Period], bool, bool]:
    periods, period_independent, requires_all_periods = _requested_scope(payload)
    admitted = context.admitted_request
    if admitted is not None and context.action in ADMISSION_REPLAY_ACTIONS:
        require_admitted_submission(admitted, profile_id=context.profile_id, definition_id=definition_id)
        periods = admitted.periods
        period_independent = admitted.period_independent
    elif context.authority_operation is None:
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return periods, period_independent, requires_all_periods


def _query_disclosure(
    context: OperationAccessContext, result_category: DisclosureCategory
) -> DisclosurePermission | None:
    disclosure = None
    if context.action in {AccessAction.OBSERVE, AccessAction.CANCEL, AccessAction.DETACH}:
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=OPERATION_OBSERVATION_PROJECTION_ID,
            category=DisclosureCategory.OPERATION_METADATA,
        )
    elif context.action is AccessAction.RESULT:
        schema = context.contract.result_schema
        if schema is None:
            raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
        disclosure = DisclosurePermission(
            destination_id=context.destination_id,
            projection_id=schema.schema_id,
            category=result_category,
        )
    return disclosure


def _query_access_request(
    context: OperationAccessContext,
    definition_id: str,
    periods: frozenset[Period],
    period_independent: bool,
) -> OperationAccessRequest:
    return OperationAccessRequest(
        profile_id=context.profile_id,
        definition_id=definition_id,
        action=context.action,
        frontend=context.frontend,
        periods=periods,
        period_independent=period_independent,
        destination_id=context.destination_id,
    )


def _query_access_policy(
    context: OperationAccessContext,
    definition_id: str,
    periods: frozenset[Period],
    period_independent: bool,
    requires_all_periods: bool,
    disclosure: DisclosurePermission | None,
) -> OperationAccessPolicy:
    return OperationAccessPolicy(
        definition_id=definition_id,
        definition_contract_digest=context.contract.definition_contract_digest,
        actions=frozenset(
            {
                AccessAction.SUBMIT,
                AccessAction.START,
                AccessAction.RESUME,
                AccessAction.OBSERVE,
                AccessAction.RESULT,
                AccessAction.CANCEL,
                AccessAction.DETACH,
            }
        ),
        disclosures=frozenset((disclosure,)) if disclosure is not None else frozenset(),
        periods=periods,
        allow_period_independent=period_independent,
        requires_all_periods=requires_all_periods,
        backend=Availability.AVAILABLE,
        published_authority=context.published_authority,
        provider=Availability.NOT_REQUIRED,
        transaction_authority_required=False,
    )


def resolve_modelo_query_read_access(
    request: OperationRequest[BaseModel],
    context: OperationAccessContext,
    *,
    definition_id: str,
    payload_type: type[BaseModel],
    result_category: DisclosureCategory,
) -> ResolvedOperationAccess:
    """Resolve an exact modelo query scope and public result category."""
    payload = _validated_access_payload(request, context, definition_id=definition_id, payload_type=payload_type)
    periods, period_independent, requires_all_periods = _authorized_query_scope(payload, context, definition_id)
    disclosure = _query_disclosure(context, result_category)
    return ResolvedOperationAccess(
        request=_query_access_request(context, definition_id, periods, period_independent),
        policy=_query_access_policy(
            context,
            definition_id,
            periods,
            period_independent,
            requires_all_periods,
            disclosure,
        ),
    )


def _read_registration(
    definition: OperationDefinition,
    *,
    request_type: type[BaseModel],
    result_type: type[BaseModel],
    category: DisclosureCategory,
) -> OperationPublicDefinitionRegistrationV1:
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request",
            schema_version=1,
            model_type=request_type,
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=result_type,
        ),
        access_resolver=lambda request, context: resolve_modelo_query_read_access(
            request,
            context,
            definition_id=definition.definition_id,
            payload_type=request_type,
            result_category=category,
        ),
    )


def build_modelo_bindings_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register the closed list contract and scoped authorization."""
    return _read_registration(
        definition,
        request_type=ModeloBindingsListRequest,
        result_type=ModeloBindingsListProjection,
        category=DisclosureCategory.PROFILE_VALUES,
    )


def build_modelo_bindings_resolve_registration(
    definition: OperationDefinition,
) -> OperationPublicDefinitionRegistrationV1:
    """Register the closed unsaved preview contract."""
    return _read_registration(
        definition,
        request_type=ModeloBindingsResolveRequest,
        result_type=ModeloBindingsResolveProjection,
        category=DisclosureCategory.TAX_VALUES,
    )


def build_modelo_requires_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register the complete checklist contract."""
    return _read_registration(
        definition,
        request_type=ModeloRequiresRequest,
        result_type=ModeloRequiresProjection,
        category=DisclosureCategory.PROFILE_VALUES,
    )


def build_modelo_readiness_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Register the canonical readiness axes and all-period rule."""
    return _read_registration(
        definition,
        request_type=ModeloReadinessOperationRequest,
        result_type=ModeloReadinessProjection,
        category=DisclosureCategory.TAX_VALUES,
    )
