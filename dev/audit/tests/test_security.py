"""Security report shape and parsing over synthetic-free, real captured output.

In-process checks only: the parser reads a real captured semgrep ``--json``
payload (trimmed from an actual scoped run against ``src/cadrumo/core``, not
synthesised), and the typed result/renderer are exercised directly. Split
from the live-scan half so each module carries one execution lane -- the gate
that actually runs semgrep over the tree lives in ``test_security_scan``.
"""

from __future__ import annotations

import json
import tomllib

import pytest

from ..._paths import REPO_ROOT
from ..security import (
    _PYTHON_LEGACY_COMPATIBILITY_RULE_IDS,
    SecurityOutcome,
    SecurityResult,
    classify_semgrep_output,
    render_console_report,
    semgrep_command,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

# A real captured semgrep --json payload, trimmed from a scoped run against
# src/cadrumo/core (2 of the 11 real results, the 1 real parse error, and a
# trimmed `paths.scanned` list -- shapes and field names verbatim).
_CAPTURED_JSON = json.dumps(
    {
        "version": "1.71.0",
        "results": [
            {
                "check_id": "python.lang.security.audit.non-literal-import.non-literal-import",
                "path": "src\\cadrumo\\core\\errors\\tests\\test_exception_base_hygiene.py",
                "start": {"line": 81, "col": 24, "offset": 3830},
                "end": {"line": 81, "col": 53, "offset": 3859},
                "extra": {
                    "message": (
                        "Untrusted user input in `importlib.import_module()` function allows an "
                        "attacker to load arbitrary code."
                    ),
                    "severity": "WARNING",
                    "metadata": {"confidence": "LOW"},
                },
            },
            {
                "check_id": "python.lang.compatibility.python37.python37-compatibility-importlib2",
                "path": "src\\cadrumo\\core\\tests\\test_resources.py",
                "start": {"line": 5, "col": 1, "offset": 0},
                "end": {"line": 5, "col": 10, "offset": 9},
                "extra": {"message": "importlib.resources API requires python3.7+", "severity": "ERROR"},
            },
        ],
        "errors": [
            {
                "code": 3,
                "level": "warn",
                "type": "Syntax error",
                "message": "Syntax error at line src\\cadrumo\\core\\redaction\\__init__.py:725:\n `[` was unexpected",
                "path": "src\\cadrumo\\core\\redaction\\__init__.py",
            },
        ],
        "paths": {"scanned": ["src\\cadrumo\\core\\__init__.py", "src\\cadrumo\\core\\_aeat_csv.py"]},
    },
)

# semgrep's own signature for "matched zero files" -- no `results`/`paths.scanned`
# proof of life at all, just an empty envelope.
_EMPTY_SCAN_JSON = json.dumps({"version": "1.71.0", "results": [], "errors": [], "paths": {"scanned": []}})


def test_command_uses_json_not_the_text_report() -> None:
    """The command requests --json, not the text report that renders code context."""
    command = semgrep_command("uvx")

    assert "--json" in command
    assert "--quiet" in command
    assert "src/cadrumo" in command
    assert not any("\\" in arg for arg in command), f"a backslash path reached semgrep: {command}"


def test_command_excludes_the_python36_python37_compatibility_rules() -> None:
    """The rules flag `Popen`/`importlib.resources` version gates this project never hits.

    `pyproject.toml` requires Python >=3.13 with no upper bound, so a rule warning that an API
    needs 3.6+ or 3.7+ can never describe a real regression; every occurrence
    is excluded by rule id rather than judged finding by finding.
    """
    command = semgrep_command("uvx")

    excluded = {command[i + 1] for i, arg in enumerate(command) if arg == "--exclude-rule"}
    assert excluded == set(_PYTHON_LEGACY_COMPATIBILITY_RULE_IDS)


def test_legacy_rule_exclusions_are_anchored_to_the_open_project_floor() -> None:
    """The compatibility-rule filter must not drift back to a Python ceiling."""
    with (REPO_ROOT / "pyproject.toml").open("rb") as handle:
        project = tomllib.load(handle)["project"]

    requires_python = project["requires-python"]
    assert requires_python == ">=3.13"
    assert "<" not in requires_python
    assert _PYTHON_LEGACY_COMPATIBILITY_RULE_IDS


def test_classify_reads_real_captured_findings() -> None:
    """The parser reads real check_id/path/severity/message fields from --json."""
    result = classify_semgrep_output(_CAPTURED_JSON)

    assert result.outcome is SecurityOutcome.FINDINGS
    assert result.files_scanned == 2
    assert len(result.findings) == 2
    error_finding = next(f for f in result.findings if f.severity == "ERROR")
    assert error_finding.check_id == "python.lang.compatibility.python37.python37-compatibility-importlib2"
    assert error_finding.path == "src/cadrumo/core/tests/test_resources.py"
    assert error_finding.line == 5


def test_classify_surfaces_parse_errors_rather_than_swallowing_them() -> None:
    """semgrep's own `errors[]` (files it could not parse) must reach the result."""
    result = classify_semgrep_output(_CAPTURED_JSON)

    assert len(result.parse_errors) == 1
    assert "redaction/__init__.py" in result.parse_errors[0] or "redaction\\__init__.py" in result.parse_errors[0]


def test_findings_are_sorted_error_first() -> None:
    """The worst severity sorts first, so a capped console view never buries an ERROR."""
    result = classify_semgrep_output(_CAPTURED_JSON)

    assert result.findings[0].severity == "ERROR"


def test_count_by_severity_uses_semgreps_own_axis() -> None:
    """count_by_severity reflects semgrep's real ERROR/WARNING/INFO field."""
    result = classify_semgrep_output(_CAPTURED_JSON)

    assert result.count_by_severity == {"ERROR": 1, "WARNING": 1}


def test_empty_scan_output_is_unavailable_not_zero() -> None:
    """A scan that matched zero files must refuse to claim cleanliness.

    Mirrors ``duplication.py``'s own ``test_empty_scan_output_is_unavailable_not_zero``:
    a naive `len(results) == 0` reading would render this GREEN, which is the
    false-green the `files_scanned` proof-of-life check exists to prevent.
    """
    result = classify_semgrep_output(_EMPTY_SCAN_JSON)

    assert result.outcome is SecurityOutcome.UNAVAILABLE
    assert result.is_green is False


def test_malformed_json_is_unavailable_not_zero() -> None:
    """Non-JSON stdout (a crash, a truncated pipe) must not be misread as clean."""
    result = classify_semgrep_output("not json at all")

    assert result.outcome is SecurityOutcome.UNAVAILABLE
    assert result.is_green is False


def test_zero_findings_over_real_scanned_files_is_green() -> None:
    """A scan that demonstrably inspected files and found nothing is the only honest GREEN."""
    clean_payload = json.dumps(
        {"results": [], "errors": [], "paths": {"scanned": ["src\\cadrumo\\core\\__init__.py"]}},
    )
    result = classify_semgrep_output(clean_payload)

    assert result.outcome is SecurityOutcome.OBSERVED_ZERO
    assert result.is_green is True
    assert result.files_scanned == 1


def test_from_findings_rejects_an_empty_tuple() -> None:
    """Constructing a FINDINGS result with no findings is a programming error, not data."""
    with pytest.raises(ValueError, match="from_findings"):
        SecurityResult.from_findings(files_scanned=1, findings=(), parse_errors=(), raw_json="{}")


def test_observed_zero_rejects_a_non_positive_file_count() -> None:
    """observed_zero requires proof files were actually inspected."""
    with pytest.raises(ValueError, match="observed_zero"):
        SecurityResult.observed_zero(0, (), "{}")


def test_render_console_report_caps_findings_by_default() -> None:
    """The console renderer caps the finding list unless `full=True`."""
    many = classify_semgrep_output(_CAPTURED_JSON).findings * 25  # 50 findings
    result = SecurityResult.from_findings(files_scanned=2, findings=many, parse_errors=(), raw_json="{}")

    capped = render_console_report(result, full=False, cap=10)
    uncapped = render_console_report(result, full=True, cap=10)

    assert "more (--full for all)" in capped
    assert "more (--full for all)" not in uncapped
    assert capped.count("\n") < uncapped.count("\n")


def test_render_console_report_shows_no_code_context() -> None:
    """The whole point: no source-line rendering, only one line per finding."""
    result = classify_semgrep_output(_CAPTURED_JSON)

    report = render_console_report(result, full=True)

    assert report.count("\n") < 10, f"the reduced report grew source-context lines back: {report!r}"
