"""An adapter with no enrolled key asks the runtime to resume the person's sign-in.

The adapter's own part is shown here: when it asks, how often, for which
profile, and what it does with the answer. The runtime's answer is supplied by
a connection double, because whether a sign-in is admitted is the runtime's
decision and is proven against the real runtime where that runtime lives.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import NoReturn, cast
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.frontend_client import RuntimeFrontendClient
from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.auth.auth_read_contracts import AUTH_READ_OPERATION_DEFINITION_ID
from cadrumo.application.ledger.attachment_mutation_operation import LEDGER_ATTACH_OPERATION_DEFINITION_ID
from cadrumo.application.operations.mcp_surfaces import MCP_SURFACES, McpSurface, McpSurfaceName
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.user_profile.access_contracts import (
    AccessAction,
    AccessDenialCode,
    AccessScope,
    Availability,
    ProfileAccessStatus,
)
from cadrumo.application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from cadrumo.application.user_profile.login_session import ProfileReceiptRefusedError
from cadrumo.core import logging as cadrumo_logging
from cadrumo.core.config import Settings, override_settings
from cadrumo.core.profile_session import ProfileSessionRefusalReason
from cadrumo.core.time.clock import now
from cadrumo_harness.mcp import main as mcp_main
from cadrumo_harness.mcp import runtime_adapter as mcp_runtime
from cadrumo_harness.mcp import server as mcp_server
from cadrumo_harness.mcp.protocol_contract import MCP_TOOL_CATALOGUE
from cadrumo_harness.mcp.runtime_adapter import RuntimeMcpAdapter
from cadrumo_harness.mcp.runtime_admission import (
    McpAdmission,
    require_exact_admitted_status,
    selected_profile_id,
    status_on_surface,
)
from cadrumo_harness.mcp.server import build_server
from cadrumo_harness.mcp.tests.session import connected_server_and_client_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_FULL = MCP_SURFACES[McpSurfaceName.FULL]
_READ_ONLY_LOCAL = MCP_SURFACES[McpSurfaceName.READ_ONLY_LOCAL]
_READ = AUTH_READ_OPERATION_DEFINITION_ID
_WRITE = LEDGER_ATTACH_OPERATION_DEFINITION_ID
_FOUND = {"outcome": "found", "operations": [{"definition_id": _READ}]}
_MCP = OperationFrontendProjection.MCP


class _ServingStoppedError(Exception):
    """Stop the stdio server before it reads this process's standard input."""


def _runtime_refusal(reason: ProfileSessionRefusalReason, code: str) -> ProfileReceiptRefusedError:
    """The refusal a connection raises when the runtime itself refused the presented proof."""
    refused = ProfileReceiptRefusedError(reason)
    refused.__cause__ = RuntimeFrontendRefusedError(code)
    return refused


class _ListedContract(dict[str, str]):
    """The one member a listing shows of a contract that declares no typed operator input."""

    transient_financial_operand = None


class _SignInConnection:
    """One opened MCP connection, answering a resume as its runtime was told to."""

    def __init__(self, runtime: _Runtime, profile_id: UUID) -> None:
        self.profile_id = profile_id
        self.frontend = _MCP
        self._runtime = runtime
        self._session: UUID | None = None
        self._expires_at = now() + timedelta(minutes=15)
        self._receivers: list[Callable[[], None]] = []
        self.described: list[str] = []
        self.close_count = 0

    @property
    def session_id(self) -> UUID:
        if self._session is None:
            raise RuntimeFrontendRefusedError(AccessDenialCode.AUTHENTICATION_REQUIRED.value)
        return self._session

    def resume_receipt(self) -> None:
        assert self.close_count == 0
        self._runtime.resumes += 1
        if self._runtime.refusal is not None:
            raise self._runtime.refusal
        self._session = uuid4()

    def subscribe_session_retirement(self, receive: Callable[[], None]) -> Callable[[], None]:
        self._receivers.append(receive)
        if self._session is None:
            receive()
        return lambda: None

    def retire(self) -> None:
        """Deliver the runtime's notice that this connection's session is over."""
        self._session = None
        for receive in self._receivers:
            receive()

    def status(self) -> SimpleNamespace:
        assert self.close_count == 0
        operations = {_READ, _WRITE} if self._runtime.holds_a_write else {_READ}
        return SimpleNamespace(
            status=ProfileAccessStatus(
                connected=True,
                credential_authenticated=True,
                profile_id=self.profile_id,
                session_id=self.session_id,
                session_expires_at=self._expires_at,
                # A session resumed from the sign-in carries no automation grant.
                grant_state=None,
                grant_expires_at=None,
                grant_valid=False,
                profile_bound=True,
                storage=Availability.AVAILABLE,
                automation_custody=Availability.AVAILABLE,
                published_authority=Availability.AVAILABLE,
                provider=Availability.NOT_REQUIRED,
                effective_scope=AccessScope(
                    operations=frozenset(operations),
                    actions=frozenset(AccessAction),
                    disclosures=frozenset(),
                    periods=None,
                    allow_period_independent=True,
                    allow_delegation=True,
                ),
                denial=None,
            )
        )

    def describe(self, definition_id: str, *, deadline: float) -> SimpleNamespace:
        assert self.close_count == 0 and deadline > 0
        self.described.append(definition_id)
        return SimpleNamespace(contract=_ListedContract(definition_id=definition_id))

    def subscribe_lifecycle_notices(self, receive: object) -> None:
        """The runtime sends this double no lifecycle notice."""

    def close(self) -> None:
        self.close_count += 1


class _Runtime:
    """What the runtime answers every connection the adapter opens, and a record of each."""

    def __init__(self) -> None:
        self.refusal: Exception | None = None
        self.holds_a_write = False
        self.resumes = 0
        self.opened: list[_SignInConnection] = []
        self.options: list[dict[str, object]] = []

    async def open(self, **options: object) -> RuntimeFrontendClient:
        self.options.append(options)
        connection = _SignInConnection(self, cast(UUID, options["profile_id"]))
        self.opened.append(connection)
        return cast(RuntimeFrontendClient, connection)

    @property
    def attempts(self) -> tuple[int, int]:
        """How many connections were opened and how many resumes were asked on them."""
        return len(self.opened), self.resumes


@pytest.fixture
def runtime(monkeypatch: pytest.MonkeyPatch) -> _Runtime:
    answering = _Runtime()
    monkeypatch.setattr(mcp_runtime, "open_installed_runtime_client", answering.open)
    return answering


def _adapter(profile_id: UUID | None = None, surface: McpSurface = _FULL) -> RuntimeMcpAdapter:
    return RuntimeMcpAdapter(profile_id=profile_id, client=None, surface=surface, resumes_sign_in=True)


def _selection(root: Path, profile_id: UUID | None) -> AbstractContextManager[Settings]:
    """Select ``profile_id`` for this installation, or nothing, over an empty storage root."""
    selected = None if profile_id is None else str(profile_id)
    return override_settings(cadrumo_local_storage_root=root, cadrumo_active_profile=selected)


def _no_session(profile_id: UUID | None, denial: str) -> dict[str, object]:
    return {
        "outcome": "status",
        "profile_id": None if profile_id is None else str(profile_id),
        "authenticated": False,
        "session": "none",
        "surface": "full",
        "denial": denial,
    }


def _refused(code: str) -> dict[str, object]:
    return {"outcome": "refused", "code": code}


def test_the_selected_profile_is_read_from_the_installation_and_a_named_one_only_guards_it(tmp_path: Path) -> None:
    selected, other = uuid4(), uuid4()
    with _selection(tmp_path, selected):
        assert selected_profile_id(expected=None) == selected
        assert selected_profile_id(expected=selected) == selected
        with pytest.raises(RuntimeFrontendRefusedError) as mismatched:
            selected_profile_id(expected=other)
    assert mismatched.value.reason == "profile_mismatch"
    with _selection(tmp_path, None):
        for expected in (None, other):
            with pytest.raises(RuntimeFrontendRefusedError) as unselected:
                selected_profile_id(expected=expected)
            assert unselected.value.reason == "authentication_required"


@pytest.mark.anyio
async def test_the_tool_list_and_public_queries_answer_with_no_profile_and_nobody_signed_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, runtime: _Runtime
) -> None:
    monkeypatch.setattr(mcp_runtime, "authority_query", lambda _args: {"outcome": "published", "report": {}})
    with _selection(tmp_path, None):
        adapter = _adapter()
        try:
            async with connected_server_and_client_session(build_server(adapter)) as client:
                names = [tool.name for tool in (await client.list_tools()).tools]
                published = await client.call_tool("authority", {"query": "modelos"})
                status = await client.call_tool("status", {})
                private = await client.call_tool("search", {})
        finally:
            await adapter.close()

    assert names == [name for name, _description, _schema in MCP_TOOL_CATALOGUE]
    assert published.is_error is False
    assert published.structured_content == {"outcome": "published", "report": {}}
    assert status.is_error is False
    assert status.structured_content == _no_session(None, "authentication_required")
    assert private.is_error is True
    assert private.structured_content == _refused("authentication_required")
    # With no profile selected there is no runtime connection to open, and none was opened.
    assert runtime.attempts == (0, 0)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("refusal", "code"),
    [
        pytest.param(
            _runtime_refusal(ProfileSessionRefusalReason.ABSENT, "authentication_required"),
            "authentication_required",
            id="runtime-finds-no-sign-in",
        ),
        pytest.param(
            _runtime_refusal(ProfileSessionRefusalReason.EXPIRED_IDLE, "session_expired"),
            "session_expired",
            id="runtime-finds-the-sign-in-timed-out",
        ),
        pytest.param(
            _runtime_refusal(ProfileSessionRefusalReason.CUSTODY_CHANGED, "custody_changed"),
            "custody_changed",
            id="runtime-finds-custody-changed",
        ),
        pytest.param(RuntimeFrontendRefusedError("needs_user"), "needs_user", id="runtime-needs-the-person"),
        pytest.param(RuntimeRefusalError(RuntimeRefusalCode.DRAINING), "runtime_draining", id="runtime-draining"),
        pytest.param(
            ProfileReceiptRefusedError(ProfileSessionRefusalReason.ABSENT),
            "authentication_required",
            id="no-proof-to-present",
        ),
        pytest.param(
            ProfileReceiptRefusedError(ProfileSessionRefusalReason.KEYCHAIN_ENTRY_MISSING),
            "authentication_required",
            id="proof-missing-from-the-keychain",
        ),
        pytest.param(
            ProfileReceiptRefusedError(ProfileSessionRefusalReason.KEYRING_UNAVAILABLE),
            "custody_unavailable",
            id="keychain-unavailable",
        ),
    ],
)
async def test_a_profile_call_with_nobody_signed_in_returns_the_refusal_after_one_attempt(
    tmp_path: Path, runtime: _Runtime, refusal: Exception, code: str
) -> None:
    profile_id = uuid4()
    runtime.refusal = refusal
    adapter = _adapter()
    try:
        with _selection(tmp_path, profile_id):
            assert await adapter.call("search", {}) == _refused(code)
            assert runtime.attempts == (1, 1)
            assert runtime.opened[0].close_count == 1
            assert adapter.client is None and adapter.admission is None
            assert await adapter.call("status", {}) == _no_session(profile_id, code)
            # The status call needed the profile too, so it asked once more and no more than once.
            assert runtime.attempts == (2, 2)
            assert await adapter.call("describe", {"definition_id": _READ}) == _refused(code)
            assert runtime.attempts == (3, 3)
    finally:
        await adapter.close()
    assert [connection.close_count for connection in runtime.opened] == [1, 1, 1]
    assert runtime.options == [{"profile_id": profile_id, "frontend": _MCP}] * 3


@pytest.mark.anyio
async def test_a_live_sign_in_is_resumed_once_and_then_held(tmp_path: Path, runtime: _Runtime) -> None:
    profile_id = uuid4()
    adapter = _adapter()
    try:
        with _selection(tmp_path, profile_id):
            assert await adapter.call("search", {}) == _FOUND
            status = await adapter.call("status", {})
            assert await adapter.call("search", {}) == _FOUND
            described = await adapter.call("describe", {"definition_id": _READ})
        held = runtime.opened[0]
        assert adapter.client is held and adapter.admission is McpAdmission.SIGN_IN
        assert adapter.profile_id == profile_id
        assert status == {
            "outcome": "status",
            "session": "sign_in",
            "surface": "full",
            "status": held.status().status.model_dump(mode="json"),
        }
        assert described["outcome"] == "described"
        assert runtime.attempts == (1, 1)
        assert held.close_count == 0
    finally:
        await adapter.close()
    assert held.close_count == 1


@pytest.mark.anyio
@pytest.mark.parametrize("surface", list(MCP_SURFACES.values()), ids=lambda surface: surface.name.value)
async def test_the_resume_names_the_surface_to_the_runtime_only_when_it_narrows(
    tmp_path: Path, runtime: _Runtime, surface: McpSurface
) -> None:
    profile_id = uuid4()
    runtime.holds_a_write = True
    adapter = _adapter(surface=surface)
    try:
        with _selection(tmp_path, profile_id):
            status = await adapter.call("status", {})
    finally:
        await adapter.close()

    unnamed: dict[str, object] = {"profile_id": profile_id, "frontend": _MCP}
    assert runtime.options == [unnamed | {"surface": surface.name} if surface.narrows else unnamed]
    assert status["session"] == "sign_in" and status["surface"] == surface.name.value
    scope = status["status"]["effective_scope"]
    if surface.narrows:
        # The session holds the write and the commit door; the surface leaves neither.
        assert scope["operations"] == [_READ]
        assert "commit" not in scope["actions"] and "submit" in scope["actions"]
    else:
        assert sorted(scope["operations"]) == sorted([_READ, _WRITE])
        assert "commit" in scope["actions"]


@pytest.mark.anyio
@pytest.mark.parametrize("admitted_again", [True, False], ids=["sign-in-still-live", "signed-out"])
async def test_a_retired_session_is_dropped_and_the_next_call_asks_the_runtime_once(
    tmp_path: Path, runtime: _Runtime, admitted_again: bool
) -> None:
    profile_id = uuid4()
    adapter = _adapter()
    try:
        with _selection(tmp_path, profile_id):
            assert await adapter.call("search", {}) == _FOUND
            first = runtime.opened[0]
            assert first.described == [_READ]
            first.retire()
            # Nothing happens until a call needs the profile: the notice starts no attempt of its own.
            assert runtime.attempts == (1, 1)
            assert first.close_count == 0
            if not admitted_again:
                runtime.refusal = _runtime_refusal(ProfileSessionRefusalReason.ABSENT, "authentication_required")
            after = await adapter.call("search", {})
            assert first.close_count == 1
            assert runtime.attempts == (2, 2)
            second = runtime.opened[1]
            if admitted_again:
                assert after == _FOUND
                assert adapter.client is second and adapter.admission is McpAdmission.SIGN_IN
                # The descriptions remembered for the retired session were not served to the new one.
                assert second.described == [_READ]
            else:
                assert after == _refused("authentication_required")
                assert adapter.client is None and second.close_count == 1
                assert await adapter.call("status", {}) == _no_session(profile_id, "authentication_required")
                assert runtime.attempts == (3, 3)
                # A sign-in made later is resumed by the first call that needs the profile.
                runtime.refusal = None
                assert await adapter.call("search", {}) == _FOUND
                assert runtime.attempts == (4, 4)
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_a_named_profile_is_served_by_the_sign_in_only_while_it_is_the_selected_one(
    tmp_path: Path, runtime: _Runtime
) -> None:
    named, other = uuid4(), uuid4()
    adapter = _adapter(named)
    try:
        with _selection(tmp_path, other):
            assert await adapter.call("search", {}) == _refused("profile_mismatch")
            assert await adapter.call("status", {}) == _no_session(named, "profile_mismatch")
        with _selection(tmp_path, None):
            assert await adapter.call("search", {}) == _refused("authentication_required")
        # Neither the other profile's sign-in nor the named one's was asked for.
        assert runtime.attempts == (0, 0)
        with _selection(tmp_path, named):
            assert await adapter.call("search", {}) == _FOUND
        held = runtime.opened[0]
        assert held.profile_id == named and adapter.client is held
        with _selection(tmp_path, other):
            # The person moved to another profile: the session resumed for this one is given up.
            assert await adapter.call("search", {}) == _refused("profile_mismatch")
        assert held.close_count == 1 and adapter.client is None
        assert runtime.attempts == (1, 1)
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_a_connection_that_names_no_profile_follows_the_selection(tmp_path: Path, runtime: _Runtime) -> None:
    first, second = uuid4(), uuid4()
    adapter = _adapter()
    try:
        with _selection(tmp_path, first):
            assert await adapter.call("search", {}) == _FOUND
        with _selection(tmp_path, second):
            assert await adapter.call("search", {}) == _FOUND
            assert adapter.profile_id == second
        assert [connection.profile_id for connection in runtime.opened] == [first, second]
        assert [connection.close_count for connection in runtime.opened] == [1, 0]
        assert adapter.client is runtime.opened[1]
        with _selection(tmp_path, None):
            assert await adapter.call("status", {}) == _no_session(None, "authentication_required")
        assert [connection.close_count for connection in runtime.opened] == [1, 1]
        assert runtime.resumes == 2
    finally:
        await adapter.close()


@pytest.mark.anyio
async def test_a_connection_started_for_an_enrolled_key_never_resumes_the_sign_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    profile_id = uuid4()

    async def refuse_to_open(**_options: object) -> RuntimeFrontendClient:
        raise AssertionError("an enrolled-key connection must not open a connection to resume a sign-in")

    monkeypatch.setattr(mcp_runtime, "open_installed_runtime_client", refuse_to_open)
    adapter = RuntimeMcpAdapter(profile_id=profile_id, client=None)
    try:
        with _selection(tmp_path, profile_id):
            assert await adapter.call("search", {}) == _refused("authentication_required")
            assert await adapter.call("status", {}) == _no_session(profile_id, "authentication_required")
    finally:
        await adapter.close()


def test_an_enrolled_key_connection_names_its_profile_and_a_sign_in_connection_starts_empty() -> None:
    with pytest.raises(ValueError, match="names its profile"):
        RuntimeMcpAdapter(profile_id=None, client=None)
    profile_id = uuid4()
    held = cast(RuntimeFrontendClient, SimpleNamespace(profile_id=profile_id, frontend=_MCP))
    with pytest.raises(ValueError, match="starts with no lease"):
        RuntimeMcpAdapter(profile_id=profile_id, client=held, resumes_sign_in=True)


def test_only_a_key_lease_must_show_an_automation_grant() -> None:
    profile_id = uuid4()
    connection = _SignInConnection(_Runtime(), profile_id)
    connection.resume_receipt()
    client = cast(RuntimeFrontendClient, connection)

    admitted = require_exact_admitted_status(client, profile_id=profile_id, admission=McpAdmission.SIGN_IN)

    assert admitted.session_id == connection.session_id and admitted.grant_state is None
    with pytest.raises(RuntimeFrontendRefusedError) as refused:
        require_exact_admitted_status(client, profile_id=profile_id)
    assert refused.value.reason == "grant_inactive"


def test_a_narrowing_surface_reports_only_the_scope_it_leaves() -> None:
    answering = _Runtime()
    answering.holds_a_write = True
    connection = _SignInConnection(answering, uuid4())
    connection.resume_receipt()
    whole = connection.status().status

    assert status_on_surface(whole, _FULL) is whole
    narrowed = status_on_surface(whole, _READ_ONLY_LOCAL)
    assert narrowed.effective_scope.operations == frozenset({_READ})
    assert narrowed.effective_scope.actions == whole.effective_scope.actions - {AccessAction.COMMIT}
    assert narrowed.model_copy(update={"effective_scope": whole.effective_scope}) == whole


def _run_entry_point(monkeypatch: pytest.MonkeyPatch, arguments: list[str]) -> list[dict[str, object]]:
    """Run the installed entry point on these arguments and return what it asked to be served."""
    served: list[dict[str, object]] = []
    monkeypatch.setenv("PYDANTIC_DISABLE_PLUGINS", "__all__")
    monkeypatch.delenv("CADRUMO_MCP_REQUIRED_VERSION", raising=False)
    monkeypatch.setattr(sys, "argv", ["cadrumo-mcp", *arguments])
    monkeypatch.setattr(cadrumo_logging, "configure_logging", lambda: None)
    monkeypatch.setattr(mcp_server, "serve", lambda **options: served.append(options))
    mcp_main.main()
    return served


def test_the_entry_point_names_no_profile_when_it_is_given_none(monkeypatch: pytest.MonkeyPatch) -> None:
    assert _run_entry_point(monkeypatch, []) == [{"profile_id": None, "credential_reference": None, "surface": _FULL}]


def test_the_entry_point_reads_an_empty_credential_reference_as_none(monkeypatch: pytest.MonkeyPatch) -> None:
    profile_id = uuid4()

    served = _run_entry_point(monkeypatch, ["--profile-id", str(profile_id), "--credential-reference", ""])

    assert served == [{"profile_id": profile_id, "credential_reference": None, "surface": _FULL}]


def test_the_entry_point_refuses_a_credential_reference_that_names_no_profile(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as stopped:
        _run_entry_point(monkeypatch, ["--credential-reference", str(uuid4())])

    assert stopped.value.code == 2
    assert "names the key of one profile" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("named", "keyed"),
    [(True, False), (False, False), (True, True)],
    ids=["profile-alone", "no-arguments", "profile-and-key"],
)
def test_serving_resumes_the_sign_in_exactly_when_no_credential_reference_is_given(
    monkeypatch: pytest.MonkeyPatch, named: bool, keyed: bool
) -> None:
    profile_id = uuid4() if named else None
    started: list[RuntimeMcpAdapter] = []

    async def no_key(**_options: object) -> RuntimeFrontendClient:
        raise AutomationCustodyError(AutomationCustodyCode.MISSING)

    def stop_before_stdio(adapter: RuntimeMcpAdapter) -> NoReturn:
        started.append(adapter)
        raise _ServingStoppedError

    monkeypatch.setattr(mcp_runtime, "open_installed_credential_client", no_key)
    monkeypatch.setattr(mcp_server, "build_server", stop_before_stdio)
    with pytest.raises(_ServingStoppedError):
        mcp_server.serve(profile_id=profile_id, credential_reference=uuid4() if keyed else None)

    assert len(started) == 1
    assert started[0]._resumes_sign_in is not keyed
    assert started[0].profile_id == profile_id and started[0].client is None
