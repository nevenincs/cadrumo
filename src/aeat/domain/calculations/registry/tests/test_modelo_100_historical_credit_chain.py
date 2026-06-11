"""The M100 2020-2023 total-pagos-a-cuenta credit chain is wired and grounded.

The earlier revisions (2020-2023) historically declared the 0596/0597/0609 credit
casillas as bare definitions: 0609 carried no formula (so it never summed) and
0596/0597 carried no binding (so the M111/M123 retenciones relations targeting
them were inert). This module pins the wiring that makes the chain live and
consistent with the 2024/2025 pattern:

  * 0596 ("Por rendimientos del trabajo") binds the M111 retenciones relation.
  * 0597 ("Por rendimientos del capital mobiliario") binds the M123 retenciones
    relation.
  * 0609 ("Total pagos a cuenta") is computed by a sum formula over the credit
    casillas, including the now-bound 0596/0597.

This is a structural-wiring assertion (graph shape + provenance), not a numeric
oracle: it proves the bound credits flow into the total and that the formula is
legally grounded, without hand-computing a tax figure. The 2024/2025 revisions
exercise the identical chain through the registry scenario suite.
"""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._loader import load_registry_tree

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REGISTRY_ROOT = bundled_path("registry", "aeat")
_YEARS = ("2020", "2021", "2022", "2023")

# The credit casillas the total-pagos-a-cuenta formula sums (form-native order).
_CREDIT_SUM_CASILLAS = (
    "0592",
    "0593",
    "0594",
    "0596",
    "0597",
    "0598",
    "0599",
    "0600",
    "0601",
    "0602",
    "0603",
    "0604",
    "0605",
    "0606",
)


def _m100_revision(year: str):
    modelos, _catalogues = load_registry_tree(_REGISTRY_ROOT)
    m100 = next(m for m in modelos if m.id == "100")
    revision = m100.revisions.get(year)
    assert revision is not None, f"M100 revision {year!r} not found in the registry"
    return revision


@pytest.mark.parametrize("year", _YEARS)
def test_0609_is_computed_by_the_total_pagos_formula(year: str) -> None:
    """0609 is a computed casilla whose formula sums the credit casillas."""
    revision = _m100_revision(year)
    c0609 = next((c for c in revision.casillas if c.id == "0609"), None)
    assert c0609 is not None, f"M100 {year} casilla 0609 missing"
    assert getattr(c0609, "input_kind", None) == "computed", (
        f"M100 {year} 0609 must be computed (was {getattr(c0609, 'input_kind', None)!r})"
    )
    expected_formula = f"renta-{year}-total-pagos-a-cuenta"
    assert c0609.formula == expected_formula

    formula = next((f for f in revision.formulas if f.id == expected_formula), None)
    assert formula is not None, f"M100 {year} formula {expected_formula!r} missing"
    assert formula.target == "0609"
    summed = tuple(arg.casilla for arg in formula.expression.args)
    assert summed == _CREDIT_SUM_CASILLAS, (
        f"M100 {year} total-pagos formula must sum the credit casillas in order; "
        f"got {summed!r}"
    )


@pytest.mark.parametrize("year", _YEARS)
def test_credit_casillas_bind_their_retencion_relations(year: str) -> None:
    """0596/0597 bind the M111/M123 retenciones relations (previously inert)."""
    revision = _m100_revision(year)
    binding_ids = {b.id for b in revision.bindings}

    c0596 = next((c for c in revision.casillas if c.id == "0596"), None)
    c0597 = next((c for c in revision.casillas if c.id == "0597"), None)
    assert c0596 is not None and c0597 is not None

    assert getattr(c0596, "input_kind", None) == "bound"
    assert c0596.binding == f"renta-{year}-modelo-111-retenciones-periodicas"
    assert c0596.binding in binding_ids, (
        f"M100 {year} 0596 binds {c0596.binding!r} which is not a declared binding"
    )

    assert getattr(c0597, "input_kind", None) == "bound"
    assert c0597.binding == f"renta-{year}-modelo-123-retenciones-periodicas"
    assert c0597.binding in binding_ids, (
        f"M100 {year} 0597 binds {c0597.binding!r} which is not a declared binding"
    )


@pytest.mark.parametrize("year", _YEARS)
def test_total_pagos_formula_is_legally_grounded(year: str) -> None:
    """The total-pagos formula cites the withholding/pagos-a-cuenta provisions."""
    revision = _m100_revision(year)
    formula = next(f for f in revision.formulas if f.id == f"renta-{year}-total-pagos-a-cuenta")
    # ley-35-2006 art.99 (obligation + pagos a cuenta credit) and the rd-439-2007
    # withholding-procedure articles are the binding grounding for the credit total.
    assert "ley-35-2006:art-99" in formula.legal_refs
    assert any(ref.startswith("rd-439-2007:art-1") for ref in formula.legal_refs)
