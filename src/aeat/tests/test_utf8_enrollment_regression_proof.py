"""Regression proof for the UTF-8 enrollment of three additional file clusters.

Assertions
----------
(a) Zero bare ``"utf-8"`` survive in the three enrolled file clusters:
    ``locales/manager.py``,
    ``adapters/outbound/google/_session_store.py``, and
    ``adapters/outbound/aeat/sede/_iva_compensation_wallet.py`` (hash-only
    sites are allowlisted and therefore already zero non-hash
    violations).

(b) The inventory test in ``test_utf8_enrollment_inventory.py`` walks the
    full production tree (not a fixed allowlist), confirmed by asserting
    that the scan covers more than the original enrolled count and
    includes the files enrolled by this regression proof.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, aeat_relative, bare_utf8_literal_violations, non_test_package_python_files

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = SRC_AEAT

# Files enrolled by this regression proof that must now be zero-violation.
_ENROLLED_FILES: tuple[str, ...] = (
    "locales/manager.py",
    "adapters/outbound/google/_session_store.py",
    # _iva_compensation_wallet.py has only hash-site literals (allowlisted); zero non-hash violations.
    "adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
)

# Baseline enrolled module count prior to this regression proof.
_BASELINE_ENROLLED_COUNT = 11


def _all_production_files() -> tuple[Path, ...]:
    """Mirror the scan logic from test_utf8_enrollment_inventory."""
    _scan_excludes = frozenset({"core/external_constants.py"})
    return non_test_package_python_files(include_data=True, scan_excludes=_scan_excludes)


class TestEnrolledFilesZeroViolations:
    """(a) Zero non-hash bare utf-8 literals in each enrolled file."""

    @pytest.mark.parametrize("rel_path", _ENROLLED_FILES)
    def test_zero_violations(self, rel_path: str) -> None:
        path = _SRC_ROOT / rel_path
        assert path.exists(), f"Enrolled file missing from tree: {rel_path}"
        violations = bare_utf8_literal_violations(path)
        assert violations == [], (
            f"{rel_path} still contains {len(violations)} non-hash bare utf-8 literal(s):\n"
            + "\n".join(f"  line {ln}: {snippet!r}" for ln, snippet in violations)
        )


class TestInventoryTestCoversFullTree:
    """(b) The inventory scan covers more files than the baseline enrolled set."""

    def test_scan_covers_more_than_baseline_enrolled_count(self) -> None:
        production_files = _all_production_files()
        assert len(production_files) > _BASELINE_ENROLLED_COUNT, (
            f"Expected production tree scan to cover more than {_BASELINE_ENROLLED_COUNT} files "
            f"(baseline enrolled set), got {len(production_files)}. "
            "The full-tree inventory test may not be operating correctly."
        )

    def test_scan_includes_enrolled_files(self) -> None:
        production_files = _all_production_files()
        scanned_rels = {aeat_relative(p) for p in production_files}
        missing = [f for f in _ENROLLED_FILES if f not in scanned_rels]
        assert missing == [], (
            f"Full-tree inventory scan excludes enrolled files: {missing}. "
            "These files would escape regression detection."
        )
