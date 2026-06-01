"""W20.P52 closure aggregate test.

Asserts:
- S643: ANY-RETURN-RATIONALE-ACTIONS-IVA-WALLET-DECISION token appears within 3
  lines preceding def _iva_wallet_blocked_message in _actions.py.
- S644: ANY-RETURN-RATIONALE-SOURCE-PROFILE-FINGERPRINT token appears within 3
  lines preceding def _profile_fingerprint in _source_profile.py.
- Prior-wave inventory ratchets (utf8, cast-rationale, latin1, enum-constant)
  remain green.
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

from .core.logging import get_logger

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_logger = get_logger(__name__)

_SRC = pathlib.Path(__file__).parent
_REPO = _SRC.parent.parent


def _lines(path: pathlib.Path) -> list[str]:
    return path.read_text(encoding="utf-8").splitlines()


def _token_within_n_lines_above(lines: list[str], token: str, needle: str, n: int = 3) -> bool:
    """Return True if *token* appears within *n* lines above any line containing *needle*."""
    for i, line in enumerate(lines):
        if needle not in line:
            continue
        window_start = max(0, i - n)
        for j in range(window_start, i):
            if token in lines[j]:
                return True
    return False


# ---------------------------------------------------------------------------
# S643
# ---------------------------------------------------------------------------


def test_s643_iva_wallet_decision_token_present() -> None:
    """ANY-RETURN-RATIONALE-ACTIONS-IVA-WALLET-DECISION precedes def _iva_wallet_blocked_message."""
    path = _SRC / "application" / "modelo" / "_actions.py"
    lines = _lines(path)
    token = "ANY-RETURN-RATIONALE-ACTIONS-IVA-WALLET-DECISION"
    needle = "def _iva_wallet_blocked_message"
    assert _token_within_n_lines_above(lines, token, needle), (
        f"{token} not found within 3 lines above '{needle}' in {path}"
    )
    _logger.debug("S643 token verified in %s", path.name)


# ---------------------------------------------------------------------------
# S644
# ---------------------------------------------------------------------------


def test_s644_source_profile_fingerprint_token_present() -> None:
    """ANY-RETURN-RATIONALE-SOURCE-PROFILE-FINGERPRINT precedes def _profile_fingerprint."""
    path = _SRC / "application" / "aggregation" / "_source_profile.py"
    lines = _lines(path)
    token = "ANY-RETURN-RATIONALE-SOURCE-PROFILE-FINGERPRINT"
    needle = "def _profile_fingerprint"
    assert _token_within_n_lines_above(lines, token, needle), (
        f"{token} not found within 3 lines above '{needle}' in {path}"
    )
    _logger.debug("S644 token verified in %s", path.name)


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


def test_cast_rationale_inventory_green() -> None:
    """Prior-wave ratchet: test_cast_rationale_inventory remains green."""
    _run_test_module(_SRC / "test_cast_rationale_inventory.py")


def test_latin1_encoding_constant_enrollment_green() -> None:
    """Prior-wave ratchet: test_latin1_encoding_constant_enrollment remains green."""
    _run_test_module(_SRC / "test_latin1_encoding_constant_enrollment.py")


def test_enum_constant_extraction_inventory_green() -> None:
    """Prior-wave ratchet: test_enum_constant_extraction_inventory remains green."""
    _run_test_module(_SRC / "test_enum_constant_extraction_inventory.py")
