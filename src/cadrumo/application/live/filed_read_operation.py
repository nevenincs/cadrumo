"""Registered exact-profile Sede register listing and discovery reads."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, NonNegativeInt, model_validator

from ...core.bucket_pointer import require_active_bucket_id
from ...core.errors.hierarchy import CadrumoError
from ...core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ...core.filing_year import FilingYear
from ...core.operations import OperationEffect
from ...core.register_scoping_signal import RegisterScopingSignal
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.deadlines.models import TaxpayerProfile
from ..operations.access_resolution import OperationAccessContext, ResolvedOperationAccess
from ..operations.capabilities import (
    RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
    OperationOwnedResource,
)
from ..operations.models import OperationRequest, OperationTerminalReceipt
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext, retain_failed_operation_resources
from ..operations.registry import OperationPublicDefinitionRegistrationV1
from ..user_profile.access_contracts import AccessDenialCode
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_data import FiledDataListingRow
from .filed_data_capture import list_filed_data, list_filed_data_bulk
from .filed_data_ports import FiledDataCapturePort
from .filed_history_discovery import FiledHistoryDiscoveryReport, discover_filed_history
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .live_operation_execution import (
    own_provider_browser,
    publish_live_read_report,
    require_exact_profile_worker,
    track_capture_session,
)
from .live_operation_registration import build_live_operation_definition, resolve_whole_profile_capture_access
from .remote_state_models import FiledDataCaptureFailureRow

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
        require_exact_profile_worker(
            request.payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        payload = request.payload
        await context.events.phase(_LIST_PHASES[0])
        self._provider_preflight(payload.profile_id, context.authority_operation)
        composition = self._composition_factory(operation=context.authority_operation)
        resources = await own_provider_browser(context, self._browser_resources_factory, acquire_phase=_LIST_PHASES[1])
        session_receipt = await track_capture_session(context, may_write=False)
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
        return await publish_live_read_report(
            context,
            report,
            result_phase=_LIST_PHASES[2],
            effect=session_receipt.combine(OperationEffect.NONE),
            task_name="filed-list-result",
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
        require_exact_profile_worker(
            request.payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        await context.events.phase(_DISCOVER_PHASES[0])
        self._provider_preflight(request.payload.profile_id, context.authority_operation)
        profile = self._profile_resolver(context.authority_operation)
        composition = self._composition_factory(operation=context.authority_operation)
        resources = await own_provider_browser(
            context, self._browser_resources_factory, acquire_phase=_DISCOVER_PHASES[1]
        )
        session_receipt = await track_capture_session(context, may_write=False)
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
        return await publish_live_read_report(
            context,
            report,
            result_phase=_DISCOVER_PHASES[2],
            effect=session_receipt.combine(OperationEffect.NONE),
            task_name="filed-discover-result",
        )


def build_filed_list_definition(
    composition_factory: FiledReadCompositionFactory,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
) -> OperationDefinition:
    """Declare read-only, recorded Sede register listing."""

    def build() -> FiledListExecutor:
        return FiledListExecutor(composition_factory, browser_resources_factory, provider_preflight)

    return build_live_operation_definition(
        definition_id=FILED_LIST_DEFINITION_ID,
        request_type=FiledListRequest,
        result_type=FiledListOperationReport,
        executor_type=FiledListExecutor,
        build=build,
        phase_codes=_LIST_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
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

    return build_live_operation_definition(
        definition_id=FILED_DISCOVER_DEFINITION_ID,
        request_type=FiledDiscoverRequest,
        result_type=FiledHistoryDiscoveryReport,
        executor_type=FiledDiscoverExecutor,
        build=build,
        phase_codes=_DISCOVER_PHASES,
        capabilities=RECORDED_IDEMPOTENT_SECURE_INPUT_PROCESS_UPDATE_CAPABILITIES,
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


def resolve_filed_list_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile authority for the register row range, plus COMMIT for a provider-session save."""
    return resolve_whole_profile_capture_access(
        request, context, definition_id=FILED_LIST_DEFINITION_ID, payload_type=FiledListRequest
    )


def resolve_filed_discover_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Require whole-profile authority for expectation disclosure, plus COMMIT for a provider-session save."""
    return resolve_whole_profile_capture_access(
        request, context, definition_id=FILED_DISCOVER_DEFINITION_ID, payload_type=FiledDiscoverRequest
    )


def build_filed_list_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind closed list schemas to whole-profile disclosure access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=FiledListPublicResultV1,
        result_projector=_project_list,
        access_resolver=resolve_filed_list_access,
    )


def build_filed_discover_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind closed discovery schemas to whole-profile disclosure access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=FiledDiscoverPublicResultV1,
        result_projector=_project_discover,
        access_resolver=resolve_filed_discover_access,
    )
