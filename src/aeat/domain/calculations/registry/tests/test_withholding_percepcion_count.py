"""Distinct-(perceptor, clave, subclave) percepcion-count primitive (#28 P02).

Modelo 190 "numero total de percepciones" is the count of DISTINCT
(perceptor NIF, clave, subclave) type-2 records (AEAT Diseno de Registros) — a
perceptor paid under two claves files two percepciones, so the figure is
``percepciones >= perceptores``, NOT the distinct-NIF perceptor count that
RET-1's ``perceptor_count`` fact materialises for Modelo 180/193. These cases
lock the new ``percepcion_count`` withholding fact against the Diseno
definition (the distinct key is the full clave-bearing tuple), not the retired
op=sum-of-quarterly-counts relation.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from .....core.aggregation import BindingAggregation, BindingAggregationOp, RowSetGroupingKind
from .....core.resources import resources
from .._schema import DataBindingDefinition, ModeloRevision
from .._withholding_bindings import WithholdingObservation, resolve_withholding_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _m190_revision() -> ModeloRevision:
    return resources().modelos.authority.snapshot("190", filing_year=2024, period="0A").revision


def _percepcion_count_binding() -> DataBindingDefinition:
    """Lift a real M190 withholding binding to the ``percepcion_count`` fact.

    Reusing a committed binding's id + grounding keeps the carrier valid; only
    the source/selector/op are lifted to exercise the distinct-count primitive.
    """
    base = next(b for b in _m190_revision().bindings if b.source == RowSetGroupingKind.WITHHOLDING)
    return base.model_copy(
        update={
            "source": RowSetGroupingKind.WITHHOLDING,
            "selector": {"fact": "percepcion_count"},
            "aggregation": BindingAggregation(op=BindingAggregationOp.COUNT_DISTINCT),
        },
    )


def _revision_with(binding: DataBindingDefinition) -> ModeloRevision:
    return _m190_revision().model_copy(update={"bindings": (binding,)})


def _obs(nif: str, clave: str, subclave: str = "") -> WithholdingObservation:
    return WithholdingObservation(
        source_id=f"{nif}:{clave}:{subclave or '-'}",
        perceptor_tax_id=nif,
        transaction_date=date(2024, 6, 1),
        clave=clave,
        subclave=subclave,
        percibido_dinerario=Decimal("1000"),
        retencion_practicada=Decimal("190"),
    )


def test_percepcion_count_counts_two_claves_for_one_perceptor_twice() -> None:
    """One perceptor paid under two claves = 2 percepciones (not 1 perceptor)."""
    binding = _percepcion_count_binding()
    resolved = resolve_withholding_binding_values(
        _revision_with(binding),
        [_obs("11111111H", "A"), _obs("11111111H", "G")],
    )
    assert resolved[binding.id] == Decimal(2)


def test_percepcion_count_counts_recurring_perceptor_clave_once() -> None:
    """The same (perceptor, clave) appearing twice (e.g. two quarters) = 1 percepcion."""
    binding = _percepcion_count_binding()
    resolved = resolve_withholding_binding_values(
        _revision_with(binding),
        [_obs("22222222J", "A"), _obs("22222222J", "A")],
    )
    assert resolved[binding.id] == Decimal(1)


def test_percepcion_count_subclave_distinguishes_percepciones() -> None:
    """Same perceptor + clave but different subclave = 2 distinct percepciones."""
    binding = _percepcion_count_binding()
    resolved = resolve_withholding_binding_values(
        _revision_with(binding),
        [_obs("33333333P", "B", "01"), _obs("33333333P", "B", "02")],
    )
    assert resolved[binding.id] == Decimal(2)


def test_percepcion_count_exceeds_distinct_perceptor_count() -> None:
    """Two perceptores, one under two claves -> 3 percepciones (percepciones > perceptores)."""
    binding = _percepcion_count_binding()
    resolved = resolve_withholding_binding_values(
        _revision_with(binding),
        [_obs("11111111H", "A"), _obs("11111111H", "G"), _obs("22222222J", "A")],
    )
    # Distinct perceptores would be 2; distinct percepciones is 3 — the figure
    # this fact must report for the M190 "numero total de percepciones" box.
    assert resolved[binding.id] == Decimal(3)
