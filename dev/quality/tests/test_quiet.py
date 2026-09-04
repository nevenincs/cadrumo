"""Tests for the quiet command wrapper.

`dev.quality.module_test_reach` listed `dev/quality/quiet.py` as unreached. It is
the primitive every gate in the harness runs through: it swallows a passing
tool's chatter and replays a failing tool's output verbatim, so what it does
with a failure IS the failure report CI keeps.

Two things it did badly. An absent or unrunnable command raised ``OSError`` out
of it, so a mistyped tool in a recipe produced a traceback whose last line is a
Windows error number - naming neither the tool nor the recipe. And its
no-command diagnostic named ``quiet_ok.py``, a file that does not exist in this
tree, sending anyone who greps for it nowhere.

It also read ``sys.argv`` directly, which left the wrapper reachable only by
launching a process. It now takes its arguments, and these cases drive it in
process against real commands.
"""

from __future__ import annotations

import sys

import pytest

from ..quiet import main

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _python(*code: str) -> list[str]:
    return [sys.executable, "-c", chr(10).join(code)]


def test_a_passing_command_says_nothing(capsys: pytest.CaptureFixture[str]) -> None:
    """Green must be silent; that is the entire point of the wrapper."""
    exit_code = main(_python("print('chatty success')"))

    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == ""
    assert captured.err == ""


def test_a_failing_command_has_its_output_replayed(capsys: pytest.CaptureFixture[str]) -> None:
    """A suppressed failure would be worse than no wrapper at all."""
    exit_code = main(
        _python(
            "import sys",
            "print('what went wrong')",
            "print('and the detail', file=sys.stderr)",
            "sys.exit(3)",
        )
    )

    captured = capsys.readouterr()
    assert exit_code == 3, "the tool's own exit code must survive the wrapper"
    assert "what went wrong" in captured.out
    assert "and the detail" in captured.err


def test_the_exit_code_is_propagated_rather_than_normalised() -> None:
    """Recipes branch on these, so collapsing them to 1 loses the distinction."""
    assert main(_python("import sys; sys.exit(42)")) == 42


def test_an_absent_command_is_refused_by_name(capsys: pytest.CaptureFixture[str]) -> None:
    """The defect: this escaped as a traceback ending in a bare error number.

    The wrapper is what a recipe invokes, so it is the only place that still
    knows which command was asked for.
    """
    exit_code = main(["a-tool-that-is-not-installed-anywhere"])

    captured = capsys.readouterr()
    assert exit_code == 127
    assert "a-tool-that-is-not-installed-anywhere" in captured.err
    assert "Traceback" not in captured.err


def test_no_command_at_all_is_refused_with_the_right_file_name(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The diagnostic named a file that does not exist in this tree.

    A reader grepping the message for its source found nothing, which is the
    one thing a diagnostic must not do.
    """
    exit_code = main([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "quiet: no command given" in captured.err
    assert "quiet_ok" not in captured.err


def test_non_ascii_tool_output_survives_the_replay(capsys: pytest.CaptureFixture[str]) -> None:
    """The module's own recorded failure: a cp1252 console killed the replay.

    Ruff and import-linter emit box drawing and accented excerpts, and a replay
    that raises while reporting a failure turns a real finding into a crash in
    the reporter.
    """
    exit_code = main(
        _python(
            "import sys",
            "print('contrato roto \\u2192 capa')",
            "sys.exit(1)",
        )
    )

    assert exit_code == 1
    assert "capa" in capsys.readouterr().out
