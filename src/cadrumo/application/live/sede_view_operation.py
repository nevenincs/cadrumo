"""The registered Sede view: the person browses the AEAT Sede in a panel of the desktop.

The view resumes or acquires the profile's AEAT session through the canonical
path, seeds an unrestricted browser context from custody and relays it to the
desktop window over the view stream. It has no idle or absolute bound: it runs
while the window holds it open and the person's session is held.

How the view ends decides whether it publishes. The window's ``view.close``,
or its view connection dropping without one, and the last page closing, end
it gracefully: the view captures the context's session and publishes it
through the canonical custody path under the effect guard, then settles as
succeeded with the publication's outcome. A supervisor cancel, and the host
ending the stream because the session was retired or locked or the runtime
stops, end it without publishing.

The journal records the request's panel size and the result's end and
publication outcome only. No URL, title, image, input or file byte reaches
the journal, the result or a log.
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cadrumo_client.contracts.access_refusals import AccessDenialCode
from cadrumo_client.contracts.access_vocabulary import OperationAccessPolicy
from cadrumo_client.contracts.view_stream import (
    SEDE_VIEW_DEFINITION_ID,
    VIEW_MAX_CSS_EXTENT,
    VIEW_MAX_SCALE,
    VIEW_MIN_SCALE,
    ViewClosedReason,
    ViewPhase,
    ViewResize,
    ViewStreamSink,
)

from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
from ...core.identity.bucket import BucketId
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort
from ..auth.sessions import ViewSessionBaseline, ViewSessionPublicationOutcome, view_context_provisioner
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
from ..operations.models import (
    CredentialFreeOperationRequest,
    OperationRequest,
    OperationTerminalReceipt,
    require_succeeded_receipt_references,
    require_terminal_receipt_match_any_effect,
)
from ..operations.operation_definition import OperationDefinition
from ..operations.owner import OperationExecutorContext
from ..operations.registry import OperationFrontendProjection, OperationPublicDefinitionRegistrationV1
from ..user_profile.access_errors import ProfileAccessRefusedError
from .filed_history_operation import FiledHistoryBrowserResourcesFactory, FiledHistoryProviderPreflight
from .live_operation_execution import (
    fenced_persistence_guard,
    own_provider_browser,
    publish_live_read_report,
    require_exact_profile_worker,
    require_live_executor_identity,
)
from .live_operation_registration import build_live_operation_definition, resolve_whole_profile_capture_access
from .sede_view_ports import (
    PUBLISHING_ENDS,
    SedeViewBrowser,
    SedeViewBrowserFactory,
    SedeViewEnd,
    SedeViewOpening,
    SedeViewStreamOpener,
)
from .session import LiveSessionWriteReceipt, close_live_view_session, open_live_view_session

_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
SEDE_VIEW_ACQUIRE_PHASE = "sede-view.acquire"
SEDE_VIEW_BROWSE_PHASE = "sede-view.browse"
SEDE_VIEW_CLOSING_PHASE = "sede-view.closing"
SEDE_VIEW_RESULT_PHASE = "sede-view.result"
_PHASES = (SEDE_VIEW_ACQUIRE_PHASE, SEDE_VIEW_BROWSE_PHASE, SEDE_VIEW_CLOSING_PHASE, SEDE_VIEW_RESULT_PHASE)

#: The view's own policy: it runs until the person closes it, so it declares no execution deadline, and the
#: supervisor's cancel stops it cooperatively. One view per profile; its browser is a supervisor-owned process.
SEDE_VIEW_CAPABILITIES = OperationCapabilities(
    durability=OperationDurability.RECORDED,
    cancellation=OperationCancellation.COOPERATIVE,
    deadline=OperationDeadline.ABSENT,
    replay=OperationReplayPolicy.NONE,
    baseline=OperationBaselinePolicy.NONE,
    request_storage=OperationRequestStoragePolicy.CREDENTIAL_FREE_JOURNAL,
    sensitive_input=OperationSensitiveInputPolicy.NONE,
    conflict_scope=OperationConflictScope.DEFINITION_SUBJECT,
    owned_resources=frozenset({OperationOwnedResource.PROCESS}),
    permitted_effects=frozenset({OperationEffect.NONE, OperationEffect.UPDATED, OperationEffect.UNKNOWN}),
    close_policy=OperationClosePolicy.REQUEST_CANCEL,
)

_CLOSE_REASONS = {
    SedeViewEnd.CLOSED: ViewClosedReason.OPERATION_ENDED,
    SedeViewEnd.PAGE_LOST: ViewClosedReason.OPERATION_ENDED,
    SedeViewEnd.STREAM_ENDED: ViewClosedReason.OPERATION_ENDED,
    SedeViewEnd.STOPPED: ViewClosedReason.CANCELLED,
    SedeViewEnd.PROTOCOL_VIOLATION: ViewClosedReason.PROTOCOL_VIOLATION,
}


class SedeViewRequest(CredentialFreeOperationRequest):
    """Open the Sede view for the exact profile, at the panel's starting size."""

    model_config = _PUBLIC_CONFIG
    profile_id: UUID
    css_width: int = Field(ge=1, le=VIEW_MAX_CSS_EXTENT)
    css_height: int = Field(ge=1, le=VIEW_MAX_CSS_EXTENT)
    scale: float = Field(ge=VIEW_MIN_SCALE, le=VIEW_MAX_SCALE, allow_inf_nan=False)


class SedeViewReport(BaseModel):
    """How the view ended and what its close-time publication did; never a URL, title or byte."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    end: SedeViewEnd
    publication: ViewSessionPublicationOutcome | None


class SedeViewPublicResultV1(BaseModel):
    """The view's end and publication outcome, as the desktop shows them."""

    model_config = _PUBLIC_CONFIG
    bucket_id: BucketId
    end: SedeViewEnd
    publication: ViewSessionPublicationOutcome | None


def _unavailable_stream(identity: object) -> ViewStreamSink:
    del identity
    raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)


class SedeViewExecutor:
    """Run one Sede view from acquisition to its close."""

    def __init__(
        self,
        *,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
        browser_resources_factory: FiledHistoryBrowserResourcesFactory,
        provider_preflight: FiledHistoryProviderPreflight,
        view_browser_factory: SedeViewBrowserFactory,
        stream_opener: SedeViewStreamOpener,
    ) -> None:
        """Hold the canonical session ports, the view's browser and the host's stream opener."""
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._browser_session_factory = browser_session_factory
        self._operator_scope_ports = operator_scope_ports
        self._browser_resources_factory = browser_resources_factory
        self._provider_preflight = provider_preflight
        self._view_browser_factory = view_browser_factory
        self._stream_opener = stream_opener

    async def execute(
        self, request: OperationRequest[SedeViewRequest], context: OperationExecutorContext
    ) -> str | None:
        """Browse until the view ends; publish its session on a graceful close and report how it ended."""
        require_live_executor_identity(request, context, definition_id=SEDE_VIEW_DEFINITION_ID)
        payload = request.payload
        bucket_id = require_exact_profile_worker(
            payload.profile_id, request.subject_ref, active_bucket_id=require_active_bucket_id()
        )
        self._provider_preflight(payload.profile_id, context.authority_operation)
        resources = await own_provider_browser(
            context, self._browser_resources_factory, acquire_phase=SEDE_VIEW_ACQUIRE_PHASE
        )
        sink = self._stream_opener(context.identity)
        reason = ViewClosedReason.FAILED
        try:
            with resources.activate():
                end, publication, receipt = await self._run(payload, sink, context)
            reason = _CLOSE_REASONS[end]
        finally:
            await asyncio.to_thread(sink.close, reason)
        if publication is None and context.cancellation.cancellation_requested:
            await context.cancellation.acknowledge_cancellation()
            return None
        # A cancel that arrives once the session is published is too late to undo it: the view settles.
        effect = (
            OperationEffect.UNKNOWN
            if publication is ViewSessionPublicationOutcome.UNKNOWN
            else receipt.combine(OperationEffect.NONE)
        )
        report = SedeViewReport(bucket_id=bucket_id, end=end, publication=publication)
        return await publish_live_read_report(
            context, report, result_phase=SEDE_VIEW_RESULT_PHASE, effect=effect, task_name="cadrumo-sede-view-result"
        )

    async def _run(
        self, payload: SedeViewRequest, sink: ViewStreamSink, context: OperationExecutorContext
    ) -> tuple[SedeViewEnd, ViewSessionPublicationOutcome | None, LiveSessionWriteReceipt]:
        receipt = LiveSessionWriteReceipt(context.events.effect)
        seed, settings = await open_live_view_session(
            certificate_secret_backend_factory=self._certificate_secret_backend_factory,
            browser_session_factory=self._browser_session_factory,
            operator_scope_ports=self._operator_scope_ports,
            authority_operation=context.authority_operation,
            effect_guard=fenced_persistence_guard(context, persist_phase=SEDE_VIEW_ACQUIRE_PHASE),
            on_session_write=receipt,
        )
        provisioner = view_context_provisioner(
            settings,
            baseline=seed.baseline,
            certificate_secret_backend_factory=self._certificate_secret_backend_factory,
            browser_session_factory=self._browser_session_factory,
            operator_scope_ports=self._operator_scope_ports,
        )
        browser = await self._view_browser_factory(
            SedeViewOpening(
                settings=settings,
                sink=sink,
                viewport=ViewResize(css_width=payload.css_width, css_height=payload.css_height, scale=payload.scale),
                storage_state=seed.storage_state,
                provisioner=provisioner,
            )
        )
        try:
            await context.events.phase(SEDE_VIEW_BROWSE_PHASE)
            end = await browser.browse(stop_requested=lambda: context.cancellation.cancellation_requested)
            if end not in PUBLISHING_ENDS or context.cancellation.cancellation_requested:
                return end, None, receipt
            publication = await self._publish(browser, settings, seed.baseline, context, receipt)
            return end, publication, receipt
        finally:
            await browser.close()

    async def _publish(
        self,
        browser: SedeViewBrowser,
        settings: Settings,
        baseline: ViewSessionBaseline,
        context: OperationExecutorContext,
        receipt: LiveSessionWriteReceipt,
    ) -> ViewSessionPublicationOutcome:
        await context.events.phase(SEDE_VIEW_CLOSING_PHASE)
        await browser.announce_phase(ViewPhase.CLOSING)
        publication = await close_live_view_session(
            settings,
            baseline=baseline,
            view_context=browser.context,
            certificate_secret_backend_factory=self._certificate_secret_backend_factory,
            browser_session_factory=self._browser_session_factory,
            operator_scope_ports=self._operator_scope_ports,
            authority_operation=context.authority_operation,
            effect_guard=fenced_persistence_guard(context, persist_phase=SEDE_VIEW_CLOSING_PHASE),
            on_session_write=receipt,
        )
        return publication.outcome


def build_sede_view_definition(
    *,
    certificate_secret_backend_factory: CertificateSecretBackendFactory,
    browser_session_factory: BrowserSessionFactoryPort,
    operator_scope_ports: OperatorScopePorts,
    browser_resources_factory: FiledHistoryBrowserResourcesFactory,
    provider_preflight: FiledHistoryProviderPreflight,
    view_browser_factory: SedeViewBrowserFactory,
    stream_opener: SedeViewStreamOpener | None,
) -> OperationDefinition:
    """Declare the Sede view; without a host stream opener every run is refused before it acquires."""
    opener: SedeViewStreamOpener = stream_opener or _unavailable_stream

    def build() -> SedeViewExecutor:
        return SedeViewExecutor(
            certificate_secret_backend_factory=certificate_secret_backend_factory,
            browser_session_factory=browser_session_factory,
            operator_scope_ports=operator_scope_ports,
            browser_resources_factory=browser_resources_factory,
            provider_preflight=provider_preflight,
            view_browser_factory=view_browser_factory,
            stream_opener=opener,
        )

    return build_live_operation_definition(
        definition_id=SEDE_VIEW_DEFINITION_ID,
        request_type=SedeViewRequest,
        result_type=SedeViewReport,
        executor_type=SedeViewExecutor,
        build=build,
        phase_codes=_PHASES,
        capabilities=SEDE_VIEW_CAPABILITIES,
    )


def resolve_sede_view_access(
    request: OperationRequest[BaseModel], context: OperationAccessContext, /
) -> ResolvedOperationAccess:
    """Admit the view only to the person on the desktop, for the request's own profile."""
    if context.frontend is not OperationFrontendProjection.DESKTOP:
        raise ProfileAccessRefusedError(AccessDenialCode.FRONTEND_DENIED)
    resolved = resolve_whole_profile_capture_access(
        request, context, definition_id=SEDE_VIEW_DEFINITION_ID, payload_type=SedeViewRequest
    )
    # ``dict(model)`` keeps the nested permission models hashable inside their frozen sets.
    policy = OperationAccessPolicy.model_validate({**dict(resolved.policy), "requires_human": True})
    return ResolvedOperationAccess(request=resolved.request, policy=policy)


_RECEIPT_CONTRADICTION = "Sede view result contradicts its terminal receipt"


def _project(result: BaseModel, receipt: OperationTerminalReceipt, /) -> BaseModel:
    report = SedeViewReport.model_validate(result, strict=True)
    if report.publication is not None and report.end not in PUBLISHING_ENDS:
        raise ValueError("a Sede view that ended without a graceful close cannot have published")
    effects = (
        frozenset({OperationEffect.UNKNOWN})
        if report.publication is ViewSessionPublicationOutcome.UNKNOWN
        else frozenset({OperationEffect.NONE, OperationEffect.UPDATED})
    )
    require_terminal_receipt_match_any_effect(
        receipt,
        definition_id=SEDE_VIEW_DEFINITION_ID,
        subject_ref=profile_operation_subject(report.bucket_id),
        condition=OperationTerminalCondition.SUCCEEDED,
        effects=effects,
        message=_RECEIPT_CONTRADICTION,
    )
    require_succeeded_receipt_references(receipt, message=_RECEIPT_CONTRADICTION)
    return SedeViewPublicResultV1(bucket_id=report.bucket_id, end=report.end, publication=report.publication)


def build_sede_view_registration(definition: OperationDefinition) -> OperationPublicDefinitionRegistrationV1:
    """Bind the view's public result and its desktop-only, human-only access."""
    return OperationPublicDefinitionRegistrationV1.compose_request_result(
        definition=definition,
        public_result_type=SedeViewPublicResultV1,
        result_projector=_project,
        access_resolver=resolve_sede_view_access,
    )


__all__ = [
    "SEDE_VIEW_ACQUIRE_PHASE",
    "SEDE_VIEW_BROWSE_PHASE",
    "SEDE_VIEW_CAPABILITIES",
    "SEDE_VIEW_CLOSING_PHASE",
    "SEDE_VIEW_RESULT_PHASE",
    "SedeViewExecutor",
    "SedeViewPublicResultV1",
    "SedeViewReport",
    "SedeViewRequest",
    "build_sede_view_definition",
    "build_sede_view_registration",
    "resolve_sede_view_access",
]
