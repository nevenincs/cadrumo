"""Enum / named-constant extraction inventory: zero bare-literal survivors.

Asserts that the enum / named-constant migrations have no surviving
bare-string occurrences outside canonical definition sites and
documented escape hatches.

Canonical definition sites are excluded from every scan; the test
asserts the *non-canonical* production code is clean.

See Also:
    :mod:`~tests._inventory`
        Provides the package-file and regex inventory helpers used by this
        literal-survivor gate.
    :class:`~core.aggregation.BindingSourceKind`
        Canonical source-kind enum whose value strings must not drift back into
        runtime literals.
    :mod:`~core.external_constants`
        Central constant registry for external encodings, extensions, MIME
        strings, hostnames, and route fragments.

The source-kind enum is the single closed taxonomy for binding sources; this
inventory keeps that consolidation from regressing back into scattered
runtime literals.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

import pytest

from ._inventory import SRC_CADRUMO, non_test_package_python_files, regex_line_hits

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_SRC_ROOT = SRC_CADRUMO

# ---------------------------------------------------------------------------
# Canonical definition sites excluded from every scan.
# Each entry is the single authorised location that *defines* the constant.
# ---------------------------------------------------------------------------

_CANONICAL_DEFINITIONS: frozenset[Path] = frozenset(
    [
        # StrEnum value-string assignments (MEMBER = "value") are definitions, not usages.
        _SRC_ROOT / "core" / "aggregation.py",
        _SRC_ROOT / "application" / "operator_surface" / "_models.py",
        _SRC_ROOT / "domain" / "buckets" / "event.py",
        # Canonical constant home for XLS_EXTENSION / XLSX_EXTENSION / LATIN_1_ENCODING
        _SRC_ROOT / "core" / "external_constants.py",
        # OracleEnvironment StrEnum definition + match validator
        _SRC_ROOT / "domain" / "calculations" / "registry" / "live_parity.py",
        _SRC_ROOT / "application" / "registry" / "__init__.py",
    ],
)


def _production_py_files() -> tuple[Path, ...]:
    """Return all non-test Python source files under src/cadrumo/."""
    return tuple(p for p in non_test_package_python_files(include_data=True) if p not in _CANONICAL_DEFINITIONS)


def _scan(files: Iterable[Path], pattern: re.Pattern[str], skip_comment_lines: bool = True) -> list[str]:
    return regex_line_hits(files, pattern, skip_comment_lines=skip_comment_lines)


# ---------------------------------------------------------------------------
# No bare "ledger_transaction" runtime usage outside enum defs
# ---------------------------------------------------------------------------

# Matches bare "ledger_transaction" string literals used as runtime dict keys,
# function args, or comparisons — NOT StrEnum MEMBER = "value" assignments
# (those files are in _CANONICAL_DEFINITIONS and excluded from the scan).
_RE_LEDGER_TRANSACTION = re.compile(r'"ledger_transaction"')


def test_no_bare_ledger_transaction_literals() -> None:
    """Runtime sites must use BindingSourceKind.LEDGER_TRANSACTION, not the bare string."""
    files = _production_py_files()
    hits = _scan(files, _RE_LEDGER_TRANSACTION)
    assert not hits, (
        f"Found {len(hits)} bare 'ledger_transaction' literal(s) outside canonical definition:\n"
        + "\n".join(f"  {h}" for h in hits)
    )


# ---------------------------------------------------------------------------
# No bare ".xls" runtime usage outside canonical extension def
# ---------------------------------------------------------------------------

_RE_XLS_BARE = re.compile(r'"\.xls"')

# The one authorised escape was the workbook-parity Literal alias: ``Literal[...]``
# accepts only literal forms, never a ``Final[Literal[...]]`` constant, so that
# static extension type alias could not route through XLS_EXTENSION. The module
# carrying it has since moved out of the product package entirely, and this
# scan reads src/cadrumo/ only, so the escape excluded a path the scan can
# no longer reach. Its guard said what to do when the justifying construct went
# away -- remove the escape -- so there is no exclusion left to justify, and the
# gate scans production whole.


def test_no_bare_xls_extension_literals() -> None:
    """Runtime .xls usage must go through XLS_EXTENSION constant."""
    hits = _scan(_production_py_files(), _RE_XLS_BARE)
    assert not hits, f"Found {len(hits)} bare '.xls' literal(s) outside canonical definition:\n" + "\n".join(
        f"  {h}" for h in hits
    )


def test_bare_literal_patterns_discriminate() -> None:
    """Positive control: each scan pattern must match its target and reject near-misses.

    A pattern that matches nothing passes the survivor gates vacuously. The
    shipped ``.xls`` pattern carried a doubled backslash and could never match
    a real ``".xls"`` literal, so the gate reported clean over four live sites.
    """
    must_match: tuple[tuple[re.Pattern[str], str], ...] = (
        (_RE_XLS_BARE, 'suffix = ".xls"'),
        (_RE_XLS_BARE, 'ALLOWED = (".xls", ".xlsx")'),
        (_RE_LEDGER_TRANSACTION, 'source = "ledger_transaction"'),
    )
    must_not_match: tuple[tuple[re.Pattern[str], str], ...] = (
        (_RE_XLS_BARE, 'suffix = ".xlsx"'),
        (_RE_XLS_BARE, "suffix = XLS_EXTENSION"),
        (_RE_LEDGER_TRANSACTION, "source = BindingSourceKind.LEDGER_TRANSACTION"),
    )
    for pattern, line in must_match:
        assert pattern.search(line), f"{pattern.pattern!r} failed to match its target {line!r}"
    for pattern, line in must_not_match:
        assert not pattern.search(line), f"{pattern.pattern!r} wrongly matched {line!r}"


def test_literal_survivor_scan_reads_a_non_empty_corpus() -> None:
    """A survivor gate over zero files would pass vacuously."""
    files = _production_py_files()
    assert len(files) > 500, f"expected the production corpus, scanned only {len(files)} files"


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
        "use payable_invoice, collectible_invoice, or purchase_invoice_evidence:\n" + "\n".join(f"  {h}" for h in hits)
    )
