"""A register view the person picks reaches only their own signed-in page surfaces on that profile."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event, RLock
from typing import cast
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo_client.contracts.access_refusals import AccessDenialCode, AccessDenied, ProfileAccessStatus
from cadrumo_client.contracts.access_vocabulary import AccessScope, Availability, EffectiveScopeSummary
from cadrumo_client.contracts.contracts import Peer
from cadrumo_client.contracts.login import LoginEvidence
from cadrumo_client.contracts.presentation import PresentationDelivered, PresentationRequest
from cadrumo_client.contracts.profile_access import Request
from cadrumo_client.contracts.session_events import PresentationRequested
from cadrumo_client.contracts.transport import ConnectionContext

from ..profile_connections import RuntimeProfileConnections
from ..profile_host import ProfileConnection, RuntimeProfileHost

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TRANSACTION = "0123456789abcdef" * 4


@dataclass(frozen=True)
class _Login:
    login_id: str


@dataclass
class _Authority:
    """Answers a status read for one session, as the profile's session authority would."""

    session_id: UUID
    denial: AccessDenialCode | None = None

    def status(self, *, connection_id: UUID, session_id: UUID, **_axes: object) -> ProfileAccessStatus:
        return ProfileAccessStatus(
            connected=True,
            credential_authenticated=True,
            profile_id=None,
            session_id=session_id,
            session_expires_at=datetime.now(UTC) + timedelta(minutes=5),
            grant_state=None,
            grant_expires_at=None,
            grant_valid=False,
            profile_bound=True,
            storage=Availability.AVAILABLE,
            automation_custody=Availability.AVAILABLE,
            published_authority=Availability.NOT_REQUIRED,
            provider=Availability.NOT_REQUIRED,
            effective_scope=EffectiveScopeSummary.summarize(
                AccessScope(
                    operations=frozenset(),
                    actions=frozenset(),
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=False,
                )
            ),
            denial=self.denial if session_id == self.session_id else AccessDenialCode.SESSION_INACTIVE,
        )


@dataclass
class _Host:
    authority: _Authority
    guard: RLock = field(default_factory=RLock)


def _runtime(tmp_path: Path) -> RuntimeProfileConnections:
    return RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=uuid4(),
        stop=Event(),
        service_descriptors=(),
    )


def _join(
    profiles: RuntimeProfileConnections,
    profile_id: UUID,
    frontend: OperationFrontendProjection,
    *,
    login: str = "person",
    signed_in: bool = True,
    presents_pages: bool | None = None,
) -> ConnectionContext:
    if presents_pages is None:
        presents_pages = frontend is OperationFrontendProjection.TUI
    context = ConnectionContext(
        uuid4(),
        profiles.boot,
        Peer(os_owner_id="synthetic-owner", process_id=1),
        presentation=presents_pages,
    )
    profiles.connect_events(context)
    profiles._connections[context.connection_id] = ProfileConnection(
        context=context,
        login=cast(LoginEvidence, _Login(login)),
        client_id=uuid4(),
        profile_id=profile_id,
        frontend=frontend,
        session_id=uuid4() if signed_in else None,
    )
    return context


def _ask(
    profiles: RuntimeProfileConnections,
    asker: ConnectionContext,
    destination: str = "ledger",
    params: dict[str, str] | None = None,
) -> object:
    connection = profiles._connections[asker.connection_id]
    assert connection.session_id is not None
    profiles._profiles[connection.profile_id] = cast(RuntimeProfileHost, _Host(_Authority(connection.session_id)))
    request = PresentationRequest.model_validate(
        {
            "request_id": uuid4(),
            "profile_id": connection.profile_id,
            "session_id": connection.session_id,
            "destination": destination,
            "params": params or {},
        }
    )
    return profiles._present(asker, request)


def test_the_page_reaches_only_the_same_persons_signed_in_page_surfaces_on_that_profile(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    desktop = _join(profiles, profile_id, OperationFrontendProjection.DESKTOP)
    tui = _join(profiles, profile_id, OperationFrontendProjection.TUI)
    others = (
        _join(profiles, profile_id, OperationFrontendProjection.TUI, login="someone-else"),
        _join(profiles, uuid4(), OperationFrontendProjection.TUI),
        _join(profiles, profile_id, OperationFrontendProjection.TUI, signed_in=False),
        _join(profiles, profile_id, OperationFrontendProjection.TUI, presents_pages=False),
        _join(profiles, profile_id, OperationFrontendProjection.CLI),
    )

    delivered = _ask(profiles, desktop, "profile/aeat-access")

    assert isinstance(delivered, PresentationDelivered)
    assert (delivered.destination, delivered.delivered, delivered.connection_id) == (
        "profile/aeat-access",
        1,
        desktop.connection_id,
    )
    tui_session = profiles._connections[tui.connection_id].session_id
    assert tui_session is not None
    assert profiles.take_events(tui) == (
        PresentationRequested(
            runtime_boot_id=profiles.boot,
            connection_id=tui.connection_id,
            profile_id=profile_id,
            session_id=tui_session,
            destination="profile/aeat-access",
        ),
    )
    assert profiles.take_events(desktop) == ()
    for other in others:
        assert profiles.take_events(other) == ()


def test_no_signed_in_tui_is_reported_as_nothing_delivered(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    desktop = _join(profiles, profile_id, OperationFrontendProjection.DESKTOP)
    waiting = _join(profiles, profile_id, OperationFrontendProjection.TUI, signed_in=False)

    delivered = _ask(profiles, desktop)

    assert isinstance(delivered, PresentationDelivered)
    assert delivered.delivered == 0
    assert profiles.take_events(waiting) == ()


@pytest.mark.parametrize(
    "frontend", [OperationFrontendProjection.EXTERNAL_CLIENT, OperationFrontendProjection.INSTALLED_SERVICE]
)
def test_a_delegated_client_may_not_choose_a_page(tmp_path: Path, frontend: OperationFrontendProjection) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    asker = _join(profiles, profile_id, frontend)
    tui = _join(profiles, profile_id, OperationFrontendProjection.TUI)

    assert _ask(profiles, asker) == AccessDenied(code=AccessDenialCode.PERSON_ACT_REQUIRED)
    assert profiles.take_events(tui) == ()


@pytest.mark.parametrize("frontend", [OperationFrontendProjection.CLI, OperationFrontendProjection.TUI])
def test_any_persons_frontend_may_choose_a_page(tmp_path: Path, frontend: OperationFrontendProjection) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    asker = _join(profiles, profile_id, frontend, presents_pages=False)
    tui = _join(profiles, profile_id, OperationFrontendProjection.TUI)

    delivered = _ask(profiles, asker, "reference")
    assert isinstance(delivered, PresentationDelivered)
    assert delivered.delivered == 1
    events = profiles.take_events(tui)
    assert [event.destination for event in events if isinstance(event, PresentationRequested)] == ["reference"]
    assert profiles.take_events(asker) == ()


def test_a_denied_or_foreign_session_sends_nothing(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    desktop = _join(profiles, profile_id, OperationFrontendProjection.DESKTOP)
    tui = _join(profiles, profile_id, OperationFrontendProjection.TUI)
    connection = profiles._connections[desktop.connection_id]
    assert connection.session_id is not None

    profiles._profiles[profile_id] = cast(
        RuntimeProfileHost, _Host(_Authority(connection.session_id, denial=AccessDenialCode.SESSION_EXPIRED))
    )
    expired = PresentationRequest(
        request_id=uuid4(), profile_id=profile_id, session_id=connection.session_id, destination="home"
    )
    assert profiles._present(desktop, expired) == AccessDenied(code=AccessDenialCode.SESSION_EXPIRED)

    foreign = expired.model_copy(update={"session_id": uuid4()})
    assert profiles._present(desktop, foreign) == AccessDenied(code=AccessDenialCode.CONNECTION_MISMATCH)
    other_profile = expired.model_copy(update={"profile_id": uuid4()})
    assert profiles._present(desktop, other_profile) == AccessDenied(code=AccessDenialCode.PROFILE_MISMATCH)
    assert profiles.take_events(tui) == ()


def test_a_selected_record_is_relayed_with_the_view(tmp_path: Path) -> None:
    profiles = _runtime(tmp_path)
    profile_id = uuid4()
    desktop = _join(profiles, profile_id, OperationFrontendProjection.DESKTOP)
    tui = _join(profiles, profile_id, OperationFrontendProjection.TUI)

    delivered = _ask(profiles, desktop, "ledger", {"select": _TRANSACTION})

    assert isinstance(delivered, PresentationDelivered)
    assert delivered.delivered == 1
    events = [event for event in profiles.take_events(tui) if isinstance(event, PresentationRequested)]
    assert [(event.destination, event.params) for event in events] == [("ledger", {"select": _TRANSACTION})]


@pytest.mark.parametrize(
    ("destination", "params"),
    [
        # An element only the window implements.
        ("ledger/invoices", {}),
        ("calendar", {}),
        # An id the register does not declare, and the retired closed-vocabulary spellings.
        ("nowhere", {}),
        ("aeat_auth", {}),
        ("workbench.ledger", {}),
        # A parameter no element declares, and one this element does not take.
        ("ledger", {"focus": _TRANSACTION}),
        ("home", {"select": _TRANSACTION}),
        # A value that is not of the parameter's kind.
        ("ledger", {"select": "A" * 64}),
        ("ledger", {"select": "0042"}),
    ],
)
def test_the_runtime_refuses_a_view_no_tui_implements_or_a_parameter_the_element_refuses(
    destination: str, params: dict[str, str]
) -> None:
    # The runtime's one request door decodes every frame before any handler runs.
    frame = {
        "action": "present_destination",
        "request_id": str(uuid4()),
        "profile_id": str(uuid4()),
        "session_id": str(uuid4()),
        "destination": destination,
        "params": params,
    }
    with pytest.raises(ValidationError, match="TUI view request"):
        Request.model_validate_json(json.dumps(frame))
    admitted = Request.model_validate_json(json.dumps(frame | {"destination": "ledger", "params": {}}))
    assert isinstance(admitted.root, PresentationRequest)
