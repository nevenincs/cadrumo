"""The Sede view's registration, desktop-only human access and close policy.

The executor runs against stand-in browser, stream and session ports; the
canonical session functions and the Chromium driver have their own tests.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, AbstractContextManager, asynccontextmanager, nullcontext
from datetime import datetime
from types import SimpleNamespace
from typing import cast
from uuid import uuid4

import pytest
from pydantic import BaseModel

from cadrumo_client.contracts.access_refusals import AccessAllowed, AccessDenialCode, AccessDenied
from cadrumo_client.contracts.access_vocabulary import AccessAction, Availability
from cadrumo_client.contracts.view_stream import (
    SEDE_VIEW_DEFINITION_ID,
    ViewClosedReason,
    ViewImage,
    ViewNotice,
    ViewNoticeCode,
    ViewPhase,
    ViewResize,
    ViewSinkInput,
    ViewState,
)
from cadrumo_client.contracts.view_transfer import (
    ViewDownload,
    ViewFileChooser,
    ViewTransferByteSource,
    ViewTransferCancel,
)

from ....core.auth_provider import AuthProviderKind
from ....core.config import Settings, load_settings
from ....core.operations import (
    OperationCancellation,
    OperationClosePolicy,
    OperationDeadline,
    OperationEffect,
    profile_operation_subject,
)
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...auth.certificate_secret_backend import CertificateSecretBackendFactory
from ...auth.protocols import BrowserContextPort, ViewLoginSessionFactoryPort
from ...auth.view_sessions import (
    ViewSessionBaseline,
    ViewSessionPublication,
    ViewSessionPublicationOutcome,
    ViewSessionSeed,
)
from ...operations.access_resolution import OperationAccessContext
from ...operations.capabilities import OperationOwnedResource, OperationReplayPolicy
from ...operations.models import OperationIdentity, OperationRequest, OperationTerminalReceipt
from ...operations.owner import OperationExecutorContext
from ...operations.person_acts import operation_is_persons_act
from ...operations.registry import OperationFrontendProjection, OperationRegistry
from ...user_profile.access_errors import ProfileAccessRefusedError
from .. import sede_view_operation as module
from ..sede_view_ports import SedeViewBrowser, SedeViewEnd, SedeViewOpening, SedeViewSignIn
from .borrador_100_operation_support import PROFILE_ID, policy_decision
from .operator_scope_fakes import build_inward_operator_scope_ports_for_active_route
from .unopened_live_ports import unopened_browser_session_factory

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_BASELINE = ViewSessionBaseline(provider_kind=AuthProviderKind.CERTIFICATE, storage_state_sha256="a" * 64)
_PRIVATE_URL = "https://www1.agenciatributaria.gob.es/private/page?nif=synthetic"
_PRIVATE_TITLE = "Synthetic taxpayer page title"


class _Sink:
    """The view stream as the executor sees it; nothing is relayed."""

    def __init__(self) -> None:
        self.closed: list[ViewClosedReason] = []

    @property
    def connected(self) -> bool:
        return True

    @property
    def ended(self) -> bool:
        return bool(self.closed)

    def offer_image(self, announcement: ViewImage, image: bytes) -> None:
        del announcement, image

    def send(self, document: ViewState | ViewNotice | ViewDownload | ViewFileChooser | ViewTransferCancel) -> None:
        del document

    def receive(self, *, timeout: float) -> ViewSinkInput | None:
        del timeout
        return None

    def send_download(self, transfer_id: int, source: ViewTransferByteSource) -> bool:
        del transfer_id, source
        return False

    def cancel_download(self, transfer_id: int) -> None:
        del transfer_id

    def close(self, reason: ViewClosedReason) -> None:
        self.closed.append(reason)


class _Browser:
    """A view browser that polls its stop condition ``polls`` times, then ends as the test says."""

    def __init__(self, end: SedeViewEnd, journal: list[str], *, polls: int) -> None:
        self._end = end
        self._journal = journal
        self._polls = polls
        self.phases: list[ViewPhase] = []
        self.stop_checks = 0
        self.before_browse: Callable[[], None] | None = None
        self.context_value = cast(BrowserContextPort, SimpleNamespace())
        self.sign_in: SedeViewSignIn | None = None

    @property
    def context(self) -> BrowserContextPort:
        return self.context_value

    @property
    def login_session_factory(self) -> ViewLoginSessionFactoryPort:
        raise AssertionError("a view seeded with a verified session runs no assisted login")

    async def browse(self, *, stop_requested: Callable[[], bool], sign_in: SedeViewSignIn | None) -> SedeViewEnd:
        self._journal.append("browse")
        self.sign_in = sign_in
        if self.before_browse is not None:
            self.before_browse()
        for _ in range(self._polls):
            self.stop_checks += 1
            if stop_requested():
                return SedeViewEnd.STOPPED
        return self._end

    async def announce_phase(self, phase: ViewPhase) -> None:
        self.phases.append(phase)

    async def announce_notice(self, code: ViewNoticeCode) -> None:
        raise AssertionError(f"a view whose sign-in is not checked announces no notice: {code}")

    async def close(self) -> None:
        self._journal.append("browser.close")


class _Cancellation:
    def __init__(self, *, requested: bool) -> None:
        self.requested = requested
        self.acknowledged = False

    @property
    def cancellation_requested(self) -> bool:
        return self.requested

    async def acknowledge_cancellation(self) -> None:
        assert self.requested
        self.acknowledged = True

    @asynccontextmanager
    async def irreversible_section(self) -> AsyncGenerator[None]:
        if self.requested:
            raise ValueError("cancellation already requested")
        yield


class _Events:
    def __init__(self) -> None:
        self.phases: list[str] = []
        self.effects: list[OperationEffect] = []

    async def phase(self, phase: str) -> None:
        self.phases.append(phase)

    async def effect(self, effect: OperationEffect) -> None:
        self.effects.append(effect)


class _Operands:
    def __init__(self) -> None:
        self.values: list[BaseModel] = []

    async def put(self, value: BaseModel, *, written_at: datetime) -> str:
        del written_at
        self.values.append(value)
        return "d" * 64


class _Cleanup:
    def __init__(self) -> None:
        self.owned: list[OperationOwnedResource] = []

    def own(self, resource: object, *, family: OperationOwnedResource) -> None:
        del resource
        self.owned.append(family)


class _Resources:
    def activate(self) -> AbstractContextManager[None]:
        return nullcontext()

    async def close(self) -> None:
        return None


class _Subject:
    """One view's stand-in ports and the canonical session calls it made."""

    def __init__(
        self,
        authority_operation: PinnedAuthorityOperation,
        end: SedeViewEnd,
        *,
        cancel: bool = False,
        polls: int = 1,
        publication: ViewSessionPublicationOutcome = ViewSessionPublicationOutcome.PUBLISHED,
    ) -> None:
        self.authority_operation = authority_operation
        self.journal: list[str] = []
        self.sink = _Sink()
        self.browser = _Browser(end, self.journal, polls=polls)
        self.openings: list[SedeViewOpening] = []
        self.cancellation = _Cancellation(requested=cancel)
        self.events = _Events()
        self.operands = _Operands()
        self.cleanup = _Cleanup()
        self.publication = publication
        self.opened_for: list[OperationIdentity] = []
        self.identity = OperationIdentity(
            operation_id="e" * 64,
            definition_id=SEDE_VIEW_DEFINITION_ID,
            subject_ref=profile_operation_subject(str(PROFILE_ID)),
        )

    def context(self) -> OperationExecutorContext:
        return cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=self.identity,
                authority_operation=self.authority_operation,
                cancellation=self.cancellation,
                events=self.events,
                operands=self.operands,
                cleanup=self.cleanup,
            ),
        )

    def open_stream(self, identity: OperationIdentity) -> _Sink:
        self.opened_for.append(identity)
        return self.sink

    async def open_browser(self, opening: SedeViewOpening) -> SedeViewBrowser:
        self.openings.append(opening)
        self.journal.append("browser.open")
        return self.browser

    async def open_session(
        self,
        *,
        effect_guard: Callable[[], AbstractAsyncContextManager[None]],
        on_session_write: Callable[[OperationEffect], object],
        **ports: object,
    ) -> tuple[ViewSessionSeed, Settings]:
        del on_session_write
        async with effect_guard():
            pass
        assert ports["authority_operation"] is self.authority_operation
        self.journal.append("session.open")
        seed = ViewSessionSeed(baseline=_BASELINE, storage_state={"cookies": [], "origins": []})
        return seed, load_settings()

    async def close_session(
        self,
        settings: Settings,
        *,
        baseline: ViewSessionBaseline,
        view_context: BrowserContextPort,
        effect_guard: Callable[[], AbstractAsyncContextManager[None]],
        on_session_write: Callable[[OperationEffect], object],
        **ports: object,
    ) -> ViewSessionPublication:
        del settings, ports
        assert baseline == _BASELINE and view_context is self.browser.context_value
        self.journal.append("session.publish")
        async with effect_guard():
            if self.publication is ViewSessionPublicationOutcome.PUBLISHED:
                await cast(Callable[[OperationEffect], Awaitable[None]], on_session_write)(OperationEffect.UPDATED)
        return ViewSessionPublication(outcome=self.publication, baseline=baseline)

    def provisioner(self, settings: Settings, *, baseline: ViewSessionBaseline, **ports: object) -> None:
        del settings, ports
        assert baseline == _BASELINE
        return None

    def executor(self) -> module.SedeViewExecutor:
        return module.SedeViewExecutor(
            certificate_secret_backend_factory=cast(CertificateSecretBackendFactory, object()),
            browser_session_factory=unopened_browser_session_factory,
            operator_scope_ports=build_inward_operator_scope_ports_for_active_route(),
            browser_resources_factory=_Resources,
            provider_preflight=lambda profile_id, operation: None,
            view_browser_factory=self.open_browser,
            stream_opener=self.open_stream,
        )


async def _unopened_view_browser(opening: SedeViewOpening) -> SedeViewBrowser:
    del opening
    raise AssertionError("this test must settle before the view's browser opens")


def _request(**overrides: object) -> OperationRequest[module.SedeViewRequest]:
    payload = {"profile_id": PROFILE_ID, "css_width": 1280, "css_height": 800, "scale": 1.5, **overrides}
    return OperationRequest[module.SedeViewRequest](
        definition_id=SEDE_VIEW_DEFINITION_ID,
        subject_ref=profile_operation_subject(str(PROFILE_ID)),
        payload=module.SedeViewRequest.model_validate(payload),
    )


def _registry() -> OperationRegistry:
    definition = module.build_sede_view_definition(
        certificate_secret_backend_factory=cast(CertificateSecretBackendFactory, object()),
        browser_session_factory=unopened_browser_session_factory,
        operator_scope_ports=build_inward_operator_scope_ports_for_active_route(),
        browser_resources_factory=_Resources,
        provider_preflight=lambda profile_id, operation: None,
        view_browser_factory=_unopened_view_browser,
        stream_opener=None,
    )
    return OperationRegistry(
        definitions=(definition,), public_registrations=(module.build_sede_view_registration(definition),)
    )


@pytest.fixture
def run(monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation) -> Callable[..., _Subject]:
    def build(
        end: SedeViewEnd,
        *,
        cancel: bool = False,
        polls: int = 1,
        publication: ViewSessionPublicationOutcome = ViewSessionPublicationOutcome.PUBLISHED,
    ) -> _Subject:
        subject = _Subject(authority_operation, end, cancel=cancel, polls=polls, publication=publication)
        monkeypatch.setattr(module, "require_active_bucket_id", lambda: str(PROFILE_ID))
        monkeypatch.setattr(module, "open_live_view_session", subject.open_session)
        monkeypatch.setattr(module, "publish_live_view_session", subject.close_session)
        monkeypatch.setattr(module, "view_context_provisioner", subject.provisioner)
        return subject

    return build


def test_sede_view_declares_its_own_unbounded_cancellable_policy() -> None:
    capabilities = _registry().lookup(SEDE_VIEW_DEFINITION_ID).capabilities
    assert capabilities.deadline is OperationDeadline.ABSENT
    assert capabilities.cancellation is OperationCancellation.COOPERATIVE
    assert capabilities.close_policy is OperationClosePolicy.REQUEST_CANCEL
    assert capabilities.replay is OperationReplayPolicy.NONE
    assert capabilities.owned_resources == frozenset({OperationOwnedResource.PROCESS})
    assert operation_is_persons_act(SEDE_VIEW_DEFINITION_ID, ephemeral_secret_required=False)


def test_sede_view_request_and_result_carry_no_page_content() -> None:
    assert set(module.SedeViewRequest.model_fields) == {"profile_id", "css_width", "css_height", "scale"}
    assert set(module.SedeViewReport.model_fields) == {"bucket_id", "end", "publication"}
    assert set(module.SedeViewPublicResultV1.model_fields) == {"bucket_id", "end", "publication"}
    with pytest.raises(ValueError, match="url"):
        _request(url=_PRIVATE_URL)


@pytest.mark.parametrize(
    "frontend",
    [
        OperationFrontendProjection.CLI,
        OperationFrontendProjection.TUI,
        OperationFrontendProjection.EXTERNAL_CLIENT,
        OperationFrontendProjection.INSTALLED_SERVICE,
    ],
)
def test_sede_view_access_refuses_every_frontend_but_the_desktop(
    frontend: OperationFrontendProjection, authority_operation: PinnedAuthorityOperation
) -> None:
    registry = _registry()
    request = _request()
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.START,
        frontend=frontend,
        contract=registry.lookup_public_contract(SEDE_VIEW_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    public = OperationRequest[BaseModel](
        definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
    )
    with pytest.raises(ProfileAccessRefusedError) as refused:
        module.resolve_sede_view_access(public, context)
    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED


def test_sede_view_access_admits_the_person_on_the_desktop_and_refuses_an_automation(
    authority_operation: PinnedAuthorityOperation,
) -> None:
    registry = _registry()
    request = _request()
    context = OperationAccessContext(
        profile_id=PROFILE_ID,
        destination_id=uuid4(),
        action=AccessAction.START,
        frontend=OperationFrontendProjection.DESKTOP,
        contract=registry.lookup_public_contract(SEDE_VIEW_DEFINITION_ID),
        published_authority=Availability.AVAILABLE,
        authority_operation=authority_operation,
    )
    public = OperationRequest[BaseModel](
        definition_id=request.definition_id, subject_ref=request.subject_ref, payload=request.payload
    )
    resolved = module.resolve_sede_view_access(public, context)
    assert resolved.policy.requires_human
    human = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures, human=True)
    automation = policy_decision(resolved, registry, disclosures=resolved.policy.disclosures)
    assert isinstance(human, AccessAllowed)
    assert isinstance(automation, AccessDenied)


@pytest.mark.asyncio
@pytest.mark.parametrize("end", [SedeViewEnd.CLOSED, SedeViewEnd.PAGE_LOST])
async def test_sede_view_graceful_close_publishes_before_the_browser_closes(
    run: Callable[..., _Subject], end: SedeViewEnd
) -> None:
    subject = run(end)
    digest = await subject.executor().execute(_request(), subject.context())
    assert digest == "d" * 64
    assert subject.journal == ["session.open", "browser.open", "browse", "session.publish", "browser.close"]
    assert subject.events.phases[-2:] == [module.SEDE_VIEW_CLOSING_PHASE, module.SEDE_VIEW_RESULT_PHASE]
    assert subject.browser.phases == [ViewPhase.CLOSING]
    assert subject.events.effects[-1] is OperationEffect.UPDATED
    assert subject.sink.closed == [ViewClosedReason.OPERATION_ENDED]
    assert subject.opened_for == [subject.identity]
    assert subject.cleanup.owned == [OperationOwnedResource.PROCESS]
    report = cast(module.SedeViewReport, subject.operands.values[-1])
    assert report.end is end and report.publication is ViewSessionPublicationOutcome.PUBLISHED
    opening = subject.openings[0]
    assert (opening.viewport.css_width, opening.viewport.css_height, opening.viewport.scale) == (1280, 800, 1.5)


@pytest.mark.asyncio
async def test_sede_view_unknown_publication_settles_with_an_unknown_effect(run: Callable[..., _Subject]) -> None:
    subject = run(SedeViewEnd.CLOSED, publication=ViewSessionPublicationOutcome.UNKNOWN)
    await subject.executor().execute(_request(), subject.context())
    assert subject.events.effects[-1] is OperationEffect.UNKNOWN
    assert cast(module.SedeViewReport, subject.operands.values[-1]).publication is ViewSessionPublicationOutcome.UNKNOWN


@pytest.mark.asyncio
async def test_sede_view_supervisor_cancel_stops_without_publishing(run: Callable[..., _Subject]) -> None:
    subject = run(SedeViewEnd.CLOSED, polls=3)
    executor = subject.executor()

    def cancel() -> None:
        subject.cancellation.requested = True

    subject.browser.before_browse = cancel
    assert await executor.execute(_request(), subject.context()) is None
    assert subject.cancellation.acknowledged
    assert "session.publish" not in subject.journal and subject.journal[-1] == "browser.close"
    assert module.SEDE_VIEW_CLOSING_PHASE not in subject.events.phases
    assert subject.sink.closed == [ViewClosedReason.CANCELLED]
    assert not subject.operands.values


@pytest.mark.asyncio
@pytest.mark.parametrize("end", [SedeViewEnd.STREAM_ENDED, SedeViewEnd.PROTOCOL_VIOLATION])
async def test_sede_view_session_retirement_and_violations_end_without_publishing(
    run: Callable[..., _Subject], end: SedeViewEnd
) -> None:
    subject = run(end)
    await subject.executor().execute(_request(), subject.context())
    assert "session.publish" not in subject.journal
    report = cast(module.SedeViewReport, subject.operands.values[-1])
    assert report.end is end and report.publication is None
    assert subject.events.effects[-1] is OperationEffect.NONE


@pytest.mark.asyncio
async def test_sede_view_without_input_keeps_browsing_with_no_expiry(run: Callable[..., _Subject]) -> None:
    subject = run(SedeViewEnd.CLOSED, polls=10_000)
    await subject.executor().execute(_request(), subject.context())
    assert subject.browser.stop_checks == 10_000
    assert cast(module.SedeViewReport, subject.operands.values[-1]).end is SedeViewEnd.CLOSED


@pytest.mark.asyncio
async def test_sede_view_journal_and_result_hold_no_page_content(
    run: Callable[..., _Subject], authority_operation: PinnedAuthorityOperation
) -> None:
    subject = run(SedeViewEnd.CLOSED)
    await subject.executor().execute(_request(), subject.context())
    journal = " ".join([*subject.events.phases, *(effect.value for effect in subject.events.effects)])
    stored = subject.operands.values[-1].model_dump_json()
    for text in (journal, stored, _request().model_dump_json()):
        assert "https" not in text and _PRIVATE_TITLE not in text and "cookies" not in text
    assert authority_operation is subject.authority_operation


@pytest.mark.asyncio
async def test_sede_view_refuses_without_the_host_stream(
    monkeypatch: pytest.MonkeyPatch, authority_operation: PinnedAuthorityOperation
) -> None:
    subject = _Subject(authority_operation, SedeViewEnd.CLOSED)
    monkeypatch.setattr(module, "require_active_bucket_id", lambda: str(PROFILE_ID))
    definition = _registry().lookup(SEDE_VIEW_DEFINITION_ID)
    executor = definition.executor_factory.create()
    assert isinstance(executor, module.SedeViewExecutor)
    with pytest.raises(ProfileAccessRefusedError) as refused:
        await executor.execute(_request(), subject.context())
    assert refused.value.reason is AccessDenialCode.FRONTEND_DENIED


def test_sede_view_result_projection_refuses_a_publication_after_an_ungraceful_end() -> None:
    report = module.SedeViewReport(
        bucket_id=str(PROFILE_ID), end=SedeViewEnd.STOPPED, publication=ViewSessionPublicationOutcome.PUBLISHED
    )
    registration = module.build_sede_view_registration(_registry().lookup(SEDE_VIEW_DEFINITION_ID))
    projector = registration.result_projector
    assert projector is not None
    with pytest.raises(ValueError, match="graceful close"):
        projector(report, cast(OperationTerminalReceipt, object()))


def test_sede_view_opening_keeps_the_seed_out_of_its_repr() -> None:
    opening = SedeViewOpening(
        settings=load_settings(),
        sink=_Sink(),
        viewport=ViewResize(css_width=10, css_height=10, scale=1.0),
        storage_state={"cookies": [{"value": "synthetic-cookie"}]},
        provisioner=None,
    )
    assert "synthetic-cookie" not in repr(opening)
