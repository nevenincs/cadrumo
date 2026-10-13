"""The runtime hosts a person's agent, bound to the session that asked, against a real runtime and profile.

The profile, its encrypted custody, the stored sign-in, the profile worker that
resolves the provider credential, the native transport and the agent's
contained process tree are all real. The agent is a stand-in that records what
it received and starts a grandchild only its tree's containment can end.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from pydantic import SecretStr

from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.application.agent_host.launch_environment import (
    HOSTED_RELAY_VARIABLE,
    HOSTED_ROOT_VARIABLE,
    forbidden_program,
)
from cadrumo.application.agent_host.launcher_protocol import AgentLauncherRefusal
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.agent_host import RuntimeAgentRefused, RuntimeAgentStart, RuntimeAgentStarted
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileStatus
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, OsLockState
from cadrumo.core.config import override_settings, reset_settings_cache
from cadrumo.core.storage_environment import STORAGE_ROOT

from .agent_host_support import (
    DEVELOPMENT_KEY_VARIABLE,
    FAKE_BEARER,
    FAKE_KEY,
    assert_no_secret_exposed,
    mark_lane_root,
    probe_result,
    received,
    stand_in_agent_source,
    stopped_by_input_end,
    tree_reaped,
)
from .seeded_keyring import SEED_VARIABLE, SEEDED_KEYRING, write_seed
from .stored_sign_in_runtime import StoredSignInRuntime, stored_sign_in_runtime

pytestmark = [
    pytest.mark.integration,
    pytest.mark.hex_entrypoint,
    pytest.mark.windows_only,
    pytest.mark.skipif(sys.platform != "win32", reason="the agent tree is contained by a native Windows job"),
]

type StartReply = RuntimeAgentStarted | RuntimeAgentRefused | RuntimeAccessRefusal


def _session(
    runtime: StoredSignInRuntime, frontend: OperationFrontendProjection
) -> tuple[VerifiedRuntimeConnection, UUID]:
    connection = runtime.connect()
    status = runtime.resume(connection, frontend)
    assert isinstance(status, RuntimeProfileStatus), status
    assert status.status.session_id is not None
    return connection, status.status.session_id


def _start(
    runtime: StoredSignInRuntime, connection: VerifiedRuntimeConnection, session_id: UUID, source: Path | None
) -> StartReply:
    return connection.agent_start(
        RuntimeAgentStart(
            request_id=uuid4(),
            profile_id=runtime.profile_id,
            session_id=session_id,
            agent_source=None if source is None else str(source),
        ),
        bytearray(FAKE_BEARER, "utf-8"),
        deadline=time.monotonic() + 120,
    )


@pytest.fixture
def development_key(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Supply the development fallback key to every thread the runtime serves on.

    Development storage mode falls back to the named Cadrumo setting for an
    unset profile record: the process environment for threads that read the
    process-wide settings, and the test's own settings override for this one.
    """
    monkeypatch.setenv(DEVELOPMENT_KEY_VARIABLE, FAKE_KEY)
    reset_settings_cache()
    try:
        with override_settings(cadrumo_llm_claude_api_key=SecretStr(FAKE_KEY)):
            yield
    finally:
        monkeypatch.delenv(DEVELOPMENT_KEY_VARIABLE)
        reset_settings_cache()


@pytest.mark.usefixtures("development_key")
def test_the_agent_starts_with_its_key_only_on_its_frame_and_stops_with_the_persons_sign_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        started = _start(runtime, agent, session_id, source)
        assert isinstance(started, RuntimeAgentStarted), started
        assert started.gateway_port == 47001
        document = received(record)
        assert document["providers"] == ["claude"]
        assert document["bearer_sha256"] == hashlib.sha256(FAKE_BEARER.encode()).hexdigest()
        assert_no_secret_exposed(document)
        environment = document["environment"]
        assert isinstance(environment, dict)
        assert DEVELOPMENT_KEY_VARIABLE not in environment
        # The agent and every process it starts, the relay included, inherit the pinned storage root.
        assert Path(environment[STORAGE_ROOT.variable]).resolve() == runtime.root.resolve()
        relay = Path(environment[HOSTED_RELAY_VARIABLE])
        assert relay.is_absolute() and relay.is_file() and relay.name == "cadrumo-mcp.exe"
        # The relay is the one Cadrumo program named to the agent: no command line, interpreter or shell.
        assert not any(
            name.startswith("CADRUMO_AGENT_HOSTED_") and name not in {HOSTED_ROOT_VARIABLE, HOSTED_RELAY_VARIABLE}
            for name in environment
        )
        assert "COMSPEC" not in {name.upper() for name in environment}
        for directory in environment.get("PATH", "").split(";"):
            if directory and Path(directory).is_dir():
                assert not any(forbidden_program(entry.name) for entry in Path(directory).iterdir()), directory
        for value in environment.values():
            if value != environment[HOSTED_RELAY_VARIABLE] and Path(value).is_file():
                assert not forbidden_program(Path(value).name), value
        hosted_root = Path(environment[HOSTED_ROOT_VARIABLE])
        assert hosted_root.parent == runtime.root / "agent"
        assert str(runtime.profile_id) not in str(hosted_root)
        assert str(runtime.profile_id).replace("-", "") not in hosted_root.name
        # Runs name an existing workspace inside the boundary the agent derives from its hosted root.
        workspace = Path(started.workspace_root)
        assert workspace.is_dir()
        assert workspace.is_relative_to((hosted_root / "home" / "workspaces").resolve())

        person, person_session = _session(runtime, OperationFrontendProjection.CLI)
        runtime.session(person, person_session, "human_sign_out")
        assert tree_reaped(record)
        assert stopped_by_input_end(record)


@pytest.mark.usefixtures("development_key")
def test_an_os_lock_stops_the_agent_without_any_frontend_traffic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id, source), RuntimeAgentStarted)
        runtime.native_login.lock_state = OsLockState.LOCKED
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_the_sessions_expiry_stops_the_agent_without_any_frontend_traffic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id, source), RuntimeAgentStarted)
        runtime.clock.ahead = timedelta(days=30)
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_the_asking_connection_closing_stops_the_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id, source), RuntimeAgentStarted)
        # Another session of the profile ending does not touch this session's agent.
        other, other_session = _session(runtime, OperationFrontendProjection.CLI)
        runtime.session(other, other_session, "session_lock")
        assert not tree_reaped(record, within=3)
        agent.close()
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_runtime_shutdown_drains_and_reaps_the_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id, source), RuntimeAgentStarted)
        runtime.profiles.stop.set()
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_a_second_start_for_the_profile_is_refused_and_starts_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id, source), RuntimeAgentStarted)
        first = received(record)
        second = _start(runtime, agent, session_id, source)
        assert isinstance(second, RuntimeAgentRefused)
        assert second.code is AgentLauncherRefusal.SERVICE_FAILED
        assert received(record) == first


@pytest.mark.usefixtures("development_key")
def test_the_mcp_frontend_is_refused_and_starts_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        mcp, session_id = _session(runtime, OperationFrontendProjection.MCP)
        refused = _start(runtime, mcp, session_id, source)
        assert isinstance(refused, RuntimeAccessRefusal)
        assert refused.code is AccessDenialCode.FRONTEND_DENIED
        assert not (record / "received.json").exists()


def test_no_usable_credential_is_typed_and_leaves_no_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DEVELOPMENT_KEY_VARIABLE, raising=False)
    reset_settings_cache()
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        refused = _start(runtime, agent, session_id, source)
        assert isinstance(refused, RuntimeAgentRefused)
        assert refused.code is AgentLauncherRefusal.PROVIDER_CREDENTIAL_MISSING
        assert not (record / "received.json").exists()


@pytest.mark.usefixtures("development_key")
def test_an_unmarked_root_and_an_absent_source_are_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        unmarked = _start(runtime, agent, session_id, source)
        assert isinstance(unmarked, RuntimeAgentRefused)
        assert unmarked.code is AgentLauncherRefusal.ROOT_UNMARKED
        mark_lane_root(runtime.root)
        absent = _start(runtime, agent, session_id, tmp_path / "no-such-source")
        assert isinstance(absent, RuntimeAgentRefused)
        assert absent.code is AgentLauncherRefusal.SERVICE_ABSENT
        # Without a source tree the runtime starts the agent packaged with it; this checkout has none.
        unpackaged = _start(runtime, agent, session_id, None)
        assert isinstance(unpackaged, RuntimeAgentRefused)
        assert unpackaged.code is AgentLauncherRefusal.SERVICE_ABSENT
        assert not (record / "received.json").exists()


def _probe_environment(runtime: StoredSignInRuntime, tmp_path: Path) -> dict[str, str]:
    """What a program the agent started finds around it: the profile's root, and the person's keychain in reach."""
    from keyring import get_keyring

    from cadrumo.tests.in_memory_keyring import InMemoryKeyring

    store = get_keyring()
    assert isinstance(store, InMemoryKeyring)
    seed = write_seed(tmp_path / "keyring-seed.json", dict(store._entries))
    environment = {
        name: value
        for name, value in os.environ.items()
        if not name.startswith(("CADRUMO_LLM_", "PYTHON_KEYRING")) and "API_KEY" not in name
    }
    environment.update(
        {
            STORAGE_ROOT.variable: str(runtime.root),
            "CADRUMO_ACTIVE_PROFILE": str(runtime.profile_id),
            "PYTHON_KEYRING_BACKEND": SEEDED_KEYRING,
            SEED_VARIABLE: str(seed),
        }
    )
    return environment


def _person_act_probe(runtime: StoredSignInRuntime, tmp_path: Path) -> dict[str, object]:
    """``aeat config logout``, run by a program the agent started, with the person's stored sign-in in reach."""
    return {
        "argv": [
            str(Path(sys.executable).parent / "aeat.exe"),
            "--format",
            "json",
            "config",
            "logout",
            "--secrets-stdin",
        ],
        "env": _probe_environment(runtime, tmp_path),
        "stdin": json.dumps({"passphrase": "not-the-persons-password"}) + "\n",
    }


def _relay_probe(runtime: StoredSignInRuntime, tmp_path: Path) -> dict[str, object]:
    """The MCP relay inside the agent's tree, reading and editing the profile through MCP."""
    return {
        "argv": [sys.executable, "-m", "cadrumo.entrypoints.runtime.tests.agent_tree_relay_probe"],
        "env": _probe_environment(runtime, tmp_path),
        "stdin": "",
    }


@pytest.mark.usefixtures("development_key")
def test_a_program_the_agent_starts_is_refused_the_persons_sign_in_and_acts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        source, record = stand_in_agent_source(tmp_path, probe=_person_act_probe(runtime, tmp_path))
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id, source), RuntimeAgentStarted)
        result = probe_result(record)
        # The command line inside the agent's job reached the runtime and was refused both the person's
        # stored sign-in and the password, whatever frontend it named: nothing it holds signs the person out.
        assert result["returncode"] != 0, result
        attempts = [login for login in runtime.profiles.logins if login.frontend is OperationFrontendProjection.CLI]
        assert {login.method for login in attempts} >= {"receipt"}, attempts
        assert runtime.stored_sign_in() is not None
        assert {lease.session_id for lease in runtime.leases()} == {session_id}
        # A process outside the agent's job is admitted as before, and the agent's own session is untouched.
        _person, person_session = _session(runtime, OperationFrontendProjection.CLI)
        assert person_session != session_id
        assert not tree_reaped(record, within=1)


@pytest.mark.usefixtures("development_key", "authority_operation")
def test_the_relay_in_the_agents_tree_acts_as_the_agent_under_the_lease_that_started_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        source, record = stand_in_agent_source(tmp_path, probe=_relay_probe(runtime, tmp_path))
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id, source), RuntimeAgentStarted)
        result = probe_result(record)
        # With no key, no person's decision and no resumed sign-in, the relay read and edited the profile.
        assert result["returncode"] == 0, result
        relayed = json.loads(str(result["stdout"]).strip().splitlines()[-1])
        assert relayed["admitted"] is True, relayed
        # It held only an attended child of the agent's own lease, never a person's session of its own.
        relay_logins = [login for login in runtime.profiles.logins if login.frontend is OperationFrontendProjection.MCP]
        assert relay_logins, runtime.profiles.logins
        assert runtime.stored_sign_in() is not None
        children = [lease for lease in runtime.leases() if lease.session_id != session_id]
        assert all(lease.parent_session_id == session_id for lease in children), children

        # The person signs out: the agent's lease ends, its tree is reaped, and nothing of the relay survives.
        person, person_session = _session(runtime, OperationFrontendProjection.CLI)
        runtime.session(person, person_session, "human_sign_out")
        assert tree_reaped(record)
        assert runtime.leases() == ()
