"""The runtime hosts a person's agent, bound to the session that asked, against a real runtime and profile.

The profile, its encrypted custody, the stored sign-in, the profile worker that
resolves the provider credential, the native transport and the agent's
contained process tree are all real. The agent is a stand-in image, planted
where the runtime's package values name it, that records how it was started
and what it received and starts a grandchild only its tree's containment can
end.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
import time
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from cadrumo.adapters.local_runtime.agent_process import WindowsAgentInvocationRunner
from cadrumo.adapters.local_runtime.agent_programs import (
    AGENT_COMMAND_LINE,
    PACKAGE_AEAT_VARIABLE,
    PACKAGE_AGENT_VARIABLE,
    PACKAGE_PYTHON_VARIABLE,
    PACKAGE_RELAY_VARIABLE,
    STORES_ASIDE,
    HostedStoresAside,
    profile_agent_root,
)
from cadrumo.adapters.local_runtime.framing import VerifiedRuntimeConnection
from cadrumo.adapters.local_runtime.tests.agent_host_fixture import NATIVE_REFUSAL_SUBJECT
from cadrumo.adapters.local_runtime.tests.agent_store_fixture import (
    CHECKPOINT,
    EXPECTED_CHECKPOINT,
    EXPECTED_PRIMARY,
    PRIMARY,
    WRITE_AHEAD_LOG,
    seed_stores,
    store_directory,
)
from cadrumo.application.agent_host.controller import AgentHostError, AgentHostRefusal, AgentLaunch
from cadrumo.application.agent_host.launch_environment import (
    ADVERTISED_VARIABLES,
    AGENT_SLOTS,
    HOSTED_ROOT_VARIABLE,
    PROGRAM_AEAT_VARIABLE,
    PROGRAM_PYTHON_VARIABLE,
    TOOL_SERVER_VARIABLE,
    agent_launch_environment,
)
from cadrumo.application.agent_host.launcher_protocol import AgentLauncherRefusal
from cadrumo.application.agent_host.store_lifecycle import AgentStoreLifecycle, StoreLifecycleBounds
from cadrumo.application.operations.registry import OperationFrontendProjection
from cadrumo.application.runtime.agent_host import RuntimeAgentRefused, RuntimeAgentStart, RuntimeAgentStarted
from cadrumo.application.runtime.profile_access import RuntimeAccessRefusal, RuntimeProfileStatus
from cadrumo.application.user_profile.access_contracts import AccessDenialCode, OsLockState
from cadrumo.core.storage_environment import STORAGE_ROOT

from .agent_host_support import (
    DEVELOPMENT_KEY_VARIABLE,
    FAKE_BEARER,
    FAKE_KEY,
    FRAMED_CREDENTIAL_ID,
    assert_no_secret_exposed,
    invocations,
    launched,
    mark_lane_root,
    probe_result,
    process_alive,
    received,
    stand_in_agent_image,
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


_RELAY = Path(sys.executable).parent / "cadrumo-mcp.exe"
_AEAT = Path(sys.executable).parent / "aeat.exe"
_PYTHON = Path(sys.executable)
# The hosting contract retired these program paths; the agent refuses a start that carries either.
_RETIRED_PROGRAM_VARIABLES = ("CADRUMO_AGENT_HOSTED_CLI_EXECUTABLE", "CADRUMO_AGENT_HOSTED_PYTHON_EXECUTABLE")


def _packaged_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mode: str = "ready",
    probe: dict[str, object] | None = None,
    stores: dict[str, object] | None = None,
) -> tuple[Path, Path]:
    """Plant the stand-in agent image and name it and the relay as the runtime image's package values do."""
    image, record = stand_in_agent_image(tmp_path, mode=mode, probe=probe, stores=stores)
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(image))
    monkeypatch.setenv(PACKAGE_RELAY_VARIABLE, str(_RELAY))
    monkeypatch.setenv(PACKAGE_AEAT_VARIABLE, str(_AEAT))
    monkeypatch.setenv(PACKAGE_PYTHON_VARIABLE, str(_PYTHON))
    return image, record


def _start(
    runtime: StoredSignInRuntime, connection: VerifiedRuntimeConnection, session_id: UUID, source: Path | None = None
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

    Development storage mode falls back, for an unset profile record, to the
    process environment value constructed from the lane id the agent reports.
    """
    monkeypatch.setenv(DEVELOPMENT_KEY_VARIABLE, FAKE_KEY)
    try:
        yield
    finally:
        monkeypatch.delenv(DEVELOPMENT_KEY_VARIABLE)


@pytest.mark.usefixtures("development_key")
def test_the_agent_starts_with_its_key_only_on_its_frame_and_stops_with_the_persons_sign_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        image, record = _packaged_agent(tmp_path, monkeypatch)
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        started = _start(runtime, agent, session_id)
        assert isinstance(started, RuntimeAgentStarted), started
        assert started.gateway_port == 47001
        document = received(record)
        assert document["providers"] == [FRAMED_CREDENTIAL_ID]
        assert document["bearer_sha256"] == hashlib.sha256(FAKE_BEARER.encode()).hexdigest()
        assert_no_secret_exposed(document)
        environment = document["environment"]
        assert isinstance(environment, dict)
        assert DEVELOPMENT_KEY_VARIABLE not in environment
        # The runtime starts the package's agent image, itself the interpreter, with the gateway invocation.
        launch = launched(record)
        assert Path(str(launch["executable"])) == image
        assert launch["arguments"] == ["-m", "cadrumo_agent.cli.main", "serve"]
        # The agent and every process it starts, the relay included, inherit the pinned storage root.
        assert Path(environment[STORAGE_ROOT.variable]).resolve() == runtime.root.resolve()
        # Of the agent's names the runtime supplies only the gateway's slots and what Cadrumo advertises.
        assert {name for name in environment if name.startswith("CADRUMO_AGENT_")} == AGENT_SLOTS | ADVERTISED_VARIABLES
        assert not set(_RETIRED_PROGRAM_VARIABLES) & set(environment)
        assert Path(environment[TOOL_SERVER_VARIABLE]) == _RELAY
        assert Path(environment[PROGRAM_AEAT_VARIABLE]) == _AEAT
        assert Path(environment[PROGRAM_PYTHON_VARIABLE]) == _PYTHON
        # The search path is not narrowed: in a package the agent image's host composes it.
        assert environment["PATH"] == os.environ["PATH"]
        hosted_root = Path(environment[HOSTED_ROOT_VARIABLE])
        assert Path(str(launch["directory"])).resolve() == hosted_root.resolve()
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
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
        runtime.native_login.lock_state = OsLockState.LOCKED
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_the_sessions_expiry_stops_the_agent_without_any_frontend_traffic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
        runtime.clock.ahead = timedelta(days=30)
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_the_asking_connection_closing_stops_the_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
        # Another session of the profile ending does not touch this session's agent.
        other, other_session = _session(runtime, OperationFrontendProjection.CLI)
        runtime.session(other, other_session, "session_lock")
        assert not tree_reaped(record, within=3)
        agent.close()
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_runtime_shutdown_drains_and_reaps_the_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
        runtime.profiles.stop.set()
        assert tree_reaped(record)


@pytest.mark.usefixtures("development_key")
def test_a_second_start_for_the_profile_is_refused_and_starts_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
        first = received(record)
        second = _start(runtime, agent, session_id)
        assert isinstance(second, RuntimeAgentRefused)
        assert second.code is AgentLauncherRefusal.SERVICE_FAILED
        assert received(record) == first


@pytest.mark.usefixtures("development_key")
def test_the_mcp_frontend_is_refused_and_starts_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        mcp, session_id = _session(runtime, OperationFrontendProjection.MCP)
        refused = _start(runtime, mcp, session_id)
        assert isinstance(refused, RuntimeAccessRefusal)
        assert refused.code is AccessDenialCode.FRONTEND_DENIED
        assert not (record / "received.json").exists()


def test_no_usable_credential_is_typed_and_leaves_no_agent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(DEVELOPMENT_KEY_VARIABLE, raising=False)
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        refused = _start(runtime, agent, session_id)
        assert isinstance(refused, RuntimeAgentRefused)
        assert refused.code is AgentLauncherRefusal.PROVIDER_CREDENTIAL_MISSING
        assert not (record / "received.json").exists()


@pytest.mark.usefixtures("development_key")
def test_an_unmarked_root_and_an_absent_source_are_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(PACKAGE_AGENT_VARIABLE, raising=False)
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
        # Without a source tree the runtime starts the agent image its package names; a checkout names none.
        unpackaged = _start(runtime, agent, session_id, None)
        assert isinstance(unpackaged, RuntimeAgentRefused)
        assert unpackaged.code is AgentLauncherRefusal.SERVICE_ABSENT
        assert not (record / "received.json").exists()


@pytest.mark.usefixtures("development_key")
def test_a_development_source_tree_runs_the_gateway_invocation_from_its_own_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv(PACKAGE_AGENT_VARIABLE, raising=False)
    source, record = stand_in_agent_source(tmp_path)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id, source), RuntimeAgentStarted)
        environment = received(record)["environment"]
        assert isinstance(environment, dict)
        launch = launched(record)
        assert Path(str(launch["executable"])).is_relative_to(source)
        assert launch["arguments"] == ["-m", "cadrumo_agent.cli.main", "serve"]
        assert Path(str(launch["directory"])) == source
        # The checkout's relay, beside this interpreter. Its command line and interpreter sit inside the
        # checkout's virtual environment, which the agent refuses to run as programs, so they are not advertised.
        assert Path(environment[TOOL_SERVER_VARIABLE]) == _RELAY
        assert PROGRAM_AEAT_VARIABLE not in environment
        assert PROGRAM_PYTHON_VARIABLE not in environment
        advertised = ADVERTISED_VARIABLES - {PROGRAM_AEAT_VARIABLE, PROGRAM_PYTHON_VARIABLE}
        assert {name for name in environment if name.startswith("CADRUMO_AGENT_")} == AGENT_SLOTS | advertised


_CONTROLLER_LOGGER = "cadrumo.application.agent_host.controller"


@pytest.mark.usefixtures("development_key")
def test_an_agent_the_native_host_refuses_to_launch_is_a_service_failure_that_records_the_hosts_reason(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch, mode="native_refusal")
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        with caplog.at_level(logging.WARNING, logger=_CONTROLLER_LOGGER):
            first = _start(runtime, agent, session_id)
            second = _start(runtime, agent, session_id)
        for refused in (first, second):
            assert isinstance(refused, RuntimeAgentRefused), refused
            assert refused.code is AgentLauncherRefusal.SERVICE_FAILED
        # The agent never ran, and each refusal released the profile's one reservation: both starts launched.
        assert not (record / "received.json").exists()
        messages = [record.getMessage() for record in caplog.records if record.name == _CONTROLLER_LOGGER]
        assert (
            messages
            == [
                "agent launch refused by the native host exit=125 native_refusal=launch_value_malformed "
                f"subject={NATIVE_REFUSAL_SUBJECT}"
            ]
            * 2
        )


@pytest.mark.usefixtures("development_key")
def test_an_agent_that_exits_before_its_ready_line_without_the_hosts_status_is_a_service_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch, mode="native_other_exit")
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        with caplog.at_level(logging.WARNING, logger=_CONTROLLER_LOGGER):
            refused = _start(runtime, agent, session_id)
        assert isinstance(refused, RuntimeAgentRefused), refused
        assert refused.code is AgentLauncherRefusal.SERVICE_FAILED
        assert not (record / "received.json").exists()
        assert [item for item in caplog.records if item.name == _CONTROLLER_LOGGER] == []


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
        _, record = _packaged_agent(tmp_path, monkeypatch, probe=_person_act_probe(runtime, tmp_path))
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
        result = probe_result(record)
        # The command line inside the agent's job reached the runtime and was refused both the person's
        # stored sign-in and the password, whatever frontend it named: nothing it holds signs the person out.
        assert result["returncode"] != 0, result
        attempts = [login for login in runtime.profiles.logins if login.frontend is OperationFrontendProjection.CLI]
        assert {login.method for login in attempts} >= {"receipt"}, attempts
        assert runtime.stored_sign_in() is not None
        # Naming the command line won it nothing: whatever it was admitted as is an attended child of the
        # agent's own lease, no wider than it, and the sign-out it asked for was refused as the person's act.
        assert "person_act_required" in json.dumps(result), result
        agent_lease = runtime.lease(session_id)
        for lease in runtime.leases():
            if lease.session_id != session_id:
                assert lease.parent_session_id == session_id, lease
                assert lease.scope.operations <= agent_lease.scope.operations, lease
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
        _, record = _packaged_agent(tmp_path, monkeypatch, probe=_relay_probe(runtime, tmp_path))
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
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


def _verbs(record: Path) -> list[list[str]]:
    verbs: list[list[str]] = []
    for entry in invocations(record):
        verb = entry["verb"]
        assert isinstance(verb, list)
        verbs.append([str(part) for part in verb])
    return verbs


def _stores(hosted_root: Path) -> dict[str, str]:
    stores = store_directory(hosted_root)
    if not stores.is_dir():
        return {}
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(stores.iterdir())}


_SETUP_SEQUENCE = [["version", "--json"], ["stores-state"], ["setup"], ["stores-state"]]


@pytest.mark.usefixtures("development_key")
def test_a_fresh_root_is_set_up_by_the_agents_own_invocations_in_the_gateways_environment_before_it_serves(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
        assert _verbs(record) == _SETUP_SEQUENCE
        served = received(record)["environment"]
        hosted_root = profile_agent_root(runtime.root, runtime.profile_id)
        for entry in invocations(record):
            # The same program, directory and environment as the gateway it prepares.
            assert Path(str(entry["executable"])) == image
            assert Path(str(entry["directory"])).resolve() == hosted_root.resolve()
            assert entry["environment"] == served
        assert launched(record)["arguments"] == [*AGENT_COMMAND_LINE, "serve"]
        assert _stores(hosted_root)[PRIMARY] == EXPECTED_PRIMARY
        assert not (hosted_root / STORES_ASIDE).exists()


@pytest.mark.usefixtures("development_key")
def test_older_stores_are_copied_aside_then_migrated_and_the_copy_goes_once_they_read_current(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        hosted_root = profile_agent_root(runtime.root, runtime.profile_id)
        seed_stores(hosted_root, primary="0001", checkpoint=EXPECTED_CHECKPOINT)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        assert isinstance(_start(runtime, agent, session_id), RuntimeAgentStarted)
        assert _verbs(record) == [
            ["version", "--json"],
            ["stores-state"],
            ["migrate", "--expect-from", "0001", "--expect-head", EXPECTED_PRIMARY],
            ["stores-state"],
        ]
        # The migrate ran over stores whose complete copy, write-ahead log included, was already aside.
        assert invocations(record)[2]["aside"] == sorted([PRIMARY, CHECKPOINT, WRITE_AHEAD_LOG])
        assert _stores(hosted_root)[PRIMARY] == EXPECTED_PRIMARY
        assert not (hosted_root / STORES_ASIDE).exists()
        assert received(record)["providers"] == [FRAMED_CREDENTIAL_ID]


@pytest.mark.usefixtures("development_key")
def test_newer_stores_are_a_downgrade_that_is_refused_as_incompatible_and_left_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        hosted_root = profile_agent_root(runtime.root, runtime.profile_id)
        seed_stores(hosted_root, primary="0003", checkpoint=EXPECTED_CHECKPOINT)
        before = _stores(hosted_root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        refused = _start(runtime, agent, session_id)
        assert isinstance(refused, RuntimeAgentRefused), refused
        assert refused.code is AgentLauncherRefusal.SERVICE_INCOMPATIBLE
        assert _verbs(record) == [["version", "--json"], ["stores-state"]]
        assert _stores(hosted_root) == before
        assert not (record / "received.json").exists()


@pytest.mark.usefixtures("development_key")
@pytest.mark.parametrize(
    "stores",
    [pytest.param({"setup": "fail"}, id="setup-failed"), pytest.param({"malformed": "stores-state"}, id="malformed")],
)
def test_stores_that_cannot_be_brought_to_current_refuse_the_start_and_release_the_profile(
    stores: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch, stores=stores)
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        for _attempt in range(2):
            # Each refusal released the profile's one reservation: the second start ran the sequence again.
            refused = _start(runtime, agent, session_id)
            assert isinstance(refused, RuntimeAgentRefused), refused
            assert refused.code is AgentLauncherRefusal.SERVICE_FAILED
        expected = _SETUP_SEQUENCE[:3] if stores.get("setup") == "fail" else _SETUP_SEQUENCE[:2]
        assert _verbs(record) == expected * 2
        assert not (record / "received.json").exists()


@pytest.mark.usefixtures("development_key")
def test_a_failed_migrate_keeps_the_copy_and_no_later_start_migrates_over_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, record = _packaged_agent(tmp_path, monkeypatch, stores={"migrate": "fail"})
    with stored_sign_in_runtime(tmp_path, monkeypatch) as runtime:
        mark_lane_root(runtime.root)
        hosted_root = profile_agent_root(runtime.root, runtime.profile_id)
        seed_stores(hosted_root, primary="0001", checkpoint=EXPECTED_CHECKPOINT)
        original = _stores(hosted_root)
        agent, session_id = _session(runtime, OperationFrontendProjection.AGENT_HOST)
        for _attempt in range(2):
            refused = _start(runtime, agent, session_id)
            assert isinstance(refused, RuntimeAgentRefused), refused
            assert refused.code is AgentLauncherRefusal.SERVICE_FAILED
        verbs = [verb[0] for verb in _verbs(record)]
        assert verbs == ["version", "stores-state", "migrate", "version", "stores-state"]
        # The live stores were left half-way; the copy is the stores as they were before the migrate.
        assert _stores(hosted_root) != original
        aside = hosted_root / STORES_ASIDE
        assert {path.name: path.read_text(encoding="utf-8") for path in aside.iterdir()} == original
        assert not (record / "received.json").exists()


def test_an_invocation_past_its_bound_is_ended_with_its_whole_tree_and_its_outcome_stays_unknown(
    tmp_path: Path,
) -> None:
    image, record = stand_in_agent_image(tmp_path, stores={"migrate": "hang"})
    hosted_root = tmp_path / "hosted-root"
    hosted_root.mkdir()
    seed_stores(hosted_root, primary="0001", checkpoint=EXPECTED_CHECKPOINT)
    environment = agent_launch_environment(
        storage_root=tmp_path / "storage",
        agent_root=hosted_root,
        relay=_RELAY,
        aeat=_AEAT,
        python=_PYTHON,
        received=os.environ,
    )
    lifecycle = AgentStoreLifecycle(
        runner=WindowsAgentInvocationRunner(),
        launch=AgentLaunch(
            executable=image, arguments=(*AGENT_COMMAND_LINE, "serve"), directory=hosted_root, environment=environment
        ),
        command_line=AGENT_COMMAND_LINE,
        aside=HostedStoresAside(hosted_root),
        quiesced=lambda: True,
        bounds=StoreLifecycleBounds(migrate=5.0),
    )
    started = time.monotonic()
    with pytest.raises(AgentHostError) as refused:
        lifecycle.prepare()
    assert refused.value.reason is AgentHostRefusal.STORES_UNPREPARED
    assert time.monotonic() - started < 60
    hung = invocations(record)[-1]
    assert hung["verb"] == ["migrate", "--expect-from", "0001", "--expect-head", EXPECTED_PRIMARY]
    pid = hung["pid"]
    assert isinstance(pid, int)
    assert not process_alive(pid, within=5)
    # Whether the migrate changed anything is not known: the copy stays and no second migrate runs.
    assert (hosted_root / STORES_ASIDE).is_dir()
    with pytest.raises(AgentHostError):
        lifecycle.prepare()
    assert [verb[0] for verb in _verbs(record)].count("migrate") == 1
