"""Unit tests for the CLI exit-code table."""

from __future__ import annotations

import pytest
import typer

from ... import cli

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


def test_exit_code_values_are_stable() -> None:
    """The exact numeric exit-code mapping is a compatibility contract."""

    assert {code.name: int(code) for code in cli.ExitCode} == {
        "SUCCESS": 0,
        "ERROR": 1,
        "REFUSED": 2,
        "AUTH": 3,
        "INTEGRITY": 4,
        "FAIL": 5,
        "INTERNAL": 6,
        "LOCKED_BY_DESIGN": 7,
        "LOCKED_BY_CONCURRENCY": 8,
        "NO_NETWORK": 10,
        "USAGE": 20,
    }


def test_exit_with_emits_message_to_stderr_and_raises(capsys: pytest.CaptureFixture[str]) -> None:
    """``exit_with`` should standardize stderr emission before exiting."""

    with pytest.raises(typer.Exit) as excinfo:
        cli.exit_with(cli.ExitCode.REFUSED, message="interactive stdin required")

    captured = capsys.readouterr()
    assert excinfo.value.exit_code == int(cli.ExitCode.REFUSED)
    assert captured.err.strip() == "interactive stdin required"
