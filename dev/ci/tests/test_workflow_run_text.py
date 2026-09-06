"""The executed-lines reader keeps prose out of what a gate judges.

Both directions, because a reader that dropped too much would be the same
defect wearing the other sign: a real command lost to an over-eager comment
rule fails a lane that is fine, and a commented-out command kept fails nothing
at all while the lane it names runs nothing.
"""

from __future__ import annotations

import pytest

from ..workflow_run_text import executed_lines, executed_text

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_a_commented_out_invocation_is_not_executed() -> None:
    """The defect this module exists for, stated as its smallest case."""
    script = "\n".join(
        (
            "# uv run --no-sync python -m dev.packaging.evidence",
            "echo skipped",
        ),
    )

    assert executed_lines(script) == ("echo skipped",)
    assert "dev.packaging.evidence" not in executed_text(script)


def test_the_same_invocation_uncommented_is_executed() -> None:
    """The other direction: the reader must not simply lose the line."""
    script = "\n".join(
        (
            "uv run --no-sync python -m dev.packaging.evidence",
            "echo done",
        ),
    )

    assert executed_lines(script) == (
        "uv run --no-sync python -m dev.packaging.evidence",
        "echo done",
    )
    assert "dev.packaging.evidence" in executed_text(script)


def test_an_indented_comment_is_still_a_comment() -> None:
    """YAML block scalars keep their indentation, so the rule strips first."""
    assert executed_lines("    # just packaging-smoke") == ()


def test_a_hash_that_is_not_a_comment_survives_intact() -> None:
    """A fragment, a colour, or a quoted literal is part of the command.

    Truncating from the first `#` anywhere would silently shorten real
    commands, which is how a narrower rule turns into a different bug.
    """
    command = "gh issue comment 3 --body 'see #412 and colour #ff0000'"

    assert executed_lines(command) == (command,)


def test_blank_lines_are_not_executed_content() -> None:
    """An empty line is neither a command nor evidence that one exists."""
    assert executed_lines("\n\n   \n") == ()


def test_an_absent_run_block_reads_as_executing_nothing() -> None:
    """A step with no `run:` is a normal input, not an error."""
    assert executed_lines(None) == ()
    assert executed_text(None) == ""


def test_a_sequence_of_scripts_joins_under_the_same_rule() -> None:
    """Joining every step in a job must not reintroduce the prose."""
    steps = ("# just packaging-smoke", "just packaging-quick", None)

    assert executed_text(steps) == "just packaging-quick"


def test_a_bare_string_is_one_script_rather_than_its_characters() -> None:
    """The iterable overload must not shred a single `run:` block."""
    assert executed_text("just packaging-quick") == "just packaging-quick"
