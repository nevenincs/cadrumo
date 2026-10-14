"""The store sequence before a hosted gateway starts: which invocation runs, what is copied, what is refused.

The runner and the copy are replaced by scripted stand-ins that record how they
were asked, so the sequence's decisions are isolated here. The real contained
invocations, the real copy and the runtime door are exercised by the Windows
integration tests.
"""

from __future__ import annotations

import copy
import json
import logging
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

from ..controller import AgentHostError, AgentHostRefusal, AgentLaunch
from ..launcher_protocol import AgentLauncherRefusal, launcher_refusal_for
from ..store_lifecycle import STORE_OUTPUT_MAX_BYTES, AgentInvocationResult, AgentStoreLifecycle, StoreLifecycleBounds

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_COMMAND_LINE = ("-m", "agent.cli")
_LAUNCH = AgentLaunch(
    executable=Path("/image/bin/agent"),
    arguments=(*_COMMAND_LINE, "serve"),
    directory=Path("/root/agent/opaque"),
    environment={"ROOT_SLOT": "/root/agent/opaque"},
)
_BOUNDS = StoreLifecycleBounds(version=1.0, stores_state=2.0, setup=3.0, migrate=4.0)
_LOGGER_NAME = "cadrumo_agent_service.host.store_lifecycle"
_AGENT_DETAIL = "AGENT-DETAIL-TEXT"
_HOME = "/private/home/of/the/agent"


def _judgement(state: str, found: object, expected: object) -> dict[str, object]:
    return {"state": state, "found": found, "expected": expected}


def _state(state: str, *, found: object = "0001", expected: object = "0002") -> dict[str, object]:
    primary_state = state if state != "absent" else "absent"
    return {
        "state": state,
        "primary": _judgement(primary_state, None if state == "absent" else found, expected),
        "checkpoint": _judgement("current", "1.0.0", "1.0.0"),
    }


def _step(status: str, *, stage: str | None = None) -> dict[str, object]:
    return {
        "status": status,
        "target_head": "0002",
        "stores": [
            {
                "store": "primary",
                "status": "failed" if stage is not None else "migrated",
                "from_revision": "0001",
                "to_revision": "0002",
                "schema_version": None,
            }
        ],
        "duration_seconds": 0.5,
        "failed_stage": stage,
        "error_class": "MigrationError" if stage is not None else None,
        "detail": f"{_AGENT_DETAIL} in {_HOME}" if stage is not None else None,
        "app_home": _HOME,
    }


_VERSION = {"api_version": "v1", "package_version": "1.2.3"}


def _out(document: object, status: int | None = 0) -> AgentInvocationResult:
    return AgentInvocationResult(status=status, standard_output=json.dumps(document, indent=2).encode())


class _Runner:
    """Answers each verb from a script, in order, and records every call."""

    def __init__(self, answers: Mapping[str, list[AgentInvocationResult] | Exception]) -> None:
        self._answers = {
            verb: answer if isinstance(answer, Exception) else list(answer) for verb, answer in answers.items()
        }
        self.calls: list[tuple[str, ...]] = []
        self.timeouts: list[float] = []

    def run(
        self,
        *,
        executable: Path,
        arguments: Sequence[str],
        directory: Path,
        environment: Mapping[str, str],
        timeout: float,
        output_limit: int,
    ) -> AgentInvocationResult:
        assert executable == _LAUNCH.executable
        assert directory == _LAUNCH.directory
        assert environment == _LAUNCH.environment
        assert output_limit == STORE_OUTPUT_MAX_BYTES
        assert tuple(arguments[: len(_COMMAND_LINE)]) == _COMMAND_LINE
        verb = tuple(arguments[len(_COMMAND_LINE) :])
        self.calls.append(verb)
        self.timeouts.append(timeout)
        answer = self._answers[verb[0]]
        if isinstance(answer, Exception):
            raise answer
        return answer.pop(0)


class _Aside:
    def __init__(self, *, kept: bool = False, keep_error: OSError | None = None) -> None:
        self.copy = kept
        self.actions: list[str] = []
        self._keep_error = keep_error

    def clear_partial(self) -> None:
        self.actions.append("clear_partial")

    def kept(self) -> bool:
        return self.copy

    def keep(self) -> None:
        self.actions.append("keep")
        if self._keep_error is not None:
            raise self._keep_error
        self.copy = True

    def discard(self) -> None:
        self.actions.append("discard")
        self.copy = False


def _lifecycle(runner: _Runner, aside: _Aside, *, quiesced: bool = True) -> AgentStoreLifecycle:
    return AgentStoreLifecycle(
        runner=runner,
        launch=_LAUNCH,
        command_line=_COMMAND_LINE,
        aside=aside,
        quiesced=lambda: quiesced,
        bounds=_BOUNDS,
    )


def _refusal(lifecycle: AgentStoreLifecycle) -> AgentHostError:
    with pytest.raises(AgentHostError) as raised:
        lifecycle.prepare()
    return raised.value


def test_current_stores_run_nothing_but_the_two_reads() -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("current", found="0002"))]})
    aside = _Aside()
    _lifecycle(runner, aside).prepare()
    assert runner.calls == [("version", "--json"), ("stores-state",)]
    assert runner.timeouts == [_BOUNDS.version, _BOUNDS.stores_state]
    assert aside.actions == ["clear_partial"]


@pytest.mark.parametrize("status", ["succeeded", "already-initialized"])
def test_absent_stores_are_set_up_then_must_read_current(status: str) -> None:
    runner = _Runner(
        {
            "version": [_out(_VERSION)],
            "stores-state": [_out(_state("absent")), _out(_state("current", found="0002"))],
            "setup": [_out(_step(status))],
        }
    )
    aside = _Aside()
    _lifecycle(runner, aside).prepare()
    assert runner.calls == [("version", "--json"), ("stores-state",), ("setup",), ("stores-state",)]
    assert runner.timeouts[2] == _BOUNDS.setup
    assert aside.actions == ["clear_partial"]


def test_older_stores_are_copied_aside_before_the_asserted_migrate_and_the_copy_goes_once_current() -> None:
    runner = _Runner(
        {
            "version": [_out(_VERSION)],
            "stores-state": [_out(_state("older")), _out(_state("current", found="0002"))],
            "migrate": [_out(_step("succeeded"))],
        }
    )
    aside = _Aside()
    _lifecycle(runner, aside).prepare()
    assert runner.calls == [
        ("version", "--json"),
        ("stores-state",),
        ("migrate", "--expect-from", "0001", "--expect-head", "0002"),
        ("stores-state",),
    ]
    assert runner.timeouts[2] == _BOUNDS.migrate
    assert aside.actions == ["clear_partial", "keep", "discard"]


def test_older_stores_are_not_migrated_while_the_profile_is_not_quiet() -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("older"))]})
    aside = _Aside()
    error = _refusal(_lifecycle(runner, aside, quiesced=False))
    assert error.reason is AgentHostRefusal.STORES_UNPREPARED
    assert runner.calls == [("version", "--json"), ("stores-state",)]
    assert aside.actions == ["clear_partial"]


def test_a_copy_that_cannot_be_taken_stops_the_migrate() -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("older"))]})
    aside = _Aside(keep_error=OSError("disk full"))
    assert _refusal(_lifecycle(runner, aside)).reason is AgentHostRefusal.STORES_UNPREPARED
    assert ("migrate",) not in [call[:1] for call in runner.calls]


@pytest.mark.parametrize(
    "result",
    [
        pytest.param(_out(_step("failed", stage="checkpoint"), status=1), id="failed"),
        pytest.param(AgentInvocationResult(status=None, standard_output=b""), id="timed-out"),
        pytest.param(_out(_step("succeeded"), status=1), id="status-disagrees"),
        pytest.param(AgentInvocationResult(status=3, standard_output=b""), id="other-exit"),
    ],
)
def test_a_migrate_that_did_not_succeed_keeps_the_copy_and_is_not_retried(
    result: AgentInvocationResult, caplog: pytest.LogCaptureFixture
) -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("older"))], "migrate": [result]})
    aside = _Aside()
    with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
        error = _refusal(_lifecycle(runner, aside))
    assert error.reason is AgentHostRefusal.STORES_UNPREPARED
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_FAILED
    assert [call[0] for call in runner.calls] == ["version", "stores-state", "migrate"]
    assert aside.actions == ["clear_partial", "keep"]
    assert aside.copy
    # The agent's text and its home's path never reach a diagnostic.
    assert _AGENT_DETAIL not in caplog.text
    assert _HOME not in caplog.text


def test_a_kept_copy_over_stores_that_are_not_current_refuses_every_later_start() -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("older"))]})
    aside = _Aside(kept=True)
    assert _refusal(_lifecycle(runner, aside)).reason is AgentHostRefusal.STORES_UNPREPARED
    assert runner.calls == [("version", "--json"), ("stores-state",)]
    assert aside.actions == ["clear_partial"]
    assert aside.copy


def test_a_kept_copy_is_removed_once_the_stores_read_current() -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("current", found="0002"))]})
    aside = _Aside(kept=True)
    _lifecycle(runner, aside).prepare()
    assert aside.actions == ["clear_partial", "discard"]
    assert not aside.copy


@pytest.mark.parametrize("found", ["0003", None])
def test_newer_stores_are_a_downgrade_and_refused_as_incompatible(found: str | None) -> None:
    # An unreadable primary store reports newer with nothing found.
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("newer", found=found))]})
    aside = _Aside()
    error = _refusal(_lifecycle(runner, aside))
    assert error.reason is AgentHostRefusal.STORES_NEWER
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_INCOMPATIBLE
    assert runner.calls == [("version", "--json"), ("stores-state",)]


def test_another_command_line_contract_is_incompatible() -> None:
    runner = _Runner({"version": [_out({"api_version": "v2", "package_version": "9.0.0"})]})
    error = _refusal(_lifecycle(runner, _Aside()))
    assert error.reason is AgentHostRefusal.AGENT_INCOMPATIBLE
    assert launcher_refusal_for(error) is AgentLauncherRefusal.SERVICE_INCOMPATIBLE
    assert runner.calls == [("version", "--json")]


@pytest.mark.parametrize(
    "status",
    [
        pytest.param(_out(_step("failed", stage="primary"), status=1), id="failed"),
        pytest.param(_out(_step("failed", stage="primary"), status=0), id="exit-zero-but-failed"),
        pytest.param(AgentInvocationResult(status=None, standard_output=b""), id="timed-out"),
    ],
)
def test_a_setup_that_did_not_succeed_is_refused_without_a_recheck(status: AgentInvocationResult) -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("absent"))], "setup": [status]})
    assert _refusal(_lifecycle(runner, _Aside())).reason is AgentHostRefusal.STORES_UNPREPARED
    assert [call[0] for call in runner.calls] == ["version", "stores-state", "setup"]


def test_a_recheck_that_is_not_current_is_refused() -> None:
    runner = _Runner(
        {
            "version": [_out(_VERSION)],
            "stores-state": [_out(_state("absent")), _out(_state("older"))],
            "setup": [_out(_step("succeeded"))],
        }
    )
    assert _refusal(_lifecycle(runner, _Aside())).reason is AgentHostRefusal.STORES_UNPREPARED


def test_an_invocation_that_cannot_run_is_refused() -> None:
    runner = _Runner({"version": OSError("no image")})
    assert _refusal(_lifecycle(runner, _Aside())).reason is AgentHostRefusal.STORES_UNPREPARED


def _with(document: dict[str, object], path: tuple[str | int, ...], value: object) -> dict[str, object]:
    """A copy of the document with one value, at this path of keys and list positions, replaced or added."""
    copied = copy.deepcopy(document)
    target: object = copied
    for key in path[:-1]:
        target = target[key] if isinstance(target, list) and isinstance(key, int) else _member(target, key)
    last = path[-1]
    if isinstance(target, list) and isinstance(last, int):
        target[last] = value
    else:
        assert isinstance(target, dict)
        assert isinstance(last, str)
        target[last] = value
    return copied


def _member(target: object, key: str | int) -> object:
    assert isinstance(target, dict)
    return target[key]


_MALFORMED_STATES = {
    "integer-revision": _with(_state("current", found="0002"), ("primary", "found"), 2),
    "float-revision": _with(_state("current", found="0002"), ("primary", "expected"), 2.0),
    "boolean-revision": _with(_state("current", found="0002"), ("checkpoint", "found"), True),
    "extra-key": _with(_state("current", found="0002"), ("extra",), "x"),
    "nested-extra-key": _with(_state("current", found="0002"), ("primary", "extra"), "x"),
    "unknown-state": _with(_state("current", found="0002"), ("state",), "mixed"),
    "missing-key": {"state": "current", "primary": _judgement("current", "0002", "0002")},
}


@pytest.mark.parametrize("document", list(_MALFORMED_STATES.values()), ids=list(_MALFORMED_STATES))
def test_a_stores_state_that_is_not_exactly_the_agents_shape_is_refused(document: dict[str, object]) -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(document)]})
    assert _refusal(_lifecycle(runner, _Aside())).reason is AgentHostRefusal.STORES_UNPREPARED
    assert runner.calls == [("version", "--json"), ("stores-state",)]


@pytest.mark.parametrize(
    "output",
    [
        pytest.param(b"not json", id="not-json"),
        pytest.param(b"", id="empty"),
        pytest.param(json.dumps(_state("current")).encode() * 2, id="two-objects"),
        pytest.param(b" " * (STORE_OUTPUT_MAX_BYTES + 1), id="oversize"),
    ],
)
def test_stores_state_output_that_is_not_one_bounded_object_is_refused(output: bytes) -> None:
    runner = _Runner(
        {"version": [_out(_VERSION)], "stores-state": [AgentInvocationResult(status=0, standard_output=output)]}
    )
    assert _refusal(_lifecycle(runner, _Aside())).reason is AgentHostRefusal.STORES_UNPREPARED


@pytest.mark.parametrize(
    "document",
    [
        pytest.param(_with(_step("succeeded"), ("stores", 0, "to_revision"), 2), id="integer-revision"),
        pytest.param(_with(_step("succeeded"), ("duration_seconds",), "0.5"), id="text-duration"),
        pytest.param(_with(_step("succeeded"), ("status",), "done"), id="unknown-status"),
        pytest.param(_with(_step("succeeded"), ("unexpected",), None), id="extra-key"),
        pytest.param(_with(_step("succeeded"), ("failed_stage",), "elsewhere"), id="unknown-stage"),
    ],
)
def test_a_setup_report_that_is_not_exactly_the_agents_shape_is_refused(document: dict[str, object]) -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("absent"))], "setup": [_out(document)]})
    assert _refusal(_lifecycle(runner, _Aside())).reason is AgentHostRefusal.STORES_UNPREPARED
    assert [call[0] for call in runner.calls] == ["version", "stores-state", "setup"]


@pytest.mark.parametrize("found", ["--compact", "", "0001 --compact", "x" * 65])
def test_a_reported_revision_that_could_read_as_an_option_is_never_passed_back(found: str) -> None:
    runner = _Runner({"version": [_out(_VERSION)], "stores-state": [_out(_state("older", found=found))]})
    aside = _Aside()
    assert _refusal(_lifecycle(runner, aside)).reason is AgentHostRefusal.STORES_UNPREPARED
    assert aside.actions == ["clear_partial"]
    assert runner.calls == [("version", "--json"), ("stores-state",)]
