"""Workbook scan-status enum, STRICT_FROZEN_CONFIG, and UTF-8 enrollment.

Asserts that:
(a) Zero bare ``report.scan_status == "scanned"`` (or
    ``in {"failed", "timeout"}``) comparisons survive in
    ``_workbook_parity.py`` — all sites must use ``WorkbookScanStatus``
    enum members.
(b) ``STRICT_FROZEN_CONFIG`` from ``aeat.core`` is used everywhere
    a local ``_STRICT_FROZEN = ConfigDict(...)`` would otherwise be
    declared; the two relevant persistence-layer files use the canonical
    constant.
(c) ``UTF_8_ENCODING`` from ``aeat.core.external_constants`` is enrolled
    in all production persistence and application call sites covered by
    this inventory; no bare ``encoding="utf-8"`` strings remain in the
    enrolled-files set outside the canonical definition site.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = PROJECT_ROOT / "src" / "aeat"

# ---------------------------------------------------------------------------
# Helpers shared across assertions
# ---------------------------------------------------------------------------

_UTF8_CONSTANT_DEFINITION = _SRC_ROOT / "core" / "external_constants.py"
_WORKBOOK_PARITY_FILE = _SRC_ROOT / "domain" / "calculations" / "registry" / "_workbook_parity.py"

# Production files that are ALLOWED to keep bare encoding="utf-8" because
# they are test modules, not production code.  The scan skips them.
# Any new production file that must keep a bare literal for a documented
# reason should be added here with a comment explaining why.
_UTF8_ALLOWLIST: frozenset[Path] = frozenset(
    [
        # canonical constant definition — the ONLY place the literal must appear
        _UTF8_CONSTANT_DEFINITION,
    ],
)


def _production_py_files() -> list[Path]:
    """Return all non-test Python source files under src/aeat/."""
    return [
        p
        for p in _SRC_ROOT.rglob("*.py")
        if not any(part.startswith("test_") or part == "__pycache__" for part in p.parts)
    ]


def _scan(
    files: list[Path],
    pattern: re.Pattern[str],
    *,
    skip_comment_lines: bool = True,
) -> list[str]:
    hits: list[str] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = text.splitlines()
        for match in pattern.finditer(text):
            line_no = text[: match.start()].count("\n") + 1
            if skip_comment_lines and line_no <= len(lines):
                stripped = lines[line_no - 1].lstrip()
                if stripped.startswith("#"):
                    continue
            relative = path.relative_to(PROJECT_ROOT).as_posix()
            hits.append(f"{relative}:{line_no}: {match.group(0)!r}")
    return hits


# ---------------------------------------------------------------------------
# No bare scan_status string comparisons in _workbook_parity.py
# ---------------------------------------------------------------------------

# Matches == "scanned" or in {"scanned", ...} where the string is a bare literal
_RE_BARE_SCAN_STATUS_SCANNED = re.compile(r'scan_status\s*==\s*"scanned"')
# Matches in {... "failed" ..., "timeout" ...} set comparisons
_RE_BARE_SCAN_STATUS_SET = re.compile(r'scan_status\s+in\s+\{[^}]*"(?:failed|timeout)"[^}]*\}')


def test_no_bare_scan_status_scanned_comparison() -> None:
    """WorkbookArtefactReport.scan_status comparisons must use WorkbookScanStatus members."""
    assert _WORKBOOK_PARITY_FILE.is_file(), f"_workbook_parity.py not found at expected path: {_WORKBOOK_PARITY_FILE}"
    text = _WORKBOOK_PARITY_FILE.read_text(encoding="utf-8")
    hits_scanned = _RE_BARE_SCAN_STATUS_SCANNED.findall(text)
    hits_set = _RE_BARE_SCAN_STATUS_SET.findall(text)
    all_hits = hits_scanned + hits_set
    assert not all_hits, (
        f"Found {len(all_hits)} bare scan_status string comparison(s) in "
        f"_workbook_parity.py; replace with WorkbookScanStatus.SCANNED / "
        f"WorkbookScanStatus.FAILED / WorkbookScanStatus.TIMEOUT:\n" + "\n".join(f"  {h!r}" for h in all_hits)
    )


# ---------------------------------------------------------------------------
# No local _STRICT_FROZEN = ConfigDict(...) definition in the two
# persistence-layer files; both must import STRICT_FROZEN_CONFIG from
# aeat.core
# ---------------------------------------------------------------------------

_LAYOUT_FILE = _SRC_ROOT / "adapters" / "persistence" / "storage" / "bucket" / "_layout.py"
_SECURE_OBJECTS_FILE = _SRC_ROOT / "adapters" / "persistence" / "storage" / "sql" / "_secure_object_records.py"

_RE_LOCAL_STRICT_FROZEN_DEF = re.compile(r"_STRICT_FROZEN\s*=\s*ConfigDict\s*\(")


def test_layout_uses_canonical_strict_frozen_config() -> None:
    """_layout.py must import STRICT_FROZEN_CONFIG from aeat.core, not define locally."""
    assert _LAYOUT_FILE.is_file(), f"_layout.py not found: {_LAYOUT_FILE}"
    text = _LAYOUT_FILE.read_text(encoding="utf-8")
    assert "STRICT_FROZEN_CONFIG" in text, "_layout.py does not import STRICT_FROZEN_CONFIG from aeat.core"
    assert not _RE_LOCAL_STRICT_FROZEN_DEF.search(text), (
        "_layout.py still defines a local _STRICT_FROZEN = ConfigDict(...); "
        "remove it and use the canonical STRICT_FROZEN_CONFIG import"
    )


def test_secure_objects_uses_canonical_strict_frozen_config() -> None:
    """secure_objects.py must import STRICT_FROZEN_CONFIG from aeat.core, not define locally."""
    assert _SECURE_OBJECTS_FILE.is_file(), f"secure_objects.py not found: {_SECURE_OBJECTS_FILE}"
    text = _SECURE_OBJECTS_FILE.read_text(encoding="utf-8")
    assert "STRICT_FROZEN_CONFIG" in text, "secure_objects.py does not import STRICT_FROZEN_CONFIG from aeat.core"
    assert not _RE_LOCAL_STRICT_FROZEN_DEF.search(text), (
        "secure_objects.py still defines a local _STRICT_FROZEN = ConfigDict(...); "
        "remove it and use the canonical STRICT_FROZEN_CONFIG import"
    )


# ---------------------------------------------------------------------------
# UTF_8_ENCODING enrollment - no bare encoding="utf-8" in the enrolled
# production persistence and application modules
# ---------------------------------------------------------------------------

# Matches encoding="utf-8" as a keyword argument (file I/O pattern)
_RE_BARE_ENCODING_KWARG = re.compile(r'\bencoding\s*=\s*"utf-8"')
# Matches .encode("utf-8") and .decode("utf-8") (bytes codec pattern)
_RE_BARE_ENCODE_DECODE = re.compile(r'\.(?:encode|decode)\s*\(\s*"utf-8"\s*\)')

# Enrolled UTF-8-canonicalised files. Extend this list as more modules
# are migrated to UTF_8_ENCODING.
_UTF8_ENROLLED_FILES: tuple[Path, ...] = (
    _SRC_ROOT / "adapters" / "persistence" / "storage" / "blob_store" / "_blob_store.py",
    _SRC_ROOT / "adapters" / "persistence" / "storage" / "master_key" / "_master_key.py",
    _SRC_ROOT / "adapters" / "persistence" / "storage" / "master_key" / "_recovery.py",
    _SRC_ROOT / "application" / "workflow" / "_profile_health.py",
    _SRC_ROOT / "adapters" / "outbound" / "aeat" / "sede" / "_observation_store.py",
    _SRC_ROOT / "application" / "user_profile" / "_orchestration.py",
    _SRC_ROOT / "application" / "user_profile" / "_profile_repository.py",
)


def test_utf8_encoding_enrolled_files_have_no_bare_literals() -> None:
    """The UTF-8-enrolled files must contain no bare encoding='utf-8' /
    .encode('utf-8') / .decode('utf-8') literals.  All sites must use
    UTF_8_ENCODING imported from aeat.core.external_constants."""
    hits: list[str] = []
    for path in _UTF8_ENROLLED_FILES:
        if not path.is_file():
            hits.append(f"MISSING: {path.relative_to(PROJECT_ROOT).as_posix()}")
            continue
        file_hits = _scan([path], _RE_BARE_ENCODING_KWARG) + _scan([path], _RE_BARE_ENCODE_DECODE)
        hits.extend(file_hits)
    assert not hits, (
        f"Found {len(hits)} bare 'utf-8' literal(s) in enrolled files; "
        "replace with UTF_8_ENCODING from aeat.core.external_constants:\n" + "\n".join(f"  {h}" for h in hits)
    )
