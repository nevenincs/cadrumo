"""Inventory test: inline quantize and bare Decimal(str()) enrollment gate.

Rule
----
Production modules under ``src/aeat/`` must not use:

1. ``value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)`` inline.
   All callers must delegate to :func:`aeat.core.money.round_to_cents`.

2. ``Decimal(str(`` bare coercion patterns inline.
   All callers must delegate to :func:`aeat.core.decimal.coerce_decimal`.

Exclusions (permanent)
----------------------
- ``test_*.py`` files: test suites may exercise decimal behaviour directly.
- ``src/aeat/core/money/__init__.py``: the canonical round_to_cents definition.
- ``src/aeat/core/decimal/_coerce.py``: the canonical coerce_decimal definition.
"""

from __future__ import annotations

import pathlib
import re

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_SRC_ROOT = pathlib.Path(__file__).parent.parent

# Canonical modules exempt from their own rules.
_ROUNDING_MODULE = _SRC_ROOT / "core" / "money" / "__init__.py"
_COERCE_MODULE = _SRC_ROOT / "core" / "decimal" / "_coerce.py"

# Pattern 1: inline quantize to cent precision with ROUND_HALF_UP.
_QUANTIZE_PATTERN = re.compile(
    r'\.quantize\s*\(\s*Decimal\s*\(\s*["\']0\.01["\']\s*\)\s*,\s*rounding\s*=\s*ROUND_HALF_UP\s*\)',
)

# Pattern 2: bare Decimal(str(...)) coercion.
_DECIMAL_STR_PATTERN = re.compile(r"Decimal\s*\(\s*str\s*\(")


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

    All known sites use ``round_to_cents`` from ``aeat.core.money``.
    Any new inline call is a regression.
    """
    violations = _collect_quantize_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} inline quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)"
            f" call(s) found in production code:\n  {joined}\n\n"
            "Replace each call with round_to_cents() from aeat.core.money.",
        )


def test_no_bare_decimal_str_coercion() -> None:
    """Bare ``Decimal(str(`` coercion must be zero in production code.

    All call-sites must delegate to :func:`aeat.core.decimal.coerce_decimal`.
    The only permitted occurrence lives in the canonical helper module itself,
    which is excluded above.
    """
    violations = _collect_decimal_str_violations()
    if violations:
        joined = "\n  ".join(violations)
        raise AssertionError(
            f"{len(violations)} bare Decimal(str()) coercion call(s) found in production code:\n  {joined}\n\n"
            "Replace each call with coerce_decimal() from aeat.core.decimal.",
        )
