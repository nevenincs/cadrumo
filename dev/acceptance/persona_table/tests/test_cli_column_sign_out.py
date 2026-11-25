"""The CLI column signs the profile it served out through the person's own command before the runtime is drained.

The installed CLI here is a recording stand-in for the ``aeat`` process only: it answers each command with an envelope
of the shape the backend prints. What is under test is which command the runner sends, with the passphrase on which
channel, in which order against the runtime's drain, and that a sign-out that fails is reported and never raised.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from typing import Any

import pytest

from cadrumo.entrypoints.tests.persona_world import PERSONA_PROFILE_CREDENTIAL

from ..cli_column.case import with_sign_out_findings
from ..cli_column.driver import CaseSummary
from ..cli_column.intake import Kind, Outcome
from ..cli_column.runtime import SIGN_OUT_FAILED_CODE, CliRunner, SignOut, signing_out

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


_OK = {"status": "success", "result": {"logged_out_profile": "persona"}}


def _refused() -> dict[str, Any]:
    return {"status": "error", "error": {"code": "REFUSED_PROFILE_SESSION", "message": "no", "category": "refused"}}


class _Cli:
    """Records every command; the answer of a command is chosen by ``answer``, which may also raise."""

    def __init__(self, events: list[str], answer: Callable[[Sequence[str]], dict[str, Any]] | None = None) -> None:
        self.passphrase = PERSONA_PROFILE_CREDENTIAL
        self.events = events
        self.calls: list[tuple[tuple[str, ...], bool, str | None]] = []
        self._answer = answer or (lambda _args: _OK)

    def run(
        self, args: Sequence[str], *, authenticated: bool, allow_error: bool, stdin_payload: str | None = None
    ) -> dict[str, Any]:
        assert allow_error
        self.calls.append((tuple(args), authenticated, stdin_payload))
        self.events.append("command " + " ".join(args[:3]))
        return self._answer(args)


def _logouts(cli: _Cli) -> list[tuple[tuple[str, ...], bool, str | None]]:
    return [call for call in cli.calls if call[0][:2] == ("config", "logout")]


def test_a_profile_a_command_carried_the_passphrase_for_is_signed_out_with_the_persons_command() -> None:
    cli = _Cli([])
    runner = CliRunner(cli)

    runner(("--profile", "persona", "app", "modelo", "work", "list"))
    made = runner.sign_out_all()

    assert [(call[0], call[1]) for call in _logouts(cli)] == [
        (("config", "logout", "persona", "--secrets-stdin"), False)
    ]
    assert json.loads(_logouts(cli)[0][2] or "") == {"passphrase": PERSONA_PROFILE_CREDENTIAL}
    assert [sign_out.profile for sign_out in made] == ["persona"]
    assert made[0].outcome.kind is Kind.OK and made[0].finding is None
    assert runner.sign_outs == made


def test_the_passphrase_never_travels_in_the_command_line() -> None:
    cli = _Cli([])
    runner = CliRunner(cli)
    runner(("--profile", "persona", "app", "modelo", "work", "list"))

    runner.sign_out_all()

    assert all(PERSONA_PROFILE_CREDENTIAL not in " ".join(call[0]) for call in cli.calls)


def test_a_profile_is_signed_out_once_however_many_commands_used_it() -> None:
    cli = _Cli([])
    runner = CliRunner(cli)

    for _ in range(3):
        runner(("--profile", "persona", "app", "modelo", "work", "list"))
    runner.sign_out_all()
    second = runner.sign_out_all()

    assert len(_logouts(cli)) == 1
    assert second == []


def test_commands_without_the_passphrase_sign_nothing_in_and_so_nothing_out() -> None:
    cli = _Cli([])
    runner = CliRunner(cli)

    runner(("config", "profile", "list"), authenticated=False)

    assert runner.sign_out_all() == []
    assert len(cli.calls) == 1


def test_a_passphrase_command_that_names_no_profile_signs_out_the_selected_one() -> None:
    cli = _Cli([])
    runner = CliRunner(cli)

    runner(("app", "modelo", "work", "list"))
    runner.sign_out_all()

    assert [call[0] for call in _logouts(cli)] == [("config", "logout", "--secrets-stdin")]


def test_each_profile_that_was_used_is_signed_out() -> None:
    cli = _Cli([])
    runner = CliRunner(cli)

    runner(("--profile", "first", "app", "modelo", "work", "list"))
    runner(("--profile", "second", "app", "modelo", "work", "list"))
    runner.sign_out_all()

    assert [call[0][2] for call in _logouts(cli)] == ["first", "second"]


def test_a_refused_sign_out_is_a_typed_finding_and_does_not_raise() -> None:
    cli = _Cli([], lambda args: _refused() if args[:2] == ("config", "logout") else _OK)
    runner = CliRunner(cli)
    runner(("--profile", "persona", "app", "modelo", "work", "list"))

    made = runner.sign_out_all()

    assert made[0].outcome.kind is Kind.REFUSED
    assert made[0].outcome.code == "REFUSED_PROFILE_SESSION"
    finding = made[0].finding
    assert finding is not None
    assert "config logout persona" in finding
    assert "refused" in finding
    assert "REFUSED_PROFILE_SESSION" in finding
    assert PERSONA_PROFILE_CREDENTIAL not in finding


@pytest.mark.parametrize(
    "failure",
    [
        OSError("the launcher is gone"),
        subprocess.TimeoutExpired("aeat", 180),
        subprocess.SubprocessError("broken"),
    ],
)
def test_a_sign_out_that_cannot_run_is_reported_and_does_not_raise(failure: BaseException) -> None:
    def answer(args: Sequence[str]) -> dict[str, Any]:
        if args[:2] == ("config", "logout"):
            raise failure
        return _OK

    runner = CliRunner(_Cli([], answer))
    runner(("--profile", "persona", "app", "modelo", "work", "list"))

    made = runner.sign_out_all()

    assert made[0].outcome.kind in {Kind.ERROR, Kind.UNKNOWN}
    assert made[0].finding is not None


def test_a_launcher_failure_is_named_by_its_type_alone() -> None:
    def answer(args: Sequence[str]) -> dict[str, Any]:
        if args[:2] == ("config", "logout"):
            raise OSError(f"cannot start with {PERSONA_PROFILE_CREDENTIAL}")
        return _OK

    runner = CliRunner(_Cli([], answer))
    runner(("--profile", "persona", "app", "modelo", "work", "list"))

    outcome = runner.sign_out_all()[0].outcome

    assert outcome.code == SIGN_OUT_FAILED_CODE
    assert outcome.reason == "OSError"


@contextmanager
def _host(events: list[str]) -> Generator[None]:
    """Stands for the caller-owned runtime: it records when it is drained."""
    events.append("runtime started")
    try:
        yield
    finally:
        events.append("runtime drained")


def test_the_sign_out_happens_while_the_runtime_still_serves_and_before_it_is_drained() -> None:
    events: list[str] = []
    cli = _Cli(events)

    with _host(events), signing_out(CliRunner(cli)) as runner:
        runner(("--profile", "persona", "app", "modelo", "work", "list"))

    assert events == [
        "runtime started",
        "command --profile persona app",
        "command config logout persona",
        "runtime drained",
    ]


def test_a_body_that_fails_still_signs_out_before_the_drain_and_its_error_is_kept() -> None:
    events: list[str] = []
    cli = _Cli(events)

    with pytest.raises(RuntimeError, match="the case failed"), _host(events), signing_out(CliRunner(cli)) as runner:
        runner(("--profile", "persona", "app", "modelo", "work", "list"))
        raise RuntimeError("the case failed")

    assert events[-2:] == ["command config logout persona", "runtime drained"]


def test_a_failing_sign_out_neither_hides_the_body_nor_skips_the_drain() -> None:
    events: list[str] = []
    cli = _Cli(events, lambda args: _refused() if args[:2] == ("config", "logout") else _OK)
    with _host(events), signing_out(CliRunner(cli)) as runner:
        runner(("--profile", "persona", "app", "modelo", "work", "list"))

    assert events[-1] == "runtime drained"
    assert runner.sign_outs[0].outcome.kind is Kind.REFUSED


def test_a_failed_sign_out_becomes_a_note_of_the_case_and_every_sign_out_is_traced() -> None:
    traced: list[tuple[str, Outcome]] = []
    summary = CaseSummary(written=(("100", 2022, "0A"),), notes=("kept",))
    refused = SignOut("persona", Outcome(Kind.REFUSED, "REFUSED_PROFILE_SESSION", "no"))
    done = SignOut("other", Outcome(Kind.OK))

    result = with_sign_out_findings(summary, [refused, done], lambda label, outcome: traced.append((label, outcome)))

    assert [label for label, _ in traced] == ["config logout", "config logout"]
    assert [outcome.kind for _, outcome in traced] == [Kind.REFUSED, Kind.OK]
    assert result.written == summary.written
    assert result.notes[0] == "kept"
    assert len(result.notes) == 2
    assert "config logout persona" in result.notes[1]


def test_a_case_whose_sign_outs_all_succeeded_is_returned_as_it_was() -> None:
    summary = CaseSummary(notes=("kept",))

    result = with_sign_out_findings(summary, [SignOut("persona", Outcome(Kind.OK))], lambda _label, _outcome: None)

    assert result is summary
