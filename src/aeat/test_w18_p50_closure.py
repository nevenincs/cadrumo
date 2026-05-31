"""W18.P50 closure aggregate test.

Asserts:
- S638: CAST-RATIONALE-SANITIZER-PIKEPDF-OPERAND-LIST token appears within 3
  lines preceding any cast( in _streams.py.
- S639: CAST-RATIONALE-WORKFLOW-SITE-HEALTH-STATUS token appears within 3
  lines preceding the cast( at workflow/_engine.py:1270.
- cast-rationale inventory remains zero-violation.
- Prior-wave inventory ratchets (utf8, latin1, enum-constant) remain green.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

from aeat.core.logging import get_logger

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_logger = get_logger(__name__)

_SRC = pathlib.Path(__file__).parent
_REPO = _SRC.parent.parent


def _lines(path: pathlib.Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _token_precedes_cast_via_comment_walk(
    lines: list[str], token: str, cast_needle: str = "cast("
) -> bool:
    """Return True if *token* appears on or immediately above any *cast_needle* line.

    Mirrors the inventory test's upward-walk: ascend through consecutive
    comment/blank lines; stop at the first code line.
    """

    def _is_comment_or_blank(line: str) -> bool:
        stripped = line.strip()
        return stripped == "" or stripped.startswith("#")

    for i, line in enumerate(lines):
        if cast_needle not in line:
            continue
        # Check the cast line itself.
        if token in line:
            return True
        # Walk upward through adjacent comment/blank lines.
        scan = i - 1
        while scan >= 0:
            candidate = lines[scan]
            if token in candidate:
                return True
            if _is_comment_or_blank(candidate):
                scan -= 1
            else:
                break
    return False


# ---------------------------------------------------------------------------
# S638
# ---------------------------------------------------------------------------


def test_s638_sanitizer_pikepdf_operand_list_token_present() -> None:
    """CAST-RATIONALE-SANITIZER-PIKEPDF-OPERAND-LIST precedes cast( in _streams.py."""
    path = _SRC / "adapters" / "inbound" / "sanitizer" / "_streams.py"
    lines = _lines(path)
    token = "CAST-RATIONALE-SANITIZER-PIKEPDF-OPERAND-LIST"
    assert _token_precedes_cast_via_comment_walk(lines, token), (
        f"{token} not found in comment block immediately preceding any cast( in {path}"
    )
    _logger.debug("S638 token verified in %s", path.name)


# ---------------------------------------------------------------------------
# S639
# ---------------------------------------------------------------------------


def test_s639_workflow_site_health_status_token_present() -> None:
    """CAST-RATIONALE-WORKFLOW-SITE-HEALTH-STATUS precedes cast( in _engine.py."""
    path = _SRC / "application" / "workflow" / "_engine.py"
    lines = _lines(path)
    token = "CAST-RATIONALE-WORKFLOW-SITE-HEALTH-STATUS"
    assert _token_precedes_cast_via_comment_walk(lines, token), (
        f"{token} not found in comment block immediately preceding any cast( in {path}"
    )
    _logger.debug("S639 token verified in %s", path.name)


# ---------------------------------------------------------------------------
# cast-rationale inventory gate
# ---------------------------------------------------------------------------


def test_cast_rationale_inventory_zero_violations() -> None:
    """Delegating to test_cast_rationale_inventory._collect_violations() asserts zero."""
    import importlib.util

    inv_path = _SRC / "test_cast_rationale_inventory.py"
    spec = importlib.util.spec_from_file_location("_cast_inv", inv_path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    violations: list[str] = mod._collect_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} cast() call(s) lack a CAST-RATIONALE-* marker:\n  {joined}"
        )
    _logger.debug("cast-rationale inventory: 0 violations")


# ---------------------------------------------------------------------------
# Prior-wave inventory ratchets
# ---------------------------------------------------------------------------


def _run_test_module(test_file: pathlib.Path) -> None:
    """Run a test module via pytest subprocess and assert it passes."""
    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_file), "-x", "-q", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=_REPO,
    )
    _logger.debug(
        "pytest %s → returncode=%d stdout=%s stderr=%s",
        test_file.name,
        result.returncode,
        result.stdout[-500:] if result.stdout else "",
        result.stderr[-200:] if result.stderr else "",
    )
    if result.returncode != 0:
        raise AssertionError(
            f"{test_file.name} failed (returncode={result.returncode}):\n{result.stdout}\n{result.stderr}"
        )


def test_utf8_enrollment_inventory_green() -> None:
    """Prior-wave ratchet: test_utf8_enrollment_inventory remains green."""
    _run_test_module(_SRC / "test_utf8_enrollment_inventory.py")


def test_latin1_encoding_constant_enrollment_green() -> None:
    """Prior-wave ratchet: test_latin1_encoding_constant_enrollment remains green."""
    _run_test_module(_SRC / "test_latin1_encoding_constant_enrollment.py")


def test_enum_constant_extraction_inventory_green() -> None:
    """Prior-wave ratchet: test_enum_constant_extraction_inventory remains green."""
    _run_test_module(_SRC / "test_enum_constant_extraction_inventory.py")
