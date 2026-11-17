"""Every agent invocation the service sends is one the package declares for the right launch profile.

The bundled agent image has no default profile: an argument vector that matches
no declared invocation is refused by the native launcher before Python starts.
Each vector here comes from the service's own command builder, run with
synthetic inputs and a recording runner, and is resolved against the
declaration the way the launcher selects a profile.
"""

from __future__ import annotations

import dataclasses
import json
import os
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Iterator, Mapping, Sequence
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast, get_args
from uuid import UUID

import pytest

from cadrumo_agent_service import service_startup
from cadrumo_agent_service.adapters import agent_provider_auth_status
from cadrumo_agent_service.adapters.agent_programs import (
    AGENT_COMMAND_LINE,
    PACKAGE_AGENT_VARIABLE,
    agent_image,
    profile_agent_root,
)
from cadrumo_agent_service.adapters.agent_provider_auth_status import AgentProviderAuthStatusProbe
from cadrumo_agent_service.adapters.agent_provider_catalog import AgentProviderCatalogSource
from cadrumo_agent_service.adapters.provider_login import DEVICE_PROVIDERS, SIGN_IN_PROVIDERS, prepare_provider_login
from cadrumo_agent_service.host.controller import AgentHostError, AgentHostRefusal, AgentLaunch
from cadrumo_agent_service.host.store_lifecycle import (
    AGENT_COMMAND_LINE_API,
    AgentInvocationResult,
    AgentStoreLifecycle,
)
from cadrumo_agent_service.providers.application.contracts import SignInMethod
from cadrumo_agent_service.providers.application.ports import ProviderCatalogUnavailableError
from cadrumo_agent_service.providers.domain.record import LocalEngine
from cadrumo_agent_service.service import AgentService
from cadrumo_client.contracts.deadline_budget import TimeoutDeadline
from cadrumo_client.transport.service_client import InstalledServiceClient
from dev.paths import REPO_ROOT

from ..application_environment import load_for_build, parse
from ..environment_declaration_primitives import DECLARATION
from ..environment_models import ApplicationEnvironment
from ..environment_reference import LaunchRefusedError, reference_select

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AGENT = "cadrumo-agent"
_FAMILIES = ("windows", "posix")
_SOURCE = (REPO_ROOT / DECLARATION).read_text(encoding="utf-8")
_PROFILE = UUID("12345678-1234-5678-1234-567812345678")
_PROVIDER = SIGN_IN_PROVIDERS[0]

type Sent = tuple[str, tuple[str, ...]]
"""The launch profile the service needs for one vector, and the vector."""


def _matching_profiles(declaration: ApplicationEnvironment, family: str, arguments: Sequence[str]) -> list[str]:
    """Return the profile of every declared invocation that admits ``arguments``, one per match.

    Each invocation is resolved alone through the reference selector, so a match
    is counted exactly as the launcher would select it and no earlier
    invocation can shadow a later one.
    """
    matched: list[str] = []
    for invocation in declaration.invocations:
        if declaration.profiles[invocation.profile]["image"] != _AGENT:
            continue
        alone = dataclasses.replace(declaration, invocations=(invocation,))
        try:
            selected = reference_select(alone, family, _AGENT, arguments)
        except LaunchRefusedError:
            continue
        if selected == invocation.profile:
            matched.append(selected)
    return matched


def _undeclared(declaration: ApplicationEnvironment, sent: Sequence[Sent]) -> list[str]:
    """Describe every vector that does not select exactly one invocation of its profile on every family."""
    findings: list[str] = []
    for family in _FAMILIES:
        for profile, arguments in sent:
            matched = _matching_profiles(declaration, family, arguments)
            if matched != [profile]:
                findings.append(f"{family}: {list(arguments)} needs {profile}, declared {matched}")
            else:
                assert reference_select(declaration, family, _AGENT, arguments) == profile
    return findings


def _agent_executable(tmp_path: Path) -> Path:
    executable = tmp_path / "package" / "cadrumo-agent.exe"
    executable.parent.mkdir(parents=True, exist_ok=True)
    executable.write_bytes(b"")
    return executable


class _Recorder:
    """Records each vector it is asked to run and answers from ``answer``, or refuses when none is given."""

    def __init__(self, answer: Callable[[tuple[str, ...]], AgentInvocationResult] | None = None) -> None:
        self.calls: list[tuple[str, ...]] = []
        self.settled = True
        self._answer = answer

    def run(self, *, arguments: Sequence[str], **_ignored: object) -> AgentInvocationResult:
        self.calls.append(tuple(arguments))
        if self._answer is None:
            raise AgentHostError(AgentHostRefusal.LAUNCH_FAILED)
        return self._answer(tuple(arguments))


def _document(document: object) -> AgentInvocationResult:
    return AgentInvocationResult(status=0, standard_output=json.dumps(document).encode())


def _stores(state: str) -> dict[str, object]:
    found = None if state == "absent" else ("0002" if state == "current" else "0001")
    return {
        "state": state,
        "primary": {"state": state, "found": found, "expected": "0002"},
        "checkpoint": {"state": "current", "found": "1.0.0", "expected": "1.0.0"},
    }


_STEP_SUCCEEDED = {
    "status": "succeeded",
    "target_head": "0002",
    "stores": [],
    "duration_seconds": 0.0,
    "failed_stage": None,
    "error_class": None,
    "detail": None,
    "app_home": "home",
}


class _Aside:
    def __init__(self) -> None:
        self.copy = False

    def clear_partial(self) -> None:
        pass

    def kept(self) -> bool:
        return self.copy

    def keep(self) -> None:
        self.copy = True

    def discard(self) -> None:
        self.copy = False


def _store_sequence(tmp_path: Path, initial: str) -> list[tuple[str, ...]]:
    """Run the service's store preparation for stores first read as ``initial`` and return what it sent."""
    verb_start = len(AGENT_COMMAND_LINE)

    def answer(arguments: tuple[str, ...]) -> AgentInvocationResult:
        verb = arguments[verb_start]
        if verb == "preflight":
            return _document(
                {"api_version": AGENT_COMMAND_LINE_API, "package_version": "1", "stores": _stores(initial)}
            )
        if verb == "stores-state":
            return _document(_stores("current"))
        return _document(_STEP_SUCCEEDED)

    runner = _Recorder(answer)
    image = agent_image(agent_root=tmp_path, received={PACKAGE_AGENT_VARIABLE: str(_agent_executable(tmp_path))})
    AgentStoreLifecycle(
        runner=runner,
        launch=AgentLaunch(image.executable, image.arguments, image.directory, {}),
        command_line=AGENT_COMMAND_LINE,
        aside=_Aside(),
        quiesced=lambda: True,
        deadline=TimeoutDeadline(time.monotonic() + 60),
    ).prepare()
    return runner.calls


def _gateway_and_stores(tmp_path: Path) -> list[Sent]:
    received = {PACKAGE_AGENT_VARIABLE: str(_agent_executable(tmp_path))}
    sent: list[Sent] = [("agent-gateway", agent_image(agent_root=tmp_path, received=received).arguments)]
    calls = [*_store_sequence(tmp_path, "absent"), *_store_sequence(tmp_path, "older")]
    verbs = {call[len(AGENT_COMMAND_LINE)] for call in calls}
    assert verbs == {"preflight", "stores-state", "setup", "migrate"}
    sent.extend(("agent-gateway", call) for call in calls)
    return sent


def _catalog_reads(tmp_path: Path) -> list[Sent]:
    runner = _Recorder()
    source = AgentProviderCatalogSource(
        received={PACKAGE_AGENT_VARIABLE: str(_agent_executable(tmp_path))}, runner=runner
    )
    reads: tuple[Callable[[], object], ...] = (source.catalog, source.sign_in_providers, source.gui_sign_in_methods)
    for read in reads:
        with pytest.raises(ProviderCatalogUnavailableError):
            read()
    assert len(runner.calls) == len(reads)
    return [("agent-providers", call) for call in runner.calls]


def _status_and_sign_out(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[Sent]:
    recorded: list[tuple[str, ...]] = []

    class _Runner(_Recorder):
        def __init__(self, **_ignored: object) -> None:
            super().__init__()
            self.calls = recorded

    monkeypatch.setattr(agent_provider_auth_status, "WindowsAgentInvocationRunner", _Runner)
    monkeypatch.setenv(PACKAGE_AGENT_VARIABLE, str(_agent_executable(tmp_path)))
    probe = AgentProviderAuthStatusProbe(context=lambda: (tmp_path, "key"))
    probe.refresh()
    assert probe.log_out(_PROVIDER, root=tmp_path) is False
    assert len(recorded) == 2
    return [("agent-auth", call) for call in recorded]


def _gui_sign_ins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> list[Sent]:
    captured: list[tuple[str, ...]] = []

    class _Attempt:
        def __init__(self, *, arguments: Sequence[str], **_ignored: object) -> None:
            captured.append(tuple(arguments))

    monkeypatch.setattr(service_startup, "AuthAttempt", _Attempt)
    client = SimpleNamespace(lease=None, connection=SimpleNamespace(close=lambda: None))
    service = AgentService(
        local_engine_default=LocalEngine.LLAMACPP,
        client=cast(InstalledServiceClient, client),
        storage_root=tmp_path,
        gateway_bearer=bytearray(),
        emit=lambda _event: None,
    )
    launch: dict[str, Any] = {"executable": str(_agent_executable(tmp_path)), "directory": str(tmp_path)}
    launch["environment"] = {}
    methods = tuple(str(method) for method in get_args(SignInMethod))
    assert methods
    for method in methods:
        service._new_attempt(
            _PROVIDER, {"entry": {"provider": _PROVIDER}}, method, launch, lambda: True, lambda: (True, None)
        )
    return [("agent-auth", call) for call in captured]


def _console_sign_ins(tmp_path: Path, *, device: bool) -> list[Sent]:
    profile_agent_root(tmp_path, _PROFILE)
    received: Mapping[str, str] = {PACKAGE_AGENT_VARIABLE: str(_agent_executable(tmp_path))}
    providers = DEVICE_PROVIDERS if device else SIGN_IN_PROVIDERS
    return [
        (
            "agent-auth",
            prepare_provider_login(
                storage_root=tmp_path, profile_id=_PROFILE, provider=provider, device=device, received=received
            ).arguments,
        )
        for provider in providers
    ]


@pytest.fixture
def outside_git() -> Iterator[Path]:
    """A folder with no Git project above it: the console sign-in refuses an agent root inside one."""
    system = Path(os.environ["LOCALAPPDATA"]) / "Temp" if sys.platform == "win32" else Path(os.sep, "tmp")
    folder = Path(tempfile.mkdtemp(prefix="cadrumo-invocations-", dir=system)).resolve()
    try:
        assert not any((parent / ".git").exists() for parent in (folder, *folder.parents))
        yield folder
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_the_gateway_and_store_invocations_are_declared_for_the_gateway_profile(tmp_path: Path) -> None:
    findings = _undeclared(load_for_build(REPO_ROOT), _gateway_and_stores(tmp_path))
    assert not findings, findings


def test_the_provider_catalog_reads_are_declared_for_the_providers_profile(tmp_path: Path) -> None:
    findings = _undeclared(load_for_build(REPO_ROOT), _catalog_reads(tmp_path))
    assert not findings, findings


def test_the_sign_in_status_read_is_declared_for_the_auth_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    status, _sign_out = _status_and_sign_out(tmp_path, monkeypatch)
    findings = _undeclared(load_for_build(REPO_ROOT), [status])
    assert not findings, findings


def test_the_sign_out_is_declared_for_the_auth_profile(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _status, sign_out = _status_and_sign_out(tmp_path, monkeypatch)
    findings = _undeclared(load_for_build(REPO_ROOT), [sign_out])
    assert not findings, findings


def test_every_window_sign_in_method_is_declared_for_the_auth_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    findings = _undeclared(load_for_build(REPO_ROOT), _gui_sign_ins(tmp_path, monkeypatch))
    assert not findings, findings


@pytest.mark.parametrize("device", [False, True], ids=["browser", "device"])
def test_the_console_sign_in_is_declared_for_the_auth_profile(outside_git: Path, *, device: bool) -> None:
    findings = _undeclared(load_for_build(REPO_ROOT), _console_sign_ins(outside_git, device=device))
    assert not findings, findings


def test_a_declaration_without_the_causes_flag_leaves_the_sent_status_and_sign_ins_undeclared(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    planted = parse(_SOURCE.replace('  { literal = "--causes" },\n', ""))
    assert planted.invocations != load_for_build(REPO_ROOT).invocations
    sent = [*_status_and_sign_out(tmp_path, monkeypatch), *_gui_sign_ins(tmp_path, monkeypatch)]
    status_and_connects = [entry for entry in sent if "--causes" in entry[1]]
    assert len(status_and_connects) == 1 + len(get_args(SignInMethod))
    findings = _undeclared(planted, status_and_connects)
    assert len(findings) == len(status_and_connects) * len(_FAMILIES)
    assert all("declared []" in finding for finding in findings), findings


def test_a_sent_vector_with_an_extra_argument_is_undeclared(tmp_path: Path) -> None:
    profile, arguments = _catalog_reads(tmp_path)[0]
    declaration = load_for_build(REPO_ROOT)
    assert _undeclared(declaration, [(profile, arguments)]) == []
    assert _undeclared(declaration, [(profile, (*arguments, "--extra"))]) == [
        f"{family}: {[*arguments, '--extra']} needs {profile}, declared []" for family in _FAMILIES
    ]
