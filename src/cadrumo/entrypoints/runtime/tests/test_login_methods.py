"""Which login methods and options the runtime accepts from each frontend.

The connection service and its rules are the real ones. A login the rules
refuse is refused before any credential is read, any native login is captured
or any profile is opened, so these checks need no profile custody and no
worker.
"""

from __future__ import annotations

from itertools import product
from pathlib import Path
from threading import Event
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.tests.test_enrollment_framing import MemoryChannel
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.login import RuntimeLoginEvidence
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileLogin
from cadrumo.application.runtime.transport import RuntimeConnectionContext
from cadrumo.application.user_profile.access_contracts import AccessScope

from ..profile_connections import RuntimeProfileConnections

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI = OperationFrontendProjection.CLI
_TUI = OperationFrontendProjection.TUI
_MCP = OperationFrontendProjection.MCP
_METHODS = ("password", "receipt", "api_key")

type _Login = tuple[OperationFrontendProjection, str, bool]
"""A frontend, the method it sends, and whether it asks for the sign-in to be stored."""

_ADMITTED: tuple[_Login, ...] = (
    (_CLI, "password", False),
    (_CLI, "password", True),
    (_TUI, "password", False),
    (_TUI, "password", True),
    (_CLI, "receipt", False),
    (_TUI, "receipt", False),
    # An MCP connection resumes a sign-in the person already stored, and does nothing else as the person.
    (_MCP, "receipt", False),
    (_CLI, "api_key", False),
    (_TUI, "api_key", False),
    (_MCP, "api_key", False),
)
_REFUSED: tuple[_Login, ...] = (
    # No password travels through MCP, and MCP never asks for a sign-in to be stored.
    (_MCP, "password", False),
    (_MCP, "password", True),
    (_MCP, "receipt", True),
    # Only a password login can store a sign-in.
    (_CLI, "receipt", True),
    (_TUI, "receipt", True),
    (_CLI, "api_key", True),
    (_TUI, "api_key", True),
    (_MCP, "api_key", True),
)
_NARROWING_SCOPE = AccessScope(
    operations=frozenset(),
    actions=frozenset(),
    disclosures=frozenset(),
    periods=None,
    allow_period_independent=True,
    allow_delegation=False,
)


def _refuse_capture(_channel: object) -> RuntimeLoginEvidence:
    raise AssertionError("a refused login must not capture the native login")


def _connections(tmp_path: Path, boot: UUID) -> RuntimeProfileConnections:
    return RuntimeProfileConnections(
        storage_root=tmp_path,
        storage_identity="a" * 64,
        runtime_boot_id=boot,
        stop=Event(),
        capture_login=_refuse_capture,
    )


def _login(
    frontend: OperationFrontendProjection, method: str, persist_receipt: bool, *, scope: AccessScope | None = None
) -> RuntimeProfileLogin:
    return RuntimeProfileLogin.model_validate(
        {
            "request_id": uuid4(),
            "profile_id": uuid4(),
            "method": method,
            "frontend": frontend,
            "persist_receipt": persist_receipt,
            "scope": scope,
        }
    )


def _refusal(tmp_path: Path, request: RuntimeProfileLogin) -> RuntimeAccessRefusal:
    """Put one login to the connection service and return its refusal, having read and opened nothing."""
    boot = uuid4()
    channel = MemoryChannel()
    context = RuntimeConnectionContext(uuid4(), boot, channel.peer)
    connections = _connections(tmp_path, boot)

    reply = connections.handle(context, channel, request)

    assert isinstance(reply, RuntimeAccessRefusal), reply
    assert not connections._connections
    assert not channel.writes
    return reply


def test_every_frontend_method_and_storing_option_has_a_recorded_answer() -> None:
    """The two lists below cover every login a frontend can write, and no login twice."""
    every_login = set(product(OperationFrontendProjection, _METHODS, (False, True)))

    assert set(_ADMITTED) | set(_REFUSED) == every_login
    assert not set(_ADMITTED) & set(_REFUSED)
    assert len(_ADMITTED) + len(_REFUSED) == len(every_login)


@pytest.mark.parametrize(("frontend", "method", "persist_receipt"), _ADMITTED)
def test_a_login_its_frontend_may_send_passes_the_login_rules(
    frontend: OperationFrontendProjection, method: str, persist_receipt: bool
) -> None:
    # Passing the rules admits nothing: the credential is still read and proven afterwards.
    RuntimeProfileConnections._validate_login_request(_login(frontend, method, persist_receipt))


@pytest.mark.parametrize(("frontend", "method", "persist_receipt"), _REFUSED)
def test_a_login_its_frontend_may_not_send_is_refused_before_any_credential_is_read(
    tmp_path: Path, frontend: OperationFrontendProjection, method: str, persist_receipt: bool
) -> None:
    request = _login(frontend, method, persist_receipt)

    with pytest.raises(RuntimeRefusalError) as refused:
        RuntimeProfileConnections._validate_login_request(request)

    assert refused.value.reason is RuntimeRefusalCode.INVALID_FRAME
    assert _refusal(tmp_path, request).code is RuntimeRefusalCode.INVALID_FRAME


@pytest.mark.parametrize("frontend", list(OperationFrontendProjection))
@pytest.mark.parametrize("method", ["password", "receipt"])
def test_a_sign_in_takes_no_narrowing_scope_from_any_frontend(
    tmp_path: Path, frontend: OperationFrontendProjection, method: str
) -> None:
    request = _login(frontend, method, False, scope=_NARROWING_SCOPE)

    assert _refusal(tmp_path, request).code is RuntimeRefusalCode.INVALID_FRAME


@pytest.mark.parametrize("frontend", list(OperationFrontendProjection))
def test_a_key_login_may_ask_for_a_narrower_scope_from_any_frontend(frontend: OperationFrontendProjection) -> None:
    RuntimeProfileConnections._validate_login_request(_login(frontend, "api_key", False, scope=_NARROWING_SCOPE))
