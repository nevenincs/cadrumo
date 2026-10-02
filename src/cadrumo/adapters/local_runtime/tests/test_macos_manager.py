"""Portable LaunchAgent decisions with explicit native observations, not native proof."""

from __future__ import annotations

import plistlib
from typing import cast, override

import pytest

from cadrumo.application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from cadrumo.application.runtime.management import RuntimeManagerKind, RuntimeManagerProcessState, RuntimeServiceBinding

from .. import macos_manager as implementation
from ..macos_manager import (
    MacosJobObservation,
    MacosUserManager,
    macos_agent_definition_policy,
    project_macos_job,
)
from ..macos_process import MacosProcessObservation
from ..manager_commands import ManagerCommandResult, NativeManagerCommand
from ..service_definitions import macos_agent_plist, runtime_service_arguments, runtime_service_name

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


@pytest.fixture
def binding() -> RuntimeServiceBinding:
    return RuntimeServiceBinding(
        executable="/Applications/Cadrumo/bin/cadrumo-runtime",
        storage_root="/Users/fixture/Cadrumo",
        storage_identity="a" * 64,
        os_owner_id="501",
        product_version="synthetic-cohort",
    )


class _ObservedLaunchd:
    """Only native facts and control acknowledgements are supplied by this fixture."""

    def __init__(self, binding: RuntimeServiceBinding, *, enabled: bool = False, provisioned: bool = True) -> None:
        self.binding = binding
        self.payload = macos_agent_plist(binding, login_autostart=enabled) if provisioned else None
        self.observation = MacosJobObservation(loaded=False, binding_matches=False)
        self.actions: list[tuple[tuple[str, ...], float]] = []
        self.writes: list[bytes] = []
        self.available = True

    async def job(self, binding: RuntimeServiceBinding) -> MacosJobObservation:
        assert binding == self.binding
        if not self.available:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return self.observation

    async def control(self, arguments: tuple[str, ...], *, timeout: float = 5) -> None:
        self.actions.append((arguments, timeout))
        if arguments[0] == "bootout":
            self.observation = MacosJobObservation(loaded=False, binding_matches=False)
            return
        assert self.payload is not None
        document = cast(dict[str, object], plistlib.loads(self.payload))
        enabled = document["RunAtLoad"] is True
        pid = 123 if arguments[0] == "kickstart" or enabled else None
        self.observation = _project(_native_document(binding=self.binding, pid=pid), self.binding, enabled=enabled)

    def definition(self, binding: RuntimeServiceBinding) -> bytes | None:
        assert binding == self.binding
        return self.payload

    def definition_path(self, binding: RuntimeServiceBinding) -> str:
        return "/Users/fixture/Library/LaunchAgents/" + runtime_service_name(binding) + ".plist"

    def publish(self, binding: RuntimeServiceBinding, payload: bytes, *, expected: bytes | None) -> None:
        assert binding == self.binding and expected == self.payload
        self.writes.append(payload)
        self.payload = payload


def _definition_path(binding: RuntimeServiceBinding) -> str:
    return "/Users/fixture/Library/LaunchAgents/" + runtime_service_name(binding) + ".plist"


def _native_document(*, binding: RuntimeServiceBinding, pid: int | None = None) -> dict[str, object]:
    document: dict[str, object] = {
        "Label": runtime_service_name(binding),
        "LastExitStatus": 0,
        "LimitLoadToSessionType": "Aqua",
        "OnDemand": True,
        "Program": binding.executable,
        "ProgramArguments": [binding.executable, *runtime_service_arguments(binding)],
        "StandardErrorPath": "/dev/null",
        "StandardOutPath": "/dev/null",
    }
    if pid is not None:
        document["PID"] = pid
    return document


def _native_print(binding: RuntimeServiceBinding, *, enabled: bool, pid: int | None = None) -> str:
    rows = [
        f"gui/{binding.os_owner_id}/{runtime_service_name(binding)} = {{",
        "\tpath = " + _definition_path(binding),
        "\ttype = LaunchAgent",
        "\tstate = " + ("not running" if pid is None else "running"),
        "\tprogram = " + binding.executable,
        "\targuments = {",
        *("\t\t" + argument for argument in (binding.executable, *runtime_service_arguments(binding))),
        "\t}",
        "\tworking directory = " + binding.storage_root,
        "\tstdout path = /dev/null",
        "\tstderr path = /dev/null",
        f"\tdomain = gui/{binding.os_owner_id} [100002]",
        "\tasid = 100002",
        "\tumask = 77",
        "\tminimum runtime = 60",
        "\texit timeout = 25",
        "\tdefault environment = {",
        "\t\tPATH => /usr/bin:/bin:/usr/sbin:/sbin",
        "\t}",
        "\tenvironment = {",
        "\t\tOSLogRateLimit => 64",
        "\t\tXPC_SERVICE_NAME => " + runtime_service_name(binding),
        "\t}",
    ]
    if pid is not None:
        rows.append(f"\tpid = {pid}")
    if enabled:
        rows.extend(("\tsemaphores = {", "\t\tsuccessful exit => 0", "\t}"))
    rows.extend(("\tproperties = " + ("runatload" if enabled else ""), "}"))
    return "\n".join(rows) + "\n"


def _project(document: object, binding: RuntimeServiceBinding, *, enabled: bool) -> MacosJobObservation:
    pid = cast(dict[str, object], document).get("PID")
    return project_macos_job(
        document,
        binding,
        persisted_definition=macos_agent_plist(binding, login_autostart=enabled),
        native_print=_native_print(binding, enabled=enabled, pid=cast(int | None, pid)),
        definition_path=_definition_path(binding),
    )


@pytest.mark.parametrize("enabled", [False, True])
def test_effective_job_requires_complete_canonical_binding_and_literal_policy(
    binding: RuntimeServiceBinding, enabled: bool
) -> None:
    payload = macos_agent_plist(binding, login_autostart=enabled)
    document = _native_document(binding=binding, pid=123)
    assert macos_agent_definition_policy(payload, binding) is enabled
    observed = _project(document, binding, enabled=enabled)
    assert observed.loaded and observed.binding_matches and observed.login_autostart is enabled
    assert observed.process_id == 123
    malformed = cast(dict[str, object], plistlib.loads(payload))
    malformed["RunAtLoad"] = int(enabled)
    assert not project_macos_job(
        document,
        binding,
        persisted_definition=plistlib.dumps(malformed),
        native_print=_native_print(binding, enabled=enabled, pid=123),
        definition_path=_definition_path(binding),
    ).binding_matches


@pytest.mark.parametrize("enabled", [False, True])
def test_reduced_native_view_requires_exact_saved_and_effective_witnesses(
    binding: RuntimeServiceBinding, enabled: bool
) -> None:
    payload = macos_agent_plist(binding, login_autostart=enabled)
    document = _native_document(binding=binding)
    assert not project_macos_job(document, binding).binding_matches
    observed = _project(document, binding, enabled=enabled)
    assert observed.loaded and observed.binding_matches and observed.login_autostart is enabled
    foreign = binding.model_copy(update={"storage_root": "/Users/other/Cadrumo"})
    assert not project_macos_job(
        document,
        binding,
        persisted_definition=macos_agent_plist(foreign, login_autostart=enabled),
        native_print=_native_print(binding, enabled=enabled),
        definition_path=_definition_path(binding),
    ).binding_matches
    assert not project_macos_job(
        document,
        binding,
        persisted_definition=payload,
        definition_path=_definition_path(binding),
    ).binding_matches
    arguments = cast(list[object], document["ProgramArguments"])
    original_root = arguments[2]
    arguments[2] = "/Users/other/Cadrumo"
    assert not _project(document, binding, enabled=enabled).binding_matches
    arguments[2] = original_root
    del document["StandardErrorPath"]
    assert not _project(document, binding, enabled=enabled).binding_matches


@pytest.mark.parametrize(
    "original,replacement",
    [
        ("working directory = /Users/fixture/Cadrumo", "working directory = /Users/foreign/Cadrumo"),
        ("umask = 77", "umask = 22"),
        ("exit timeout = 25", "exit timeout = 0"),
        ("minimum runtime = 60", "minimum runtime = 1"),
        ("properties = \n", "properties = abandon process group\n"),
        ("properties = \n", "properties = runatload\n"),
        ("path = /Users/fixture/Library/LaunchAgents/", "path = /Users/other/Library/LaunchAgents/"),
        ("state = not running", "state = running"),
        ("OSLogRateLimit => 64", "PYTHONPATH => /Users/foreign"),
        ("exit timeout = 25", "exit timeout = 25\n\texit timeout = 0"),
    ],
)
def test_effective_print_conflicts_refuse_despite_matching_saved_file_and_native_argv(
    binding: RuntimeServiceBinding, original: str, replacement: str
) -> None:
    printed = _native_print(binding, enabled=False)
    assert original in printed
    observed = project_macos_job(
        _native_document(binding=binding),
        binding,
        persisted_definition=macos_agent_plist(binding, login_autostart=False),
        native_print=printed.replace(original, replacement),
        definition_path=_definition_path(binding),
    )
    assert observed.loaded and not observed.binding_matches


def test_failure_restart_condition_and_pid_must_match_both_effective_views(binding: RuntimeServiceBinding) -> None:
    printed = _native_print(binding, enabled=True, pid=123)
    for conflicting in (
        printed.replace("successful exit => 0", "successful exit => 1"),
        printed.replace("\tpid = 123", "\tpid = 124"),
        printed.replace("\tproperties = runatload", "\tproperties = "),
    ):
        assert not project_macos_job(
            _native_document(binding=binding, pid=123),
            binding,
            persisted_definition=macos_agent_plist(binding, login_autostart=True),
            native_print=conflicting,
            definition_path=_definition_path(binding),
        ).binding_matches


@pytest.mark.asyncio
@pytest.mark.parametrize("foreign", [False, True])
async def test_native_inspector_retries_unavailable_identity_but_never_foreign_identity(
    binding: RuntimeServiceBinding, monkeypatch: pytest.MonkeyPatch, foreign: bool
) -> None:
    platform = _ObservedLaunchd(binding)
    reads: list[int] = []

    def factory(selected: RuntimeServiceBinding) -> _ObservedLaunchd:
        assert selected == binding
        return platform

    def document(label: str) -> dict[str, object]:
        assert label == runtime_service_name(binding)
        return _native_document(binding=binding, pid=123)

    async def print_job(
        command: NativeManagerCommand, arguments: tuple[str, ...], *, timeout: float = 5
    ) -> ManagerCommandResult:
        assert command is NativeManagerCommand.LAUNCHCTL
        assert arguments == ("print", "gui/501/" + runtime_service_name(binding))
        assert 0 < timeout <= 3.5
        return ManagerCommandResult(0, _native_print(binding, enabled=False, pid=123))

    def process(pid: int, *, expected_owner: str) -> MacosProcessObservation:
        assert pid == 123 and expected_owner == "501"
        reads.append(pid)
        if foreign:
            raise RuntimeRefusalError(RuntimeRefusalCode.PEER_UNTRUSTED)
        if len(reads) == 1:
            raise RuntimeRefusalError(RuntimeRefusalCode.UNAVAILABLE)
        return MacosProcessObservation(pid, expected_owner, 1, pid, 1000, 1)

    monkeypatch.setattr(implementation, "_NativeMacosLaunchd", factory)
    monkeypatch.setattr(implementation, "_native_job_dictionary", document)
    monkeypatch.setattr(implementation, "run_manager_command", print_job)
    monkeypatch.setattr(implementation, "read_macos_process", process)
    if foreign:
        with pytest.raises(RuntimeRefusalError) as refused:
            await implementation._inspect_macos_job(binding)
        assert refused.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
        assert reads == [123]
    else:
        observed = await implementation._inspect_macos_job(binding)
        assert observed.binding_matches and observed.process_id == 123
        assert reads == [123, 123, 123]
    assert not platform.actions and not platform.writes


class _DefinitionChangedDuringObservation(_ObservedLaunchd):
    @override
    async def job(self, binding: RuntimeServiceBinding) -> MacosJobObservation:
        observed = await super().job(binding)
        self.payload = macos_agent_plist(binding, login_autostart=True)
        return observed


@pytest.mark.asyncio
async def test_definition_change_during_native_job_observation_refuses_before_control(
    binding: RuntimeServiceBinding,
) -> None:
    native = _DefinitionChangedDuringObservation(binding)
    manager = MacosUserManager(binding, native=native)
    with pytest.raises(RuntimeRefusalError) as refused:
        await manager.start()
    assert refused.value.reason is RuntimeRefusalCode.VERSION_MISMATCH
    assert not native.actions and not native.writes


@pytest.mark.parametrize(
    "field,value",
    [
        ("Program", "/Applications/Foreign/bin/runtime"),
        ("WorkingDirectory", "/Users/other/Cadrumo"),
        ("AbandonProcessGroup", True),
        ("ExitTimeOut", 0),
        ("EnvironmentVariables", {"UNREVIEWED": "value"}),
    ],
)
def test_foreign_or_unbounded_effective_job_is_not_owned(
    binding: RuntimeServiceBinding, field: str, value: object
) -> None:
    document = _native_document(binding=binding)
    document[field] = value
    assert not _project(document, binding, enabled=False).binding_matches


@pytest.mark.parametrize("pid", [True, -1, 2_147_483_648, "123"])
def test_native_pid_shape_cannot_be_coerced_into_process_evidence(binding: RuntimeServiceBinding, pid: object) -> None:
    document = _native_document(binding=binding)
    document["PID"] = pid
    with pytest.raises(RuntimeRefusalError) as caught:
        _project(document, binding, enabled=False)
    assert caught.value.reason is RuntimeRefusalCode.INVALID_FRAME


@pytest.mark.asyncio
async def test_on_demand_start_and_stop_preserve_disabled_autostart(binding: RuntimeServiceBinding) -> None:
    native = _ObservedLaunchd(binding)
    manager = MacosUserManager(binding, native=native)
    before = native.payload
    initial = await manager.inspect()
    assert initial.kind is RuntimeManagerKind.MACOS_AGENT and initial.available and initial.provisioned
    assert not initial.login_autostart and initial.process_state is RuntimeManagerProcessState.STOPPED
    await manager.start()
    assert (await manager.inspect()).process_state is RuntimeManagerProcessState.RUNNING
    assert native.actions[0][0][0] == "bootstrap" and native.actions[1][0][0] == "kickstart"
    assert native.payload == before and not native.writes
    await manager.start()
    assert len(native.actions) == 2
    await manager.stop()
    assert native.actions[-1] == (("bootout", f"gui/501/{runtime_service_name(binding)}"), 25)
    assert native.payload == before and not (await manager.inspect()).login_autostart
    await manager.stop()
    assert len(native.actions) == 3


@pytest.mark.asyncio
async def test_missing_provisioning_never_starts_but_explicit_configure_can_provision(
    binding: RuntimeServiceBinding,
) -> None:
    native = _ObservedLaunchd(binding, provisioned=False)
    manager = MacosUserManager(binding, native=native)
    assert not (await manager.inspect()).provisioned
    with pytest.raises(RuntimeRefusalError) as caught:
        await manager.start()
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE and not native.actions and not native.writes
    configured = await manager.configure(login_autostart=False)
    assert configured.provisioned and configured.binding_matches and not configured.login_autostart
    assert configured.process_state is RuntimeManagerProcessState.STOPPED
    assert native.writes == [macos_agent_plist(binding, login_autostart=False)]


@pytest.mark.asyncio
async def test_explicit_login_start_policy_survives_managed_stop_and_restart(binding: RuntimeServiceBinding) -> None:
    native = _ObservedLaunchd(binding, provisioned=False)
    manager = MacosUserManager(binding, native=native)
    configured = await manager.configure(login_autostart=True)
    assert configured.login_autostart and configured.process_state is RuntimeManagerProcessState.RUNNING
    assert native.writes == [macos_agent_plist(binding, login_autostart=True)]
    before = native.payload
    await manager.stop()
    stopped = await manager.inspect()
    assert stopped.login_autostart and stopped.process_state is RuntimeManagerProcessState.STOPPED
    await manager.start()
    restarted = await manager.inspect()
    assert restarted.login_autostart and restarted.process_state is RuntimeManagerProcessState.RUNNING
    assert native.payload == before and len(native.writes) == 1
    assert [arguments[0] for arguments, _timeout in native.actions] == ["bootstrap", "bootout", "bootstrap"]


@pytest.mark.asyncio
async def test_loaded_policy_change_refuses_before_any_definition_or_job_mutation(
    binding: RuntimeServiceBinding,
) -> None:
    native = _ObservedLaunchd(binding)
    manager = MacosUserManager(binding, native=native)
    await manager.start()
    before, actions = native.payload, tuple(native.actions)
    with pytest.raises(RuntimeRefusalError) as caught:
        await manager.configure(login_autostart=True)
    assert caught.value.reason is RuntimeRefusalCode.UNAVAILABLE
    assert native.payload == before and tuple(native.actions) == actions and not native.writes


@pytest.mark.asyncio
async def test_substituted_job_refuses_control_and_unavailable_manager_does_not_provision(
    binding: RuntimeServiceBinding,
) -> None:
    native = _ObservedLaunchd(binding)
    native.observation = MacosJobObservation(loaded=True, binding_matches=False, process_id=123)
    manager = MacosUserManager(binding, native=native)
    with pytest.raises(RuntimeRefusalError) as caught:
        await manager.stop()
    assert caught.value.reason is RuntimeRefusalCode.VERSION_MISMATCH and not native.actions
    native.available = False
    unavailable = await manager.inspect()
    assert not unavailable.available and unavailable.process_state is RuntimeManagerProcessState.UNKNOWN
    assert not native.writes


def test_non_macos_native_composition_refuses_without_loading_frameworks(binding: RuntimeServiceBinding) -> None:
    import sys

    if sys.platform == "darwin":
        pytest.skip("requires the unsupported native platform")
    with pytest.raises(RuntimeRefusalError) as caught:
        MacosUserManager(binding)
    assert caught.value.reason is RuntimeRefusalCode.PEER_UNTRUSTED
