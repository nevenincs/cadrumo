"""Real-behavior inventory test: zero bare hardcoded literals in production source.

Asserts that none of the literals canonicalised in ratchet history survive in production
Python source outside their single canonical definition site and documented escapes.

See Also:
    :mod:`~tests._inventory`
        Provides the production-file and regex scanners used by this literal
        centralisation gate.
    :mod:`~core.external_constants`
        Canonical registry for shared MIME, encoding, host, and route constants.
    :mod:`~adapters.outbound.aeat.sede._browser_constants`
        Adapter-local Playwright and Sede body-encoding constants excluded as
        authoritative definition sites.

Executable AEAT/Sede constants must live in a schema-owned canonical surface,
never as scattered literals across production modules.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from .inventory import SRC_CADRUMO, non_test_package_python_files, regex_line_hits

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = SRC_CADRUMO

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
    """Return all non-test Python source files under src/cadrumo/."""
    return tuple(p for p in non_test_package_python_files(include_data=True) if p not in _CANONICAL_DEFINITIONS)


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


# ---------------------------------------------------------------------------
# Controls: the scans above only mean something while they can still match.
# ---------------------------------------------------------------------------

#: Each scan pattern with a literal it MUST flag and a migrated form it MUST NOT.
#:
#: Every test above reports absence, and absence is what a broken pattern reports
#: too. The sibling survivor gate carried a pattern built from a raw string with a
#: doubled backslash, so it required a literal backslash before the token and could
#: never match a real string literal; it read clean across the whole production tree
#: while four live sites went uncaught. These pairs are what separate "nothing to
#: find" from "cannot find anything".
_PATTERN_CONTROLS: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (
        _RE_DOMCONTENTLOADED,
        'await page.goto(url, wait_until="domcontentloaded")',
        "await page.goto(url, wait_until=PLAYWRIGHT_WAIT_DOMCONTENTLOADED)",
    ),
    (
        _RE_NETWORKIDLE,
        'page.wait_for_load_state("networkidle")',
        "page.wait_for_load_state(PLAYWRIGHT_WAIT_NETWORKIDLE)",
    ),
    (_RE_PDF_MIME, 'content_type = "application/pdf"', "content_type = PDF_MIME_TYPE"),
    (
        _RE_PLAYWRIGHT_TIMEOUT_SHORT,
        "locator.click(timeout=2_000)",
        "locator.click(timeout=PLAYWRIGHT_TIMEOUT_SHORT_MS)",
    ),
    (_RE_LATIN1_DECODE, 'body.decode("latin-1")', "body.decode(SEDE_BODY_ENCODING)"),
)

#: Near-misses that must stay unflagged, so the scans cannot be made to pass by
#: over-broadening. Each is a real neighbour of its pattern's target.
_PATTERN_NEAR_MISSES: tuple[tuple[re.Pattern[str], str], ...] = (
    (_RE_PDF_MIME, 'content_type = "application/pdfx"'),
    (_RE_PLAYWRIGHT_TIMEOUT_SHORT, "locator.click(timeout=20000)"),
    (_RE_LATIN1_DECODE, 'body.encode("latin-1")'),
)


def test_constant_scan_patterns_discriminate() -> None:
    """Positive control: each pattern flags a bare literal and clears the migrated form."""
    assert len(_PATTERN_CONTROLS) == 5, "every scan pattern in this module needs a control pair"
    failures: list[str] = []
    failures.extend(
        f"{pattern.pattern!r} failed to flag the bare literal {bare!r}"
        for pattern, bare, _ in _PATTERN_CONTROLS
        if not pattern.search(bare)
    )
    failures.extend(
        f"{pattern.pattern!r} wrongly flagged the migrated form {migrated!r}"
        for pattern, _, migrated in _PATTERN_CONTROLS
        if pattern.search(migrated)
    )
    failures.extend(
        f"{pattern.pattern!r} wrongly flagged the near-miss {probe!r}"
        for pattern, probe in _PATTERN_NEAR_MISSES
        if pattern.search(probe)
    )
    assert not failures, "constant scan patterns no longer discriminate:\n" + "\n".join(failures)


def test_constant_scan_reads_a_non_empty_corpus() -> None:
    """A survivor scan over zero files would report clean without looking at anything."""
    files = _production_py_files()
    assert len(files) > 500, f"expected the production corpus, scanned only {len(files)} files"


def test_scan_reports_a_planted_literal_with_its_location() -> None:
    """The scan reports a real hit, not merely an empty list, and names where it is.

    Proves the walk reaches file contents. A scanner whose file read or line
    accounting broke would return an empty list over a corpus that genuinely
    contains the token, which is indistinguishable from the clean result the
    tests above assert.
    """
    planted = _SRC_ROOT / "core" / "external_constants.py"
    assert planted.is_file(), "canonical constant home moved; update this control"

    hits = _scan((planted,), _RE_PDF_MIME)

    assert hits, "the canonical constant home defines the PDF MIME literal, so the scan must see it"
    assert all(":" in hit for hit in hits), f"scan hits must carry a path:line locator, got {hits!r}"
