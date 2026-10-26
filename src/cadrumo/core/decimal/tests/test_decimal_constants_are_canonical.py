"""The shared Decimal constants have exactly one definition each.

Thirty-one modules declared their own private copies before these were
centralised. A duplicated constant drifts, and the copy nobody updated keeps
producing the old value while still looking right at its call site.

The sharper hazard this gate protects is the one that motivated the split
between ``ZERO`` and ``MONEY_ZERO``: ``_ZERO`` meant ``Decimal("0")`` in
twenty-two modules and ``Decimal("0.00")`` in four. Those compare equal, so no
equality test would have caught a module reaching the wrong one, while Decimal
arithmetic propagates the larger scale and changes how the result renders.
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path
from typing import Final

import pytest

from ..constants import HUNDRED, MONEY_ZERO, ONE, ZERO

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parents[3]

#: Literals that now have a canonical home.
_CANONICAL_LITERALS: Final[frozenset[str]] = frozenset({"0", "0.00", "1", "100"})

#: A constant is a duplicate when its NAME describes the number rather than a
#: domain concept. `_ONE_HUNDRED`, `_PERCENT` and `_PCT_SCALE` all name the
#: value 100 and are duplicates of :data:`HUNDRED`.
#:
#: A constant named for what it MEANS is a distinct authority that happens to
#: hold the same number, and merging it would tie a domain rule to an
#: arithmetic constant. `PERCENTAGE_MAX` and `UNIT_PROPORTION_MAX` are declared
#: bounds on their types; `_MAX_IVA_RATE_FRACTION` bounds a rate;
#: `_FULL_PERCENTAGE` and `_FULL_BUSINESS_PROPORTION` name a whole share. Those
#: are deliberately out of scope, which is why this gate keys on the name.
_VALUE_DESCRIPTIVE: Final[frozenset[str]] = frozenset(
    {"zero", "one", "hundred", "onehundred", "percent", "pct", "pctscale", "moneyzero"}
)


def _names_the_number(name: str) -> bool:
    """True when the identifier describes its literal rather than a concept."""
    return name.strip("_").replace("_", "").lower() in _VALUE_DESCRIPTIVE


def test_the_canonical_constants_are_what_they_claim() -> None:
    """Pin the values, so the scan below cannot pass over a renamed concept."""
    assert Decimal("0") == ZERO
    assert Decimal("0.00") == MONEY_ZERO
    assert Decimal("1") == ONE
    assert Decimal("100") == HUNDRED


def test_the_two_zeroes_stay_distinguishable_by_scale() -> None:
    """Equality does not separate them; the exponent does, and so does rendering.

    If a future edit made ``MONEY_ZERO`` an alias of ``ZERO``, every equality
    assertion in the tree would keep passing while amounts seeded from it began
    rendering with no decimals.
    """
    assert ZERO == MONEY_ZERO
    assert ZERO.as_tuple().exponent == 0
    assert MONEY_ZERO.as_tuple().exponent == -2
    assert str(ZERO + Decimal("5")) == "5"
    assert str(MONEY_ZERO + Decimal("5")) == "5.00"


def _duplicate_definitions(path: Path) -> list[str]:
    """Return module-level names bound to a literal that has a canonical home."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if not isinstance(target, ast.Name):
            continue
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Name)
            and value.func.id == "Decimal"
            and len(value.args) == 1
            and isinstance(value.args[0], ast.Constant)
            and value.args[0].value in _CANONICAL_LITERALS
            and _names_the_number(target.id)
        ):
            found.append(target.id)
    return found


def test_no_module_redeclares_a_canonical_decimal_constant() -> None:
    """`core.decimal.constants` is the only module that may bind these literals."""
    modules = [
        path for path in _PACKAGE_ROOT.rglob("*.py") if "tests" not in path.parts and path.name != "constants.py"
    ]

    assert len(modules) > 500, (
        f"only {len(modules)} modules were enumerated; the scan collapsed, so an empty "
        "result below would mean 'nothing was searched' rather than 'no duplicates exist'"
    )

    offenders = {
        path.relative_to(_PACKAGE_ROOT).as_posix(): names for path in modules if (names := _duplicate_definitions(path))
    }

    assert offenders == {}, (
        f"module(s) redeclare a Decimal constant that has a canonical home in core.decimal.constants: {offenders}"
    )
