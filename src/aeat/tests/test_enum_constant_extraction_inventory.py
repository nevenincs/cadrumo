"""Enum / named-constant extraction inventory: zero bare-literal survivors.

Asserts that the enum / named-constant migrations have no surviving
bare-string occurrences outside canonical definition sites and
documented escape hatches.

Canonical definition sites are excluded from every scan; the test
asserts the *non-canonical* production code is clean.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from ..core.paths import PROJECT_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = PROJECT_ROOT / "src" / "aeat"

# ---------------------------------------------------------------------------
# Canonical definition sites excluded from every scan.
# Each entry is the single authorised location that *defines* the constant.
# ---------------------------------------------------------------------------

_CANONICAL_DEFINITIONS: frozenset[Path] = frozenset(
    [
        # StrEnum value-string assignments (MEMBER = "value") are definitions, not usages.
        _SRC_ROOT / "core" / "aggregation.py",
        _SRC_ROOT / "application" / "operator_surface" / "_models.py",
        _SRC_ROOT / "domain" / "buckets" / "_event.py",
        # Canonical constant home for XLS_EXTENSION / XLSX_EXTENSION / LATIN_1_ENCODING
        _SRC_ROOT / "core" / "external_constants.py",
        # OracleEnvironment StrEnum definition + match validator
        _SRC_ROOT / "domain" / "calculations" / "registry" / "_live_parity.py",
        _SRC_ROOT / "application" / "registry" / "__init__.py",
    ],
)


def _production_py_files() -> list[Path]:
    """Return all non-test Python source files under src/aeat/."""
    return [
        p
        for p in _SRC_ROOT.rglob("*.py")
        if not any(part.startswith("test_") or part == "__pycache__" for part in p.parts)
        and p not in _CANONICAL_DEFINITIONS
    ]


def _scan(files: list[Path], pattern: re.Pattern[str], skip_comment_lines: bool = True) -> list[str]:
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
# No bare "ledger_transaction" runtime usage outside enum defs
# ---------------------------------------------------------------------------

# Matches bare "ledger_transaction" string literals used as runtime dict keys,
# function args, or comparisons — NOT StrEnum MEMBER = "value" assignments
# (those files are in _CANONICAL_DEFINITIONS and excluded from the scan).
_RE_LEDGER_TRANSACTION = re.compile(r'"ledger_transaction"')


def test_no_bare_ledger_transaction_literals() -> None:
    """Runtime sites must use AggregationSourceKind.LEDGER_TRANSACTION, not the bare string."""
    files = _production_py_files()
    hits = _scan(files, _RE_LEDGER_TRANSACTION)
    assert not hits, (
        f"Found {len(hits)} bare 'ledger_transaction' literal(s) outside canonical definition:\n"
        + "\n".join(f"  {h}" for h in hits)
    )


# ---------------------------------------------------------------------------
# No bare ".xls" runtime usage outside canonical extension def
# ---------------------------------------------------------------------------

_RE_XLS_BARE = re.compile(r'"\\.xls"')


def test_no_bare_xls_extension_literals() -> None:
    """Runtime .xls usage must go through XLS_EXTENSION constant."""
    files = _production_py_files()
    hits = _scan(files, _RE_XLS_BARE)
    assert not hits, f"Found {len(hits)} bare '.xls' literal(s) outside canonical definition:\n" + "\n".join(
        f"  {h}" for h in hits
    )


# ---------------------------------------------------------------------------
# No duplicate SEDE_BODY_ENCODING = "latin-1" outside _browser_constants
# ---------------------------------------------------------------------------

_BROWSER_CONSTANTS = _SRC_ROOT / "adapters" / "outbound" / "aeat" / "sede" / "_browser_constants.py"

_RE_SEDE_BODY_ENCODING_DEF = re.compile(r'SEDE_BODY_ENCODING\s*:\s*Final\[str\]\s*=\s*"latin-1"')


def test_no_duplicate_sede_body_encoding_definition() -> None:
    """SEDE_BODY_ENCODING definition must exist only in _browser_constants.py."""
    # Verify the canonical site still defines it (not deleted by accident)
    if _BROWSER_CONSTANTS.is_file():
        canonical_text = _BROWSER_CONSTANTS.read_text(encoding="utf-8", errors="replace")
        assert "SEDE_BODY_ENCODING" in canonical_text, (
            "_browser_constants.py no longer exports SEDE_BODY_ENCODING; update callers and this test."
        )

    # Verify no other production file re-defines SEDE_BODY_ENCODING as a bare "latin-1"
    non_canonical = [p for p in _production_py_files() if p != _BROWSER_CONSTANTS]
    hits = _scan(non_canonical, _RE_SEDE_BODY_ENCODING_DEF)
    assert not hits, f"Found {len(hits)} duplicate SEDE_BODY_ENCODING = 'latin-1' definition(s):\n" + "\n".join(
        f"  {h}" for h in hits
    )


# ---------------------------------------------------------------------------
# No bare "production" string used as OracleEnvironment bypass outside
# the match validator and TOML/config defaults
# ---------------------------------------------------------------------------

# Matches environment="production" or environment == "production" call patterns
# but NOT: StrEnum PRODUCTION = "production", docstrings, or the match validator
# case arm.
_RE_PRODUCTION_ENV_BYPASS = re.compile(r'environment\s*=\s*"production"')


def test_no_bare_production_oracle_environment_bypass() -> None:
    """Oracle environment= kwargs must use OracleEnvironment.PRODUCTION, not the bare string."""
    files = _production_py_files()
    hits = _scan(files, _RE_PRODUCTION_ENV_BYPASS)
    assert not hits, (
        f"Found {len(hits)} bare environment='production' literal(s); "
        "use OracleEnvironment.PRODUCTION:\n" + "\n".join(f"  {h}" for h in hits)
    )


# ---------------------------------------------------------------------------
# No bare "invoice" runtime usage in source-kind context
# ---------------------------------------------------------------------------

# Matches bare "invoice" used specifically in source-kind comparisons or
# assignments (``== "invoice"``, ``source="invoice"``, ``source_kind == "invoice"``).
# Does NOT match scope="invoice", name="invoice", or StrEnum INVOICE = "invoice"
# value assignments.
_RE_INVOICE_SOURCE_KIND = re.compile(r'(?:==\s*"invoice"|source_kind\s*==\s*"invoice"|source\s*=\s*"invoice")')


def test_no_bare_invoice_source_kind_literals() -> None:
    """Runtime source-kind code must not revive the retired bare invoice alias."""
    files = _production_py_files()
    hits = _scan(files, _RE_INVOICE_SOURCE_KIND)
    assert not hits, (
        f"Found {len(hits)} bare 'invoice' literal(s) in source-kind context; "
        "use payable_invoice, collectible_invoice, or purchase_invoice_evidence:\n"
        + "\n".join(f"  {h}" for h in hits)
    )
