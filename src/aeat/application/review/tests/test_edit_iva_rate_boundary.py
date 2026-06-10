"""Tests for the V-3 review-edit boundary tightening.

Confirms that ``--set iva.rate=NN`` rejects values outside the
substrate-known IVA slot percentages (``0`` / ``4`` / ``10`` /
``21``) and that ``--set retention.rate=NN`` is bounded to ``[0,
100]``. The audit's V-3 finding warned that arbitrary Decimal
rates could leak into ledger records via the review-edit boundary;
this test suite is the regression guard.

Also gates that ``_edit.py`` contains no hardcoded IVA-rate frozenset
literal (the closed set must derive from
:func:`aeat.domain.invoices.numeric_iva_rate_percentages`).
"""

from __future__ import annotations

import ast
from decimal import Decimal
from pathlib import Path

import pytest

from ....domain.invoices import numeric_iva_rate_percentages
from .._edit import _INVOICE_IVA_RATE_ALLOWED, InvoiceEditSpec
from .._errors import EditParseError

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("value", ["0", "4", "10", "21"])
def test_invoice_edit_iva_rate_accepts_canonical_substrate_slots(value: str) -> None:
    spec = InvoiceEditSpec.from_strings([f"iva.rate={value}"])
    assert spec.iva_rate == Decimal(value)


@pytest.mark.parametrize("bad_value", ["5", "7", "12", "15", "16", "21.5", "100"])
def test_invoice_edit_iva_rate_rejects_non_canonical_values(bad_value: str) -> None:
    with pytest.raises(EditParseError, match=r"unsupported-iva-rate") as excinfo:
        InvoiceEditSpec.from_strings([f"iva.rate={bad_value}"])
    assert "unsupported-iva-rate" in str(excinfo.value.reason)


def test_invoice_edit_iva_rate_rejects_negative_decimal() -> None:
    with pytest.raises(EditParseError, match=r"iva|rate|invalid"):
        InvoiceEditSpec.from_strings(["iva.rate=-21"])


def test_invoice_edit_iva_rate_rejects_garbage_string() -> None:
    with pytest.raises(EditParseError, match=r"iva|rate|invalid"):
        InvoiceEditSpec.from_strings(["iva.rate=twenty-one"])


@pytest.mark.parametrize("value", ["0", "7", "15", "19", "47", "100"])
def test_invoice_edit_retention_rate_accepts_values_in_range(value: str) -> None:
    spec = InvoiceEditSpec.from_strings([f"retention.rate={value}"])
    assert spec.retention_rate == Decimal(value)


@pytest.mark.parametrize("bad_value", ["-1", "101", "150", "1000"])
def test_invoice_edit_retention_rate_rejects_out_of_range_values(bad_value: str) -> None:
    with pytest.raises(EditParseError, match=r"retention-rate-out-of-range") as excinfo:
        InvoiceEditSpec.from_strings([f"retention.rate={bad_value}"])
    assert "retention-rate-out-of-range" in str(excinfo.value.reason)


def test_invoice_edit_with_canonical_iva_and_retention_round_trips() -> None:
    spec = InvoiceEditSpec.from_strings(["base=100.00", "iva.rate=21", "iva.amount=21.00", "retention.rate=15"])
    assert spec.base == Decimal("100.00")
    assert spec.iva_rate == Decimal("21")
    assert spec.iva_amount == Decimal("21.00")
    assert spec.retention_rate == Decimal("15")


# ---------------------------------------------------------------------------
# Derivation gate — _INVOICE_IVA_RATE_ALLOWED must track the IvaRate enum
# ---------------------------------------------------------------------------


def test_invoice_iva_rate_allowed_equals_helper() -> None:
    """``_INVOICE_IVA_RATE_ALLOWED`` is identical to the helper's return value.

    Identity test: the module-level constant must be derived from
    :func:`numeric_iva_rate_percentages`, not a local literal.  If the two
    diverge the closed-taxonomy duplicate defect has been reintroduced.
    """
    assert numeric_iva_rate_percentages() == _INVOICE_IVA_RATE_ALLOWED


def test_no_bare_iva_rate_frozenset_literal_in_edit_module() -> None:
    """``_edit.py`` must not contain a hardcoded ``{0, 4, 10, 21}`` frozenset.

    AST gate: parses the real source so any future re-introduction of the
    literal set triggers an immediate failure.  The four integer-percentage
    literals ``"0"``, ``"4"``, ``"10"``, ``"21"`` must not co-occur as
    ``Decimal(...)`` constants inside a single ``frozenset(...)`` or
    ``set`` literal call in the module body.
    """
    repo_root = Path(__file__).parents[5]
    source = (repo_root / "src/aeat/application/review/_edit.py").read_text(encoding="utf-8")
    tree = ast.parse(source)

    _IVA_RATE_LITERAL_STRINGS = {"0", "4", "10", "21"}

    def _decimal_string_constants(call_node: ast.Call) -> set[str]:
        """Collect all string args to ``Decimal(...)`` calls in an AST subtree."""
        found: set[str] = set()
        for n in ast.walk(call_node):
            if not isinstance(n, ast.Call):
                continue
            func = n.func
            fname = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
            if fname == "Decimal" and n.args and isinstance(n.args[0], ast.Constant):
                found.add(str(n.args[0].value))
        return found

    offenders: list[str] = []
    for node in ast.walk(tree):
        # Match frozenset({...}) or frozenset(set(...)) call expressions
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        fname = func.id if isinstance(func, ast.Name) else (func.attr if isinstance(func, ast.Attribute) else "")
        if fname not in {"frozenset", "set"}:
            continue
        # Collect all Decimal string constants anywhere under this call
        literals = _decimal_string_constants(node)
        if _IVA_RATE_LITERAL_STRINGS.issubset(literals):
            offenders.append(
                f"_edit.py:{node.lineno}: bare IVA-rate frozenset literal "
                f"{{0, 4, 10, 21}}; use numeric_iva_rate_percentages() instead"
            )

    assert offenders == [], (
        "Hardcoded IVA-rate frozenset literals found in _edit.py; "
        "replace with numeric_iva_rate_percentages():\n" + "\n".join(offenders)
    )
