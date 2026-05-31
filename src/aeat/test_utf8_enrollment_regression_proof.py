"""Aggregate regression proof for W11.P42 UTF-8 enrollment.

Assertions
----------
(a) Zero bare ``"utf-8"`` survive in the three file clusters fixed in
    W11.P42: ``locales/manager.py``, ``adapters/outbound/google/_session_store.py``,
    and ``adapters/outbound/aeat/sede/_iva_compensation_wallet.py`` (hash-only sites
    are allowlisted and therefore already zero non-hash violations).

(b) The inventory test in ``test_utf8_enrollment_inventory.py`` walks the
    full production tree (not a fixed allowlist), confirmed by asserting that
    the scan covers more than the original fixed set of enrolled modules and
    includes the files fixed in W11.P42.
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

_BARE_UTF8_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r'encoding="utf-8"'),
    re.compile(r'\.encode\("utf-8"\)'),
    re.compile(r'\.decode\("utf-8"\)'),
)
_HASH_ALLOWLIST_TOKENS = frozenset({"hashlib", "hmac", "sha256", "sha1", "md5"})

# Files fixed in W11.P42 that must now be zero-violation.
_W11_P42_FIXED_FILES: tuple[str, ...] = (
    "locales/manager.py",
    "adapters/outbound/google/_session_store.py",
    # _iva_compensation_wallet.py has only hash-site literals (allowlisted); zero non-hash violations.
    "adapters/outbound/aeat/sede/_iva_compensation_wallet.py",
)

# Original enrolled module count from W07/W09 (11 modules).
_ORIGINAL_ENROLLED_COUNT = 11


def _is_hash_site(line: str) -> bool:
    return any(token in line for token in _HASH_ALLOWLIST_TOKENS)


def _non_hash_utf8_violations(path: pathlib.Path) -> list[tuple[int, str]]:
    violations: list[tuple[int, str]] = []
    source = path.read_text(encoding="utf-8", errors="replace")
    for lineno, line in enumerate(source.splitlines(), start=1):
        if _is_hash_site(line):
            continue
        if any(pat.search(line) for pat in _BARE_UTF8_PATTERNS):
            violations.append((lineno, line.strip()))
    return violations


def _all_production_files() -> list[pathlib.Path]:
    """Mirror the scan logic from test_utf8_enrollment_inventory."""
    _scan_excludes = frozenset({"core/external_constants.py"})
    files: list[pathlib.Path] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        rel = path.relative_to(_SRC_ROOT).as_posix()
        if path.name.startswith("test_"):
            continue
        if rel in _scan_excludes:
            continue
        files.append(path)
    return files


class TestW11P42FixedFilesZeroViolations:
    """(a) Zero non-hash bare utf-8 literals in each W11.P42 fixed file."""

    @pytest.mark.parametrize("rel_path", _W11_P42_FIXED_FILES)
    def test_zero_violations(self, rel_path: str) -> None:
        path = _SRC_ROOT / rel_path
        assert path.exists(), f"Fixed file missing from tree: {rel_path}"
        violations = _non_hash_utf8_violations(path)
        assert violations == [], (
            f"{rel_path} still contains {len(violations)} non-hash bare utf-8 literal(s):\n"
            + "\n".join(f"  line {ln}: {snippet!r}" for ln, snippet in violations)
        )


class TestInventoryTestCoversFullTree:
    """(b) The inventory scan covers more files than the original fixed allowlist."""

    def test_scan_covers_more_than_original_enrolled_count(self) -> None:
        production_files = _all_production_files()
        assert len(production_files) > _ORIGINAL_ENROLLED_COUNT, (
            f"Expected production tree scan to cover more than {_ORIGINAL_ENROLLED_COUNT} files "
            f"(original W07/W09 enrolled set), got {len(production_files)}. "
            "The full-tree inventory test may not be operating correctly."
        )

    def test_scan_includes_w11_p42_fixed_files(self) -> None:
        production_files = _all_production_files()
        scanned_rels = {p.relative_to(_SRC_ROOT).as_posix() for p in production_files}
        missing = [f for f in _W11_P42_FIXED_FILES if f not in scanned_rels]
        assert missing == [], (
            f"Full-tree inventory scan excludes W11.P42 fixed files: {missing}. "
            "These files would escape regression detection."
        )
