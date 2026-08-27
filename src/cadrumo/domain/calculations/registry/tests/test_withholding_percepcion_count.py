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

from .....core.aggregation import BindingAggregation, BindingAggregationOp, BindingSourceKind, RetencionClave
from ..schema import DataBindingDefinition, ModeloRevision
from ..schema_references import PeriodSelector
from ..withholding_bindings import WithholdingObservation, resolve_withholding_binding_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_PERCEPCION_BINDING_ID = "modelo-190-percepciones-anual"
_M190_WITHHOLDING_LEGAL_REFS = (
    "ley-35-2006:art-99",
    "orden-eha-3127-2009:art-1",
    "orden-hac-1431-2025:art-2",
    "rd-439-2007:art-108",
    "rd-439-2007:art-80",
    "ley-35-2006:art-101",
    "rd-439-2007:art-86",
    "ley-58-2003:art-93",
)
_M190_WITHHOLDING_SOURCE_REFS = (
    "aeat-dr-190-2025",
    "aeat-modelo-190-instructions-2025",
    "boe-modelo-190-2025-form",
)


def _revision_with(binding: DataBindingDefinition) -> ModeloRevision:
    return ModeloRevision(
        id="2024-y-siguientes",
        localization_key="test.schema.revision.2024-y-siguientes.label",
        valid_from=date(2024, 1, 1),
        period_selector=PeriodSelector(year_from=2024, periods=("0A",)),
        legal_refs=_M190_WITHHOLDING_LEGAL_REFS,
        source_refs=_M190_WITHHOLDING_SOURCE_REFS,
        bindings=(binding,),
    )


def _percepcion_count_binding() -> DataBindingDefinition:
    return DataBindingDefinition(
        id=_PERCEPCION_BINDING_ID,
        source=BindingSourceKind.WITHHOLDING,
        selector={"fact": "percepcion_count"},
        aggregation=BindingAggregation(op=BindingAggregationOp.COUNT_DISTINCT),
        legal_refs=_M190_WITHHOLDING_LEGAL_REFS,
        source_refs=_M190_WITHHOLDING_SOURCE_REFS,
    )


def _obs(nif: str, clave: str, subclave: str = "") -> WithholdingObservation:
    return WithholdingObservation(
        source_id=f"{nif}:{clave}:{subclave or '-'}",
        perceptor_tax_id=nif,
        transaction_date=date(2024, 6, 1),
        clave=RetencionClave(clave),
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
