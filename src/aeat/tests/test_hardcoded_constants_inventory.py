"""Real-behavior inventory test: zero bare hardcoded literals in production source.

Asserts that none of the literals canonicalised in ratchet history survive in production
Python source outside their single canonical definition site and documented escapes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from ._inventory import SRC_AEAT, package_python_files, regex_line_hits

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = SRC_AEAT

# ---------------------------------------------------------------------------
# Canonical definition sites — excluded from the bare-literal scan.
# These are the single authorised locations that *define* the constants.
# ---------------------------------------------------------------------------

_CANONICAL_DEFINITIONS: frozenset[Path] = frozenset(
    [
        _SRC_ROOT / "adapters" / "outbound" / "aeat" / "sede" / "_browser_constants.py",
        _SRC_ROOT / "core" / "external_constants.py",
    ],
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _production_py_files() -> tuple[Path, ...]:
    """Return all non-test Python source files under src/aeat/."""
    return tuple(
        p
        for p in package_python_files(include_data=True)
        if not any(part.startswith("test_") or part == "tests" or part == "__pycache__" for part in p.parts)
        and p not in _CANONICAL_DEFINITIONS
    )


def _scan(files: Iterable[Path], pattern: re.Pattern[str]) -> list[str]:
    return regex_line_hits(files, pattern, skip_comment_lines=False)


# ---------------------------------------------------------------------------
# Test: no bare domcontentloaded literals
# ---------------------------------------------------------------------------


_RE_DOMCONTENTLOADED = re.compile(r'"domcontentloaded"')


def test_no_bare_domcontentloaded_literals() -> None:
    """All domcontentloaded usage must go through PLAYWRIGHT_WAIT_DOMCONTENTLOADED."""
    files = _production_py_files()
    hits = _scan(files, _RE_DOMCONTENTLOADED)
    assert not hits, (
        f"Found {len(hits)} bare 'domcontentloaded' literal(s) outside canonical definition:\n"
        + "\n".join(f"  {h}" for h in hits)
    )


# ---------------------------------------------------------------------------
# Test: no bare networkidle literals
# ---------------------------------------------------------------------------


_RE_NETWORKIDLE = re.compile(r'"networkidle"')


def test_no_bare_networkidle_literals() -> None:
    """All networkidle usage must go through PLAYWRIGHT_WAIT_NETWORKIDLE."""
    files = _production_py_files()
    hits = _scan(files, _RE_NETWORKIDLE)
    assert not hits, f"Found {len(hits)} bare 'networkidle' literal(s) outside canonical definition:\n" + "\n".join(
        f"  {h}" for h in hits
    )


# ---------------------------------------------------------------------------
# Test: no bare application/pdf content-type literals
# ---------------------------------------------------------------------------


_RE_PDF_MIME = re.compile(r'"application/pdf"')


def test_no_bare_application_pdf_mime_literals() -> None:
    """All application/pdf usage must go through PDF_MIME_TYPE."""
    files = _production_py_files()
    hits = _scan(files, _RE_PDF_MIME)
    assert not hits, f"Found {len(hits)} bare 'application/pdf' literal(s) outside canonical definition:\n" + "\n".join(
        f"  {h}" for h in hits
    )


# ---------------------------------------------------------------------------
# Test: no bare timeout=2_000 / timeout=2000 Playwright probe literals
# ---------------------------------------------------------------------------


_RE_PLAYWRIGHT_TIMEOUT_SHORT = re.compile(r"timeout\s*=\s*2[_]?000\b")


def test_no_bare_playwright_timeout_short_literals() -> None:
    """Short Playwright timeout 2_000 must go through PLAYWRIGHT_TIMEOUT_SHORT_MS."""
    files = _production_py_files()
    hits = _scan(files, _RE_PLAYWRIGHT_TIMEOUT_SHORT)
    assert not hits, f"Found {len(hits)} bare timeout=2_000 literal(s) outside canonical definition:\n" + "\n".join(
        f"  {h}" for h in hits
    )


# ---------------------------------------------------------------------------
# Test: no bare latin-1 decode literals
# ---------------------------------------------------------------------------


_RE_LATIN1_DECODE = re.compile(r'\.decode\(\s*["\']latin-1["\']')


def test_no_bare_latin1_decode_literals() -> None:
    """All latin-1 decode calls must go through LATIN_1_ENCODING or SEDE_BODY_ENCODING."""
    # Exclude _export_parse.py comment-only references — the decode itself is migrated.
    files = _production_py_files()
    hits = _scan(files, _RE_LATIN1_DECODE)
    assert not hits, (
        f"Found {len(hits)} bare .decode('latin-1') literal(s) outside canonical definition:\n"
        + "\n".join(f"  {h}" for h in hits)
    )
