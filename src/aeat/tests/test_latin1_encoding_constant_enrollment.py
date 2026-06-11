"""LATIN_1_ENCODING enrollment in the BOE export test package.

Asserts that the ``adapters/outbound/aeat/export/`` package contains no
bare ``"iso-8859-1"`` string literals in test files — every occurrence
must be replaced with the named ``LATIN_1_ENCODING`` constant imported
from ``aeat.core.external_constants``.

No mocks, no skips, no xfail, no tautological assertions.
"""

from __future__ import annotations

import pathlib

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = pathlib.Path(__file__).parent.parent
_EXPORT_TEST_PACKAGE = _SRC_ROOT / "adapters" / "outbound" / "aeat" / "export"

_BARE_LATIN1_LITERAL = '"iso-8859-1"'


def _collect_violations() -> list[tuple[pathlib.Path, int, str]]:
    """Return (path, lineno, line) for every bare iso-8859-1 literal in test files."""
    violations: list[tuple[pathlib.Path, int, str]] = []
    for path in sorted(_EXPORT_TEST_PACKAGE.rglob("test_*.py")):
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            if _BARE_LATIN1_LITERAL in line:
                violations.append((path.relative_to(_SRC_ROOT.parent), lineno, line.strip()))
    return violations


def test_no_bare_iso8859_1_in_export_test_package() -> None:
    """Zero bare ``"iso-8859-1"`` string literals survive in the BOE export test package.

    Every occurrence must use the named ``LATIN_1_ENCODING`` constant from
    ``aeat.core.external_constants`` so encoding-string changes propagate
    from a single canonical source.
    """
    violations = _collect_violations()
    if violations:
        lines = "\n  ".join(f"{path}:{lineno}: {text}" for path, lineno, text in violations)
        raise AssertionError(
            f"{len(violations)} bare 'iso-8859-1' literal(s) found in export test package; "
            f"replace with LATIN_1_ENCODING from aeat.core.external_constants:\n  {lines}",
        )
