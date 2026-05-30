"""Inventory test: inline quantize and bare Decimal(str()) enrollment gate.

Rule
----
Production modules under ``src/aeat/`` must not use:

1. ``value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`` inline.
   All callers must delegate to :func:`aeat.domain.fincas._rounding._round_to_cents`.
   W03.P18 (S358-S363) enrolled all known sites; this test asserts zero new violations.

2. ``Decimal(str(`` bare coercion patterns inline.
   All callers must delegate to :func:`aeat.core.decimal.coerce_decimal`.
   W03.P18 (S364-S367) enrolled the targeted sites.  Remaining pre-existing
   sites are tracked in ``DECIMAL_STR_PENDING`` below and will be addressed in
   follow-up Steps.  The test asserts the live violation set is a subset of the
   declared pending set.

Exclusions (permanent)
----------------------
- ``test_*.py`` files: test suites may exercise decimal behaviour directly.
- ``src/aeat/domain/fincas/_rounding.py``: the canonical _round_to_cents definition.
- ``src/aeat/core/decimal/_coerce.py``: the canonical coerce_decimal definition.
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]

_SRC_ROOT = pathlib.Path(__file__).parent

# Canonical modules exempt from their own rules.
_ROUNDING_MODULE = _SRC_ROOT / "domain" / "fincas" / "_rounding.py"
_COERCE_MODULE = _SRC_ROOT / "core" / "decimal" / "_coerce.py"

# Pattern 1: inline quantize to cent precision with ROUND_HALF_UP.
_QUANTIZE_PATTERN = re.compile(
    r'\.quantize\s*\(\s*Decimal\s*\(\s*["\']0\.01["\']\s*\)\s*,\s*rounding\s*=\s*ROUND_HALF_UP\s*\)'
)

# Pattern 2: bare Decimal(str(...)) coercion.
_DECIMAL_STR_PATTERN = re.compile(r"Decimal\s*\(\s*str\s*\(")

# ---------------------------------------------------------------------------
# Pending enrollment for Decimal(str()) — follow-up targets beyond W03.P18
# ---------------------------------------------------------------------------
# Format: POSIX path relative to repo root (src/aeat/...).
# Remove entries as their follow-up Steps land.  The test asserts that no
# NEW sites appear beyond this declared pending set.

DECIMAL_STR_PENDING: frozenset[str] = frozenset(
    {
        "src/aeat/adapters/inbound/financial/providers/_ofx.py",
        "src/aeat/adapters/outbound/google/_calc_sheets_pull.py",
        "src/aeat/application/filing/_export.py",
        "src/aeat/application/invoices/_importing.py",
        "src/aeat/application/storage/calc_sheets/_parity_harness.py",
        "src/aeat/application/verification/_verify.py",
        "src/aeat/domain/calculations/registry/_workbook_parity.py",
        "src/aeat/domain/categories/_registry.py",
        "src/aeat/domain/deadlines/_recargo.py",
        "src/aeat/domain/iva/_rates.py",
        "src/aeat/entrypoints/cli/_config/_google.py",
    }
)


def _is_excluded(path: pathlib.Path) -> bool:
    if path.name.startswith("test_"):
        return True
    return path in (_ROUNDING_MODULE, _COERCE_MODULE)


def _collect_quantize_violations() -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every inline quantize call."""
    repo_root = _SRC_ROOT.parent.parent
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if _is_excluded(path):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            if line.strip().startswith("#"):
                continue
            code_part = line.split("#")[0]
            if _QUANTIZE_PATTERN.search(code_part):
                rel = path.relative_to(repo_root).as_posix()
                violations.append(f"{rel}:{lineno}")
    return violations


def _collect_decimal_str_violations() -> list[str]:
    """Return repo-relative ``path:lineno`` strings for every bare Decimal(str()) call."""
    repo_root = _SRC_ROOT.parent.parent
    violations: list[str] = []
    for path in sorted(_SRC_ROOT.rglob("*.py")):
        if _is_excluded(path):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        lines = source.splitlines()
        for lineno, line in enumerate(lines, start=1):
            if line.strip().startswith("#"):
                continue
            code_part = line.split("#")[0]
            if _DECIMAL_STR_PATTERN.search(code_part):
                rel = path.relative_to(repo_root).as_posix()
                violations.append(f"{rel}:{lineno}")
    return violations


def test_no_inline_quantize_round_half_up() -> None:
    """Inline ``value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`` must be zero.

    All known sites use ``_round_to_cents`` from ``aeat.domain.fincas._rounding``.
    W03.P18 (S358-S363) enrolled all sites.  Any new inline call is a regression.
    """
    violations = _collect_quantize_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)"
            f" call(s) found in production code:\n  {joined}\n\n"
            "Replace each call with _round_to_cents() from aeat.domain.fincas._rounding."
        )


def test_no_bare_decimal_str_coercion() -> None:
    """Bare ``Decimal(str(`` coercion must not grow beyond the declared pending set.

    W03.P18 (S364-S367) enrolled the targeted sites.  Pre-existing follow-up
    sites are declared in ``DECIMAL_STR_PENDING``.  Any new site outside that set
    is a regression.
    """
    violations = _collect_decimal_str_violations()

    new_violations: list[str] = []
    for hit in violations:
        file_posix = hit.rsplit(":", 1)[0].replace("\\", "/")
        if file_posix not in DECIMAL_STR_PENDING:
            new_violations.append(hit)

    if new_violations:
        joined = "\n  ".join(new_violations)
        raise AssertionError(
            f"{len(new_violations)} NEW bare Decimal(str()) coercion call(s) found outside the "
            f"declared pending set:\n  {joined}\n\n"
            "Either replace each call with coerce_decimal() from aeat.core.decimal,\n"
            "or add the file to DECIMAL_STR_PENDING in test_decimal_enrollment_inventory.py\n"
            "with a comment referencing the follow-up Step."
        )
