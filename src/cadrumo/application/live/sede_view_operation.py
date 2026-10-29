"""The registered Sede view: the person browses the AEAT Sede in a panel of the desktop.

The view resumes or acquires the profile's AEAT session through the canonical
path, seeds an unrestricted browser context from custody and relays it to the
desktop window over the view stream. It has no idle or absolute bound: it runs
while the window holds it open and the person's session is held.

The person signs in inside the view. With no valid stored session the view
opens signed out; the configured certificate or Cl@ve Movil login then runs
inside it as assistance the person watches and may interrupt, and a login the
person makes by hand, with any provider, is detected after each AEAT page load
through the provider's own verification. Either publishes at once through the
canonical custody path, so every sync reuses it.

How the view ends decides whether it publishes again. The window's ``view.close``,
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
from collections.abc import Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager
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
    ViewNoticeCode,
    ViewPhase,
    ViewResize,
    ViewStreamSink,
)

from ...core.bucket_pointer import require_active_bucket_id
from ...core.config import Settings
from ...core.errors.hierarchy import InternalInvariantError
from ...core.identity.bucket import BucketId
from ...core.logging import get_logger
from ...core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationDurability,
    OperationEffect,
    OperationTerminalCondition,
    profile_operation_subject,
)
from ...core.type_guards import is_object_list, is_object_mapping
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ..auth.certificate_secret_backend import CertificateSecretBackendFactory
from ..auth.operator_scope_ports import OperatorScopePorts
from ..auth.protocols import BrowserSessionFactoryPort, session_store
from ..auth.view_sessions import (
    VIEW_ASSISTED_PROVIDERS,
    ViewSessionBaseline,
    ViewSessionPublication,
    ViewSessionPublicationOutcome,
    ViewSessionSeed,
    view_context_provisioner,
)
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
from .session import (
    LiveSessionWriteReceipt,
    SessionWriteReporter,
    assist_live_view_login,
    open_live_view_session,
    publish_live_view_session,
)

logger = get_logger(__name__)

_PUBLIC_CONFIG = ConfigDict(strict=True, frozen=True, extra="forbid", validate_default=True)
SEDE_VIEW_ACQUIRE_PHASE = "sede-view.acquire"
SEDE_VIEW_BROWSE_PHASE = "sede-view.browse"
SEDE_VIEW_SIGN_IN_PHASE = "sede-view.sign-in"
SEDE_VIEW_CLOSING_PHASE = "sede-view.closing"
SEDE_VIEW_RESULT_PHASE = "sede-view.result"
_PHASES = (
    SEDE_VIEW_ACQUIRE_PHASE,
    SEDE_VIEW_BROWSE_PHASE,
    SEDE_VIEW_SIGN_IN_PHASE,
    SEDE_VIEW_CLOSING_PHASE,
    SEDE_VIEW_RESULT_PHASE,
)
_SIGN_IN_OPERATION = "live-sede-view-sign-in"
#: Sign-in checks whose cookie jar is not checked again until it changes.
_REFUSED_SIGN_INS = frozenset(
    {ViewSessionPublicationOutcome.VERIFICATION_FAILED, ViewSessionPublicationOutcome.IDENTITY_MISMATCH}
)

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


type EffectGuardFor = Callable[[str], Callable[[], AbstractAsyncContextManager[None]]]
"""The operation's effect guard for a publication announced in one phase."""


def _cookie_jar_digest(storage_state: Mapping[str, object]) -> str:
    """Digest the part of a capture that a provider's verification can answer differently for.

    AEAT recognises a session by the cookies the browser sends: their domain,
    path, name and value. An expiry a response slides forward, and the pages'
    local storage, change the capture on almost every load without changing
    what a verification would find, so they are left out.
    """
    raw = storage_state.get("cookies")
    cookies: list[object] = raw if is_object_list(raw) else []
    jar = sorted(
        (str(cookie.get("domain")), str(cookie.get("path")), str(cookie.get("name")), str(cookie.get("value")))
        for cookie in cookies
        if is_object_mapping(cookie)
    )
    return session_store().storage_state_sha256(
        {
            "cookies": [
                {"domain": domain, "path": path, "name": name, "value": value} for domain, path, name, value in jar
            ],
            "origins": [],
        }
    )


class SedeViewSessionSignIn:
    """The view's session, from its seed to its last publication.

    It implements :class:`~cadrumo.application.live.sede_view_ports.SedeViewSignIn`:
    a signed-out view runs the configured certificate or Cl@ve Movil login as
    assistance the person may interrupt, and checks after each AEAT page load
    whether the person has signed in by hand, through the provider's own
    verification. A sign-in publishes at once. Publications never overlap, and
    each one's baseline is the digest the view was seeded from or last
    published, so the close-time publication follows the latest sign-in.

    A page load is checked only when a verification could answer differently:
    the capture's cookie jar must differ from every jar a verification already
    refused. At most one check runs at a time, and loads that arrive meanwhile
    fold into one more check after it. Each verification runs in the
    provider's own browser, never the person's page, and none of this holds
    back the person's browsing. After a sign-in publishes, page loads are no
    longer checked: the close-time publication covers what follows. A sign-in
    publication interrupted between its ``UNKNOWN`` and ``UPDATED`` reports
    sets :attr:`unknown`, which ends the view.
    """

    def __init__(
        self,
        *,
        settings: Settings,
        seed: ViewSessionSeed,
        browser: SedeViewBrowser,
        certificate_secret_backend_factory: CertificateSecretBackendFactory,
        browser_session_factory: BrowserSessionFactoryPort,
        operator_scope_ports: OperatorScopePorts,
        authority_operation: PinnedAuthorityOperation,
        effect_guard_for: EffectGuardFor,
        on_session_write: SessionWriteReporter,
        resume_browsing: Callable[[], Awaitable[None]],
        stop_requested: Callable[[], bool],
    ) -> None:
        """Hold the seed's baseline and the ports every view publication goes through."""
        self._settings = settings
        self._baseline = seed.baseline
        self._signed_in = seed.signed_in
        self._browser = browser
        self._certificate_secret_backend_factory = certificate_secret_backend_factory
        self._browser_session_factory = browser_session_factory
        self._operator_scope_ports = operator_scope_ports
        self._authority_operation = authority_operation
        self._effect_guard_for = effect_guard_for
        self._on_session_write = on_session_write
        self._resume_browsing = resume_browsing
        self._stop_requested = stop_requested
        self._publishing = asyncio.Lock()
        self._interruptible = False
        self._refused: set[str] = set()
        self._checking = False
        self._loads = 0
        self._unknown = False

    @property
    def baseline(self) -> ViewSessionBaseline:
        """The digest the next publication requires custody to still hold."""
        return self._baseline

    @property
    def signed_in(self) -> bool:
        """Whether the view holds a session the provider verified, seeded or published."""
        return self._signed_in

    @property
    def unknown(self) -> bool:
        """Whether a sign-in publication was interrupted with its write unknown."""
        return self._unknown

    @property
    def interruptible(self) -> bool:
        """Whether the assisted login runs and has not yet been verified."""
        return self._interruptible

    async def assist(self) -> None:
        """Run the configured provider's login in a signed-out view and publish it at once.

        Only the certificate and Cl@ve Movil logins run in the view; Cadrumo
        never drives a Cl@ve Permanente login. A login that fails, or that the
        person interrupts, leaves the view to the person.
        """
        if self._signed_in or self._baseline.provider_kind not in VIEW_ASSISTED_PROVIDERS:
            return
        self._interruptible = True
        await self._browser.announce_phase(ViewPhase.ACQUIRING)
        try:
            async with self._publishing:
                publication = await assist_live_view_login(
                    self._settings,
                    baseline=self._baseline,
                    login_session_factory=self._browser.login_session_factory,
                    certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                    operator_scope_ports=self._operator_scope_ports,
                    authority_operation=self._authority_operation,
                    effect_guard=self._effect_guard_for(SEDE_VIEW_SIGN_IN_PHASE),
                    on_session_write=self._on_session_write,
                    on_login_verified=self._login_verified,
                )
                await self._settle(publication)
        except Exception as exc:
            # The provider's own failure: the person can still sign in by hand.
            logger.info("aeat view assisted login ended exc_type=%s", type(exc).__name__)
        finally:
            self._interruptible = False
            await self._browser.announce_phase(ViewPhase.BROWSING)

    async def page_loaded(self) -> None:
        """Publish the view's session if the person has signed in since the last check.

        A load that arrives while a check runs returns at once and folds into
        one more check after the running one.
        """
        if self._watch_ended():
            return
        self._loads += 1
        if self._checking:
            return
        self._checking = True
        try:
            while True:
                checked = self._loads
                await self._check_sign_in()
                if self._loads == checked or self._watch_ended():
                    return
        finally:
            self._checking = False

    async def _check_sign_in(self) -> None:
        async with self._publishing:
            if self._watch_ended():
                return
            captured = await self._browser.context.storage_state()
            if session_store().storage_state_sha256(captured) == self._baseline.storage_state_sha256:
                return
            jar = _cookie_jar_digest(captured)
            if jar in self._refused:
                return
            publication = await self._publish(SEDE_VIEW_SIGN_IN_PHASE, operation=_SIGN_IN_OPERATION)
            if publication.outcome in _REFUSED_SIGN_INS:
                self._refused.add(jar)
            if publication.outcome is ViewSessionPublicationOutcome.IDENTITY_MISMATCH:
                await self._browser.announce_notice(ViewNoticeCode.IDENTITY_MISMATCH)
            await self._settle(publication)

    async def close(self) -> ViewSessionPublicationOutcome:
        """Publish the closing view's session after any sign-in still publishing."""
        async with self._publishing:
            publication = await self._publish(SEDE_VIEW_CLOSING_PHASE, operation="live-sede-view-close")
            self._baseline = publication.baseline
            return publication.outcome

    def _watch_ended(self) -> bool:
        return self._signed_in or self._unknown or self._stop_requested()

    def _login_verified(self) -> None:
        self._interruptible = False

    async def _publish(self, phase: str, *, operation: str) -> ViewSessionPublication:
        return await publish_live_view_session(
            self._settings,
            baseline=self._baseline,
            view_context=self._browser.context,
            certificate_secret_backend_factory=self._certificate_secret_backend_factory,
            browser_session_factory=self._browser_session_factory,
            operator_scope_ports=self._operator_scope_ports,
            authority_operation=self._authority_operation,
            effect_guard=self._effect_guard_for(phase),
            on_session_write=self._on_session_write,
            operation=operation,
        )

    async def _settle(self, publication: ViewSessionPublication) -> None:
        if publication.outcome is ViewSessionPublicationOutcome.PUBLISHED:
            self._baseline = publication.baseline
            self._signed_in = True
            await self._resume_browsing()
        elif publication.outcome is ViewSessionPublicationOutcome.UNKNOWN:
            self._unknown = True


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

        def stop_requested() -> bool:
            return context.cancellation.cancellation_requested

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
            sign_in = SedeViewSessionSignIn(
                settings=settings,
                seed=seed,
                browser=browser,
                certificate_secret_backend_factory=self._certificate_secret_backend_factory,
                browser_session_factory=self._browser_session_factory,
                operator_scope_ports=self._operator_scope_ports,
                authority_operation=context.authority_operation,
                effect_guard_for=lambda phase: fenced_persistence_guard(context, persist_phase=phase),
                on_session_write=receipt,
                resume_browsing=lambda: context.events.phase(SEDE_VIEW_BROWSE_PHASE),
                stop_requested=stop_requested,
            )
            await context.events.phase(SEDE_VIEW_BROWSE_PHASE)
            end = await browser.browse(stop_requested=lambda: stop_requested() or sign_in.unknown, sign_in=sign_in)
            if sign_in.unknown:
                raise InternalInvariantError("the Sede view's sign-in publication was interrupted")
            if end not in PUBLISHING_ENDS or stop_requested():
                return end, None, receipt
            await context.events.phase(SEDE_VIEW_CLOSING_PHASE)
            await browser.announce_phase(ViewPhase.CLOSING)
            return end, await sign_in.close(), receipt
        finally:
            await browser.close()


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
    "SEDE_VIEW_SIGN_IN_PHASE",
    "EffectGuardFor",
    "SedeViewExecutor",
    "SedeViewPublicResultV1",
    "SedeViewReport",
    "SedeViewRequest",
    "SedeViewSessionSignIn",
    "build_sede_view_definition",
    "build_sede_view_registration",
    "resolve_sede_view_access",
]
