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

from .....core.casilla_id import validated_casilla_id
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_YEARS = ("2020", "2021", "2022", "2023")


_C0596 = validated_casilla_id("0596", surface="test_modelo_100_historical_credit_chain casilla id")
_C0597 = validated_casilla_id("0597", surface="test_modelo_100_historical_credit_chain casilla id")
_C0609 = validated_casilla_id("0609", surface="test_modelo_100_historical_credit_chain casilla id")

# The credit casillas the total-pagos-a-cuenta formula sums (form-native order).
_CREDIT_SUM_CASILLAS = (
    validated_casilla_id("0592", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0593", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0594", surface="test_modelo_100_historical_credit_chain casilla id"),
    _C0596,
    _C0597,
    validated_casilla_id("0598", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0599", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0600", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0601", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0602", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0603", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0604", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0605", surface="test_modelo_100_historical_credit_chain casilla id"),
    validated_casilla_id("0606", surface="test_modelo_100_historical_credit_chain casilla id"),
)


def _m100_revision(year: str):
    m100, _catalogues = _committed_modelo("100")
    revision = m100.revisions.get(year)
    assert revision is not None, f"M100 revision {year!r} not found in the registry"
    return revision


@pytest.mark.parametrize("year", _YEARS)
def test_historical_credit_chain_binds_and_grounds_total_pagos_formula(year: str) -> None:
    """0596/0597 bind retenciones, and 0609 sums the grounded credit chain."""
    revision = _m100_revision(year)
    binding_ids = {b.id for b in revision.bindings}

    c0609 = next((c for c in revision.casillas if c.id == _C0609), None)
    assert c0609 is not None, f"M100 {year} casilla 0609 missing"
    assert getattr(c0609, "input_kind", None) == "computed", (
        f"M100 {year} 0609 must be computed (was {getattr(c0609, 'input_kind', None)!r})"
    )
    expected_formula = f"renta-{year}-total-pagos-a-cuenta"
    assert c0609.formula == expected_formula

    formula = next((f for f in revision.formulas if f.id == expected_formula), None)
    assert formula is not None, f"M100 {year} formula {expected_formula!r} missing"
    assert formula.target_casilla_id == _C0609
    summed = tuple(arg.casilla_id for arg in formula.expression.args)
    assert summed == _CREDIT_SUM_CASILLAS, (
        f"M100 {year} total-pagos formula must sum the credit casillas in order; got {summed!r}"
    )

    c0596 = next((c for c in revision.casillas if c.id == _C0596), None)
    c0597 = next((c for c in revision.casillas if c.id == _C0597), None)
    assert c0596 is not None and c0597 is not None

    assert getattr(c0596, "input_kind", None) == "bound"
    assert c0596.binding == f"renta-{year}-modelo-111-retenciones-periodicas"
    assert c0596.binding in binding_ids, f"M100 {year} 0596 binds {c0596.binding!r} which is not a declared binding"

    assert getattr(c0597, "input_kind", None) == "bound"
    assert c0597.binding == f"renta-{year}-modelo-123-retenciones-periodicas"
    assert c0597.binding in binding_ids, f"M100 {year} 0597 binds {c0597.binding!r} which is not a declared binding"

    # ley-35-2006 art.99 (obligation + pagos a cuenta credit) and the rd-439-2007
    # withholding-procedure articles are the binding grounding for the credit total.
    assert "ley-35-2006:art-99" in formula.legal_refs
    assert any(ref.startswith("rd-439-2007:art-1") for ref in formula.legal_refs)
