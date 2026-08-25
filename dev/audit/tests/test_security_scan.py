"""The security gate that runs a real semgrep scan through uvx.

These spawn the vendored scanner through uvx and read what it actually
reports, so they are ``integration``: they need uvx on PATH and network
access on the first pull. The parsing and classification checks are in
``test_security``; this module only proves the runner against a live
process.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

from ..._paths import REPO_ROOT
from ..security import SecurityOutcome, run_security_scan

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_REPO_ROOT = REPO_ROOT


def _require_uvx() -> None:
    """Assert the real uvx binary is present for an integration test.

    The sanctioned convention for external-binary integration tests in this
    repo is to assert the tool is present, not to self-skip when it is absent
    (see the sibling ``test_duplication_scan.py``).
    """
    assert shutil.which("uvx") is not None, "uvx is required to run the real semgrep security scan"


def test_real_scan_over_a_small_real_tree_returns_a_typed_outcome() -> None:
    """A real semgrep run over a small real subtree classifies honestly, never a crash."""
    _require_uvx()
    result = run_security_scan(_REPO_ROOT, source_root=Path("dev/audit"))

    assert result.outcome in {SecurityOutcome.OBSERVED_ZERO, SecurityOutcome.FINDINGS}
    assert result.files_scanned > 0, "a non-unavailable verdict must prove files were scanned"
    assert result.headline()


def test_real_bad_source_path_is_unavailable_not_green() -> None:
    """A real scan of a path that matches nothing must refuse to claim cleanliness."""
    _require_uvx()
    result = run_security_scan(_REPO_ROOT, source_root=Path("src/cadrumo/no-such-directory"))

    assert result.outcome is SecurityOutcome.UNAVAILABLE
    assert result.is_green is False


def test_real_timeout_is_unavailable_not_green() -> None:
    """A real semgrep run cut off by the timeout must report unavailable."""
    _require_uvx()
    result = run_security_scan(_REPO_ROOT, timeout=0.001)

    assert result.outcome is SecurityOutcome.UNAVAILABLE
    assert result.is_green is False
    assert "timeout" in result.reason


def test_real_nonzero_exit_is_unavailable_not_green() -> None:
    """A real subprocess that exits non-zero must report unavailable.

    Same technique as `duplication.py`'s own sibling test: the injected
    ``which`` seam returns a real Python interpreter, so the scan genuinely
    launches ``<python> --from semgrep==... semgrep scan ...``, which the
    interpreter rejects and exits non-zero. A genuinely failing process is
    what is under test, not a patched parser.
    """
    result = run_security_scan(_REPO_ROOT, which=lambda _name: sys.executable)

    assert result.outcome is SecurityOutcome.UNAVAILABLE
    assert result.is_green is False
    assert "exited" in result.reason


def test_real_missing_executable_is_unavailable_not_green() -> None:
    """A resolver returning None (uvx not found) must report unavailable, not crash."""
    result = run_security_scan(_REPO_ROOT, which=lambda _name: None)

    assert result.outcome is SecurityOutcome.UNAVAILABLE
    assert "not found" in result.reason
