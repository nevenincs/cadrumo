"""Registered exact-profile Sede register listing and discovery reads."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ...core.async_cleanup import await_cancellation_complete
from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CadrumoError
from ...core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ...core.filing_year import FilingYear
from ...core.identity.profile import canonical_profile_bucket_id
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    profile_operation_subject,
)
from ...core.register_scoping_signal import RegisterScopingSignal
from ...core.time.clock import now
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.models import TaxpayerProfile
from ..ledger.read_access import resolve_ledger_read_access
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    OperationBaselinePolicy,
    OperationCapabilities,
    OperationConflictScope,
    OperationOwnedResource,
    OperationReplayPolicy,
    OperationRequestStoragePolicy,
    OperationSensitiveInputPolicy,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition, OperationExecutorFactory
from ..operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import (
    OperationFrontendProjection,
    OperationPublicDefinitionRegistrationV1,
    OperationReconciliationPolicy,
    OperationSchemaBindingV1,
)
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_data import FiledDataListingRow
from .filed_data_capture import (
    FiledHistoryDiscoveryReport,
    discover_filed_history,
    list_filed_data,
    list_filed_data_bulk,
)
from .filed_data_ports import FiledDataCapturePort
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .remote_state_models import FiledDataCaptureFailureRow
from .session import LiveSessionWriteReceipt

FILED_LIST_DEFINITION_ID = "live.filed-list"
FILED_DISCOVER_DEFINITION_ID = "live.filed-discover"
_LIST_PHASES = ("filed-list.preflight", "filed-list.read", "filed-list.result")
_DISCOVER_PHASES = ("filed-discover.preflight", "filed-discover.read", "filed-discover.result")
_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)


class FiledListRequest(BaseModel):
    """One exact profile and inclusive filing-year range to list."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    modelo: str | None = Field(default=None, min_length=1, max_length=8)
    year_from: FilingYear
    year_to: FilingYear

    @model_validator(mode="after")
    def _valid_range(self) -> FiledListRequest:
        if self.year_from > self.year_to:
            raise ValueError("filed listing year_from exceeds year_to")
        return self


class FiledDiscoverRequest(BaseModel):
    """Discover the Sede register and the bound profile's expected filing grid."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID


class FiledListOperationReport(BaseModel):
    """Private supervisor result containing the canonical typed register rows."""

    model_config = _PUBLIC_CONFIG
    modelo_filter: str | None
    year_from: FilingYear
    year_to: FilingYear
    row_count: NonNegativeInt
    failed_count: NonNegativeInt
    rows: tuple[FiledDataListingRow, ...]
    failures: tuple[FiledDataCaptureFailureRow, ...]

    @model_validator(mode="after")
    def _counts_match(self) -> FiledListOperationReport:
        if self.row_count != len(self.rows) or self.failed_count != len(self.failures):
            raise ValueError("filed listing counts do not match their rows")
        return self


class FiledListingRowPublicV1(BaseModel):
    """Safe scalar form of one declaration-register row."""

    model_config = _PUBLIC_CONFIG
    modelo: str
    year: FilingYear
    period: str
    expediente_id: str
    status: str
    presented_at: datetime
    has_submitted_file: bool
    has_declaration_copy: bool
    has_justificante: bool


class FiledListingFailurePublicV1(BaseModel):
    """Safe scalar form of one failed register pair."""

    model_config = _PUBLIC_CONFIG
    modelo: str
    year: FilingYear
    period: str | None
    expediente_id: str | None
    error_type: str
    message: str


class FiledListPublicResultV1(BaseModel):
    """Complete account of a register list without private domain objects."""

    model_config = _PUBLIC_CONFIG
    modelo_filter: str | None
    year_from: FilingYear
    year_to: FilingYear
    row_count: NonNegativeInt
    failed_count: NonNegativeInt
    rows: tuple[FiledListingRowPublicV1, ...]
    failures: tuple[FiledListingFailurePublicV1, ...]

    @model_validator(mode="after")
    def _counts_match(self) -> FiledListPublicResultV1:
        if self.row_count != len(self.rows) or self.failed_count != len(self.failures):
            raise ValueError("public filed listing counts do not match their rows")
        return self


class FiledDiscoverPairPublicV1(BaseModel):
    """One discovered filing pair and its canonical nomination signals."""

    model_config = _PUBLIC_CONFIG
    modelo: str
    ejercicio: FilingYear
    signals: tuple[FiledHistoryDiscoverySignal, ...] = Field(min_length=1)


class FiledDiscoverPublicResultV1(BaseModel):
    """Public discovery facts from one exact-profile register read."""

    model_config = _PUBLIC_CONFIG
    pairs: tuple[FiledDiscoverPairPublicV1, ...]
    profile_year_span_determined: bool
    register_options_read: bool
    scoping_signal: RegisterScopingSignal


class FiledReadComposition(Protocol):
    """Only the shared composed capability needed by register reads."""

    @property
    def filed_data_port(self) -> FiledDataCapturePort:
        """Return the authenticated Sede register port."""
        ...


class FiledReadCompositionFactory(Protocol):
    """Compose filed-register readers under the operation's held authority pin."""

    def __call__(self, *, operation: PinnedAuthorityOperation) -> FiledReadComposition:
        """Return the authenticated Sede reader bundle for this operation."""
        ...


FiledReadProfileResolver = Callable[[PinnedAuthorityOperation], TaxpayerProfile | None]


def _resolve_active_profile(operation: PinnedAuthorityOperation) -> TaxpayerProfile | None:
    """Use the pinned profile schema; preserve discovery before profile setup."""
    from ..wizard.status import load_active_taxpayer_profile
    from ..workflow.persistence import workflow_state_repository

    try:
        return load_active_taxpayer_profile(workflow_state_repository().load(), schema=operation.profile_schema())
    except CadrumoError:
        return None


def _require_exact_profile(profile_id: UUID, subject_ref: str) -> None:
    """Refuse a payload or subject that differs from this immutable worker."""
    canonical_id = canonical_profile_bucket_id(profile_id)
    if require_active_bucket_id() != canonical_id or subject_ref != profile_operation_subject(canonical_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)


def _list_row_in_scope(row: FiledDataListingRow, payload: FiledListRequest) -> bool:
    return (
        payload.year_from <= row.year <= payload.year_to
        and row.period.filing_year == row.year
        and (payload.modelo is None or row.modelo == payload.modelo)
    )


def _failure_in_scope(row: FiledDataCaptureFailureRow, payload: FiledListRequest) -> bool:
    return (
        payload.year_from <= row.year <= payload.year_to
        and (row.period is None or row.period.filing_year == row.year)
        and (payload.modelo is None or row.modelo == payload.modelo)
    )


class FiledListExecutor:
    """Run a read-only register query under the bound profile's worker."""

    def __init__(
        self,
        composition_factory: FiledReadCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
    ) -> None:
        """Bind the entrypoint-owned provider and process capabilities."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight

    async def execute(self, request: OperationRequest[FiledListRequest], context: OperationExecutorContext) -> str:
        """List remote rows and publish a scope-checked encrypted report."""
        _require_exact_profile(request.payload.profile_id, request.subject_ref)
        payload = request.payload
        await context.events.phase(_LIST_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory(operation=context.authority_operation)
        resources = self._browser_resources_factory()
        context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_LIST_PHASES[1])
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with (
            retain_failed_operation_resources(context.cleanup, family=OperationOwnedResource.PROCESS),
            resources.activate(),
        ):
            if payload.modelo is None:
                bulk = await list_filed_data_bulk(
                    filed_data_port=composition.filed_data_port,
                    year_from=payload.year_from,
                    year_to=payload.year_to,
                    operation=context.authority_operation,
                    effect_guard=context.cancellation.irreversible_section,
                    on_session_write=session_receipt,
                )
                rows, failures = bulk.rows, bulk.failures
            else:
                single = await list_filed_data(
                    filed_data_port=composition.filed_data_port,
                    modelo=payload.modelo,
                    year_from=payload.year_from,
                    year_to=payload.year_to,
                    authority_operation=context.authority_operation,
                    effect_guard=context.cancellation.irreversible_section,
                    on_session_write=session_receipt,
                )
                rows, failures = single.rows, ()
        if any(not _list_row_in_scope(row, payload) for row in rows) or any(
            not _failure_in_scope(row, payload) for row in failures
        ):
            raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
        report = FiledListOperationReport(
            modelo_filter=payload.modelo,
            year_from=payload.year_from,
            year_to=payload.year_to,
            row_count=len(rows),
            failed_count=len(failures),
            rows=rows,
            failures=failures,
        )
        await context.events.phase(_LIST_PHASES[2])
        await context.events.effect(session_receipt.combine(OperationEffect.NONE))
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="filed-list-result"
        )


class FiledDiscoverExecutor:
    """Read offered register controls and the profile's declared expectation."""

    def __init__(
        self,
        composition_factory: FiledReadCompositionFactory,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
        profile_resolver: FiledReadProfileResolver,
    ) -> None:
        """Bind composed provider, profile projection and cleanup capabilities."""
        self._composition_factory = composition_factory
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight
        self._profile_resolver = profile_resolver

    async def execute(self, request: OperationRequest[FiledDiscoverRequest], context: OperationExecutorContext) -> str:
        """Discover both signals and publish their canonical union report."""
        _require_exact_profile(request.payload.profile_id, request.subject_ref)
        await context.events.phase(_DISCOVER_PHASES[0])
        self._provider_preflight(request.payload.profile_id, context.authority_operation)
        profile = self._profile_resolver(context.authority_operation)
        composition = self._composition_factory(operation=context.authority_operation)
        resources = self._browser_resources_factory()
        context.cleanup.own(resources, family=OperationOwnedResource.PROCESS)
        await context.events.phase(_DISCOVER_PHASES[1])
        session_receipt = LiveSessionWriteReceipt(context.events.effect)
        with (
            retain_failed_operation_resources(context.cleanup, family=OperationOwnedResource.PROCESS),
            resources.activate(),
        ):
            report = await discover_filed_history(
                filed_data_port=composition.filed_data_port,
                profile=profile,
                operation=context.authority_operation,
                effect_guard=context.cancellation.irreversible_section,
                on_session_write=session_receipt,
            )
        await context.events.phase(_DISCOVER_PHASES[2])
        await context.events.effect(session_receipt.combine(OperationEffect.NONE))
        return await await_cancellation_complete(
            context.operands.put(report, written_at=now()), task_name="filed-discover-result"
        )


def build_filed_list_definition(
    composition_factory: FiledReadCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare read-only, recorded Sede register listing."""

    def build() -> FiledListExecutor:
        return FiledListExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return OperationDefinition(
        definition_id=FILED_LIST_DEFINITION_ID,
        request_type=FiledListRequest,
        result_type=FiledListOperationReport,
        executor_factory=OperationExecutorFactory(
            request_type=FiledListRequest, executor_type=FiledListExecutor, build=build
        ),
        phase_codes=_LIST_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_read_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def build_filed_discover_definition(
    composition_factory: FiledReadCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
    profile_resolver: FiledReadProfileResolver = _resolve_active_profile,
) -> OperationDefinition:
    """Declare read-only, recorded register/profile grid discovery."""

    def build() -> FiledDiscoverExecutor:
        return FiledDiscoverExecutor(
            composition_factory, browser_resources_factory, provider_preflight, profile_resolver
        )

    return OperationDefinition(
        definition_id=FILED_DISCOVER_DEFINITION_ID,
        request_type=FiledDiscoverRequest,
        result_type=FiledHistoryDiscoveryReport,
        executor_factory=OperationExecutorFactory(
            request_type=FiledDiscoverRequest, executor_type=FiledDiscoverExecutor, build=build
        ),
        phase_codes=_DISCOVER_PHASES,
        interaction_kinds=frozenset(),
        capabilities=_read_capabilities(),
        reconciliation_policy=OperationReconciliationPolicy.INTERRUPT,
        permitted_frontends=frozenset(
            {OperationFrontendProjection.CLI, OperationFrontendProjection.TUI, OperationFrontendProjection.MCP}
        ),
    )


def _read_capabilities() -> OperationCapabilities:
    return OperationCapabilities(
        durability=OperationDurability.RECORDED,
        cancellation=OperationCancellation.UNSUPPORTED,
        deadline=OperationDeadline.ABSENT,
        replay=OperationReplayPolicy.IDEMPOTENT_SUBMIT,
        baseline=OperationBaselinePolicy.NONE,
        request_storage=OperationRequestStoragePolicy.SECURE_REFERENCE,
        sensitive_input=OperationSensitiveInputPolicy.SECURE_REFERENCE,
        conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
        owned_resources=frozenset({OperationOwnedResource.PROCESS}),
        permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
        close_policy=OperationClosePolicy.DETACH_ALLOWED,
    )


def _project_list(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    del receipt
    report = FiledListOperationReport.model_validate(result, strict=True)
    return FiledListPublicResultV1(
        modelo_filter=report.modelo_filter,
        year_from=report.year_from,
        year_to=report.year_to,
        row_count=report.row_count,
        failed_count=report.failed_count,
        rows=tuple(
            FiledListingRowPublicV1(
                modelo=row.modelo,
                year=row.year,
                period=row.period.registry_token,
                expediente_id=str(row.expediente_id),
                status=row.status,
                presented_at=row.presented_at,
                has_submitted_file=row.has_submitted_file,
                has_declaration_copy=row.has_declaration_copy,
                has_justificante=row.has_justificante,
            )
            for row in report.rows
        ),
        failures=tuple(
            FiledListingFailurePublicV1(
                modelo=row.modelo,
                year=row.year,
                period=row.period.registry_token if row.period is not None else None,
                expediente_id=str(row.expediente_id) if row.expediente_id is not None else None,
                error_type=row.error_type,
                message=row.message,
            )
            for row in report.failures
        ),
    )


def _project_discover(result: BaseModel, receipt: OperationTerminalReceipt) -> BaseModel:
    del receipt
    report = FiledHistoryDiscoveryReport.model_validate(result, strict=True)
    return FiledDiscoverPublicResultV1(
        pairs=tuple(
            FiledDiscoverPairPublicV1(modelo=pair.modelo, ejercicio=pair.ejercicio, signals=pair.signals)
            for pair in report.pairs
        ),
        profile_year_span_determined=report.profile_year_span_determined,
        register_options_read=report.register_options_read,
        scoping_signal=report.scoping_signal,
    )


def _resolve_read_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, definition_id: str
) -> ResolvedOperationAccess:
    expected_type = FiledListRequest if definition_id == FILED_LIST_DEFINITION_ID else FiledDiscoverRequest
    if request.definition_id != definition_id or not isinstance(request.payload, expected_type):
        raise ProfileAccessRefusedError(AccessDenialCode.OPERATION_UNAVAILABLE)
    return resolve_ledger_read_access(request, context, profile_id=request.payload.profile_id, periods=frozenset())


def resolve_filed_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile authority for the register row range."""
    return _resolve_read_access(request, context, FILED_LIST_DEFINITION_ID)


def resolve_filed_discover_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile authority for profile expectation disclosure."""
    return _resolve_read_access(request, context, FILED_DISCOVER_DEFINITION_ID)


def build_filed_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind closed list schemas to whole-profile disclosure access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=FiledListRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result", schema_version=1, model_type=FiledListPublicResultV1
        ),
        result_projector=_project_list,
        access_resolver=resolve_filed_list_access,
    )


def build_filed_discover_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind closed discovery schemas to whole-profile disclosure access."""
    return OperationPublicDefinitionRegistrationV1.compose(
        definition=definition,
        request_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".request", schema_version=1, model_type=FiledDiscoverRequest
        ),
        result_schema=OperationSchemaBindingV1.bind(
            schema_id=definition.definition_id + ".result",
            schema_version=1,
            model_type=FiledDiscoverPublicResultV1,
        ),
        result_projector=_project_discover,
        access_resolver=resolve_filed_discover_access,
    )
