"""Dead-code report shape and parsing over synthetic-free, real captured output.

In-process checks only: the parser reads a real captured vulture run
(literal text, not synthesised), and the typed result/renderer are exercised
directly. Split from the live-scan half so each module carries one execution
lane -- the gate that actually runs vulture over the tree lives in
``test_dead_code_scan``.
"""

from __future__ import annotations

import pytest

from ..dead_code import (
    DeadCodeOutcome,
    DeadCodeResult,
    parse_vulture_output,
    render_console_report,
    vulture_command,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# A real captured two-finding vulture run against this tree.
_CAPTURED_STDOUT = (
    "src\\cadrumo\\application\\review\\_operator.py:256: unreachable code after 'if' (100% confidence)\n"
    "src\\cadrumo\\application\\storage\\calc_sheets\\_parity_harness.py:94: "
    "unused variable 'cache_discovery' (100% confidence)\n"
)


def test_command_targets_the_configured_paths() -> None:
    """The command matches today's `just audit-dead-code` invocation exactly."""
    command = vulture_command()

    assert command == [
        "uv",
        "run",
        "--no-sync",
        "vulture",
        "--config",
        "pyproject.toml",
        "src/cadrumo",
        "dev/audit/vulture_whitelist.py",
    ]


def test_parse_vulture_output_reads_real_captured_lines() -> None:
    """The parser reads vulture's real path:line: message (NN% confidence) shape."""
    findings = parse_vulture_output(_CAPTURED_STDOUT)

    assert len(findings) == 2
    first = findings[0]
    assert first.path == "src/cadrumo/application/review/operator.py"
    assert first.line == 256
    assert first.message == "unreachable code after 'if'"
    assert first.confidence == 100


def test_parse_vulture_output_normalises_windows_paths() -> None:
    """Backslash paths (native vulture output on Windows) become POSIX."""
    findings = parse_vulture_output(_CAPTURED_STDOUT)

    assert all("\\" not in f.path for f in findings)


def test_parse_vulture_output_ignores_unparseable_lines() -> None:
    """A stray blank or banner line does not crash the parser or become a phantom finding."""
    findings = parse_vulture_output("\n" + _CAPTURED_STDOUT + "some unrelated banner text\n")

    assert len(findings) == 2


def test_count_by_confidence_buckets_high_and_moderate() -> None:
    """The 80% threshold separates high-confidence findings from moderate ones."""
    findings = parse_vulture_output(_CAPTURED_STDOUT)
    result = DeadCodeResult.from_findings(findings)

    assert result.count_by_confidence == {"high (>=80%)": 2}


def test_from_findings_rejects_an_empty_tuple() -> None:
    """Constructing a FINDINGS result with no findings is a programming error, not data."""
    with pytest.raises(ValueError, match="from_findings"):
        DeadCodeResult.from_findings(())


def test_clean_result_is_green() -> None:
    """A clean scan is the only honest GREEN."""
    result = DeadCodeResult.clean()

    assert result.is_green is True
    assert result.outcome is DeadCodeOutcome.CLEAN


def test_findings_result_is_not_green() -> None:
    """A scan carrying findings must never read as green."""
    result = DeadCodeResult.from_findings(parse_vulture_output(_CAPTURED_STDOUT))

    assert result.is_green is False
    assert result.outcome is DeadCodeOutcome.FINDINGS


def test_error_result_is_not_green() -> None:
    """A tool error must never read as green -- "could not measure" is not "found nothing"."""
    result = DeadCodeResult.error("vulture exited 2: bad config")

    assert result.is_green is False
    assert result.outcome is DeadCodeOutcome.ERROR


def test_render_console_report_caps_findings_by_default() -> None:
    """The console renderer caps the finding list unless `full=True`."""
    many = tuple(parse_vulture_output(_CAPTURED_STDOUT)) * 25  # 50 findings
    result = DeadCodeResult.from_findings(many)

    capped = render_console_report(result, full=False, cap=10)
    uncapped = render_console_report(result, full=True, cap=10)

    assert capped.count("\n") < uncapped.count("\n")
    assert "more (--full for all)" in capped
    assert "more (--full for all)" not in uncapped
