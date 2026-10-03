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
    SkippedModule,
    offered_module_population,
    parse_vulture_output,
    parse_vulture_stderr,
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

# The stderr of a real vulture 2.16 run (exit 3, one finding on stdout) over a
# directory holding one module of each kind it skips plus one that only warns.
# Only the absolute checkout prefix vulture printed has been shortened.
_CAPTURED_SKIP_STDERR = (
    'e\\broken.py:1: invalid decimal literal at "x = 1_"\r\n'
    "e\\nul.py:None: source code string cannot contain null bytes\r\n"
    "Error: Could not read file C:\\checkout\\e\\undecodable.py - \r\n"
    "Try to change the encoding to UTF-8.\r\n"
    "C:\\checkout\\e\\warn.py:2: SyntaxWarning: invalid escape sequence '\\d'\r\n"
    '  P = re.compile("\\d+")\r\n'
)


def test_command_targets_the_configured_paths() -> None:
    """The command is the one vulture invocation every dead-code consumer runs."""
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
    assert first.path == "src/cadrumo/application/review/_operator.py"
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
    """A clean scan is the only honest GREEN, and it carries what it inspected."""
    result = DeadCodeResult.clean(modules_offered=1873)

    assert result.is_green is True
    assert result.outcome is DeadCodeOutcome.CLEAN
    assert result.modules_offered == 1873
    assert "1873" in result.headline()


def test_clean_refuses_a_scan_that_inspected_nothing() -> None:
    """A GREEN bound to no evidence is the one outcome the class must not admit.

    Vulture exits 0 both for a tree it read and found clean and for a target
    set offering it nothing, so CLEAN without a denominator cannot tell those
    apart. The sibling duplication and security results already refuse the
    same shape on their own tool-reported counts.
    """
    with pytest.raises(ValueError, match="clean requires a scan that demonstrably inspected"):
        DeadCodeResult.clean(modules_offered=0)


def test_offered_population_counts_the_modules_the_targets_actually_hold(tmp_path) -> None:
    """The denominator is read off the tree, not assumed from the target names."""
    assert offered_module_population(tmp_path) == 0

    package = tmp_path / "src" / "cadrumo" / "domain"
    package.mkdir(parents=True)
    (package / "one.py").write_text("", encoding="utf-8")
    (package / "two.py").write_text("", encoding="utf-8")
    (package / "notes.md").write_text("", encoding="utf-8")
    whitelist = tmp_path / "dev" / "audit"
    whitelist.mkdir(parents=True)
    (whitelist / "vulture_whitelist.py").write_text("", encoding="utf-8")

    assert offered_module_population(tmp_path) == 3


def test_offered_population_counts_only_production_source(tmp_path) -> None:
    """Test modules, conftest files and bundled data are not part of what vulture analyses."""
    package = tmp_path / "src" / "cadrumo" / "domain"
    (package / "tests").mkdir(parents=True)
    (package / "_data").mkdir()
    for module in ("one.py", "test_one.py", "_test_two.py", "conftest.py", "tests/helper.py", "_data/__init__.py"):
        (package / module).write_text("", encoding="utf-8")

    assert offered_module_population(tmp_path) == 1


def test_parse_vulture_stderr_names_every_skipped_module() -> None:
    """Each skip shape vulture prints becomes a named module, with its reason."""
    diagnostics = parse_vulture_stderr(_CAPTURED_SKIP_STDERR)

    assert diagnostics.skipped == (
        SkippedModule(path="e/broken.py", reason='invalid decimal literal at "x = 1_"'),
        SkippedModule(path="e/nul.py", reason="source code string cannot contain null bytes"),
        SkippedModule(path="C:/checkout/e/undecodable.py", reason="could not be read"),
    )
    assert diagnostics.unrecognised == ()


def test_parse_vulture_stderr_ignores_warnings_for_modules_it_still_parsed() -> None:
    """A SyntaxWarning and its echoed source line do not mark the module as skipped."""
    warning_only = "".join(_CAPTURED_SKIP_STDERR.splitlines(keepends=True)[-2:])

    diagnostics = parse_vulture_stderr(warning_only)

    assert diagnostics.skipped == ()
    assert diagnostics.unrecognised == ()


def test_parse_vulture_stderr_ignores_the_uv_launcher_warning() -> None:
    """A warning ``uv run`` prints about its environment is not a vulture diagnostic."""
    captured = (
        "warning: `VIRTUAL_ENV=Y:\\checkout\\.venv` does not match the project environment path `.venv` "
        "and will be ignored; use `--active` to target the active environment instead\n"
    )

    assert parse_vulture_stderr(captured) == parse_vulture_stderr("")


def test_parse_vulture_stderr_keeps_an_unknown_line_visible() -> None:
    """A line in no known shape is reported, not dropped, so a reworded skip cannot hide."""
    diagnostics = parse_vulture_stderr("Skipping src/cadrumo/x.py because of reasons\n")

    assert diagnostics.skipped == ()
    assert diagnostics.unrecognised == ("Skipping src/cadrumo/x.py because of reasons",)


def test_an_indented_line_not_following_a_warning_is_unrecognised() -> None:
    """Only the source line beneath a warning is dropped; a free-standing indented line is not."""
    diagnostics = parse_vulture_stderr("  something indented\n")

    assert diagnostics.unrecognised == ("  something indented",)


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
