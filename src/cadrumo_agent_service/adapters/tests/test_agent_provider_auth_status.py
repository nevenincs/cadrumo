"""The sign-in status probe reports the agent's cause per provider and never keeps a failed read."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, override

import pytest

from ...host.store_lifecycle import AgentInvocationResult
from ...providers.application.contracts import CliState, CliStateCause
from ...providers.application.tests.synthetic_catalog import synthetic_catalog
from .. import agent_provider_auth_status as status_module
from ..agent_programs import AgentImage
from ..agent_provider_auth_status import AgentProviderAuthStatusProbe

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


class _Runner:
    """Answers each invocation from a script of results, recording the arguments it was asked to run."""

    script: list[AgentInvocationResult | BaseException] = []
    calls: list[tuple[str, ...]] = []
    timeouts: list[float] = []

    def __init__(self, **_ignored: Any) -> None:
        self.settled = True

    def run(self, *, arguments: tuple[str, ...], timeout: float, **_ignored: Any) -> AgentInvocationResult:
        type(self).calls.append(tuple(arguments))
        type(self).timeouts.append(timeout)
        step = type(self).script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


def _answer(
    *, states: dict[str, str] | None = None, causes: dict[str, str | None] | None = None, version: int = 2
) -> AgentInvocationResult:
    body = {
        "schema_version": version,
        "providers": states or {"claude": "installed_signed_out", "codex": "installed_signed_in"},
        "causes": causes or {"claude": "cli_not_found", "codex": None},
    }
    return AgentInvocationResult(status=0, standard_output=json.dumps(body).encode())


@pytest.fixture
def probe(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> AgentProviderAuthStatusProbe:
    _Runner.script, _Runner.calls, _Runner.timeouts = [], [], []
    monkeypatch.setattr(status_module, "WindowsAgentInvocationRunner", _Runner)
    monkeypatch.setattr(status_module, "agent_image", lambda **_k: AgentImage(tmp_path / "agent.exe", (), tmp_path))
    monkeypatch.setattr(status_module, "hosted_python", lambda: None)
    return AgentProviderAuthStatusProbe(context=lambda: (tmp_path, "key"))


def _lane_named(provider: str, _monkeypatch: pytest.MonkeyPatch | None = None) -> Any:
    entry = synthetic_catalog().entry("example_cli")
    assert entry is not None
    return entry.model_copy(update={"provider": provider})


def test_schema_two_gives_each_provider_its_state_and_cause(
    probe: AgentProviderAuthStatusProbe, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Runner.script = [_answer()]
    claude = probe.probe(_lane_named("claude", monkeypatch))
    codex = probe.probe(_lane_named("codex", monkeypatch))
    other = probe.probe(_lane_named("antigravity", monkeypatch))
    assert (claude.state, claude.cause) == (CliState.INSTALLED_SIGNED_OUT, CliStateCause.CLI_NOT_FOUND)
    assert (codex.state, codex.cause) == (CliState.INSTALLED_SIGNED_IN, None)
    assert (other.state, other.cause) == (CliState.UNKNOWN, None)
    assert _Runner.calls == [("-m", "cadrumo_agent.cli.main", "auth", "status", "--json", "--causes")]


@pytest.mark.parametrize(
    "result",
    [
        _answer(version=1),
        AgentInvocationResult(status=0, standard_output=b"not json"),
        AgentInvocationResult(status=0, standard_output=b'{"schema_version":2,"providers":{},"causes":{"x":"bogus"}}'),
        AgentInvocationResult(status=0, standard_output=b'{"schema_version":2,"providers":{},"extra":1}'),
    ],
    ids=["schema_one", "bad_json", "unknown_cause_word", "extra_field"],
)
def test_an_answer_that_does_not_parse_is_status_unreadable_and_is_not_kept(
    probe: AgentProviderAuthStatusProbe, monkeypatch: pytest.MonkeyPatch, result: AgentInvocationResult
) -> None:
    _Runner.script = [result, _answer()]
    lane = _lane_named("codex", monkeypatch)
    failed = probe.probe(lane)
    assert (failed.state, failed.cause) == (CliState.UNKNOWN, CliStateCause.STATUS_UNREADABLE)
    recovered = probe.probe(lane)
    assert (recovered.state, recovered.cause) == (CliState.INSTALLED_SIGNED_IN, None)
    assert len(_Runner.calls) == 2


@pytest.mark.parametrize(
    "step",
    [
        AgentInvocationResult(status=2, standard_output=b""),
        AgentInvocationResult(status=None, standard_output=b""),
        OSError("PRIVATE"),
    ],
    ids=["nonzero_exit", "ended_at_bound", "os_error"],
)
def test_a_failed_read_is_status_read_failed_and_the_next_probe_reads_again(
    probe: AgentProviderAuthStatusProbe, monkeypatch: pytest.MonkeyPatch, step: AgentInvocationResult | BaseException
) -> None:
    _Runner.script = [step, _answer()]
    lane = _lane_named("codex", monkeypatch)
    failed = probe.probe(lane)
    assert (failed.state, failed.cause) == (CliState.UNKNOWN, CliStateCause.STATUS_READ_FAILED)
    assert probe.probe(lane).state is CliState.INSTALLED_SIGNED_IN


def test_a_good_read_is_kept_until_the_cache_is_dropped(
    probe: AgentProviderAuthStatusProbe, monkeypatch: pytest.MonkeyPatch
) -> None:
    _Runner.script = [_answer(), _answer(states={"codex": "installed_signed_out"}, causes={"codex": None})]
    lane = _lane_named("codex", monkeypatch)
    assert probe.probe(lane).state is CliState.INSTALLED_SIGNED_IN
    assert probe.probe(lane).state is CliState.INSTALLED_SIGNED_IN
    assert len(_Runner.calls) == 1
    probe.forget()
    assert probe.probe(lane).state is CliState.INSTALLED_SIGNED_OUT
    assert len(_Runner.calls) == 2


def test_a_read_begun_before_the_cache_was_dropped_is_not_kept(
    probe: AgentProviderAuthStatusProbe, monkeypatch: pytest.MonkeyPatch
) -> None:
    lane = _lane_named("codex", monkeypatch)
    forgetting: Callable[[], None] = probe.forget

    class _Dropping(_Runner):
        @override
        def run(self, **kwargs: Any) -> AgentInvocationResult:
            forgetting()
            return super().run(**kwargs)

    monkeypatch.setattr(status_module, "WindowsAgentInvocationRunner", _Dropping)
    _Runner.script = [_answer(), _answer()]
    probe.probe(lane)
    probe.probe(lane)
    assert len(_Runner.calls) == 2


def test_a_confirmation_reads_fresh_within_its_own_budget_and_keeps_nothing(
    probe: AgentProviderAuthStatusProbe, tmp_path: Path
) -> None:
    _Runner.script = [_answer(), _answer(states={"codex": "installed_signed_out"}, causes={"codex": None})]
    first = probe.confirm("codex", root=tmp_path)
    second = probe.confirm("codex", root=tmp_path)
    assert first.state is CliState.INSTALLED_SIGNED_IN
    assert second.state is CliState.INSTALLED_SIGNED_OUT
    assert max(_Runner.timeouts) <= 20


def test_a_confirmation_that_cannot_read_names_the_failure(probe: AgentProviderAuthStatusProbe, tmp_path: Path) -> None:
    _Runner.script = [AgentInvocationResult(status=1, standard_output=b"")]
    observed = probe.confirm("codex", root=tmp_path)
    assert (observed.state, observed.cause) == (CliState.UNKNOWN, CliStateCause.STATUS_READ_FAILED)


class _UnsettledRunner(_Runner):
    """A runner whose supplier scope is not confirmed gone until it is settled."""

    instances: list[_UnsettledRunner] = []

    def __init__(self, **_ignored: Any) -> None:
        super().__init__()
        self.settled = False
        type(self).instances.append(self)

    def settle(self) -> None:
        self.settled = True


def test_a_runner_left_unsettled_refuses_later_reads_until_close_settles_it(
    probe: AgentProviderAuthStatusProbe, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _UnsettledRunner.instances = []
    monkeypatch.setattr(status_module, "WindowsAgentInvocationRunner", _UnsettledRunner)
    _Runner.script = [_answer()]
    first = probe.confirm("codex", root=tmp_path)
    second = probe.confirm("codex", root=tmp_path)
    assert first.state is CliState.INSTALLED_SIGNED_IN
    assert (second.state, second.cause) == (CliState.UNKNOWN, CliStateCause.STATUS_READ_FAILED)
    assert len(_Runner.calls) == 1
    assert len(_UnsettledRunner.instances) == 1
    probe.close()
    assert _UnsettledRunner.instances[0].settled
