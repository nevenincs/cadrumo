"""Tier 1 round-trip tests for the small annual-summary receivers 190 and 193.

Modelos 190 and 193 are pure receivers: their casilla schemas declare
only output totals (no taxpayer-input casillas), and every formula
expression sources directly from cross-modelo relations resolved
upstream. Their Tier 1 contract is therefore "given concrete
relation values, produce concrete output casilla values" — the
receiver's formula composition is the unit under test, separate
from the chain resolver which produces the relation values.

Modelo 190 (annual summary of 111 worker / professional withholdings)
declares three output casillas:

- ``decl.total-percepciones`` = sum of the nine perception-count
  relations (trabajo dinerario, trabajo especie, ..., derechos
  imagen)
- ``decl.percepciones-total`` = sum of the nine importe relations
- ``decl.retenciones-total`` = copy of the single retenciones relation

Modelo 193 (annual summary of 123 capital-mobiliario withholdings)
declares three output casillas, each a single-relation copy:

- ``decl.total-perceptores`` = copy of perceptores-anual
- ``decl.base-total`` = copy of base-anual
- ``decl.retenciones-total`` = copy of retenciones-anual
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from aeat.core.paths import PROJECT_ROOT

from ._formula_runtime import calculate_registry_snapshot
from ._loader import load_registry_tree
from ._snapshot import build_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]

_REGISTRY_ROOT = PROJECT_ROOT / "registry" / "aeat"


def test_modelo_190_aggregates_nine_perception_relations_into_total_casillas() -> None:
    """The three 190 totals are sum / sum / copy across the nineteen 111 relations."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "190")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="0A")

    perception_relations = (
        "modelo-190-rel-111-trabajo-dinerario-percepciones-anual",
        "modelo-190-rel-111-trabajo-especie-percepciones-anual",
        "modelo-190-rel-111-actividades-dinerario-percepciones-anual",
        "modelo-190-rel-111-actividades-especie-percepciones-anual",
        "modelo-190-rel-111-premios-dinerario-percepciones-anual",
        "modelo-190-rel-111-premios-especie-percepciones-anual",
        "modelo-190-rel-111-ganancias-dinerario-percepciones-anual",
        "modelo-190-rel-111-ganancias-especie-percepciones-anual",
        "modelo-190-rel-111-derechos-imagen-percepciones-anual",
    )
    importe_relations = (
        "modelo-190-rel-111-trabajo-dinerario-importe-anual",
        "modelo-190-rel-111-trabajo-especie-importe-anual",
        "modelo-190-rel-111-actividades-dinerario-importe-anual",
        "modelo-190-rel-111-actividades-especie-importe-anual",
        "modelo-190-rel-111-premios-dinerario-importe-anual",
        "modelo-190-rel-111-premios-especie-importe-anual",
        "modelo-190-rel-111-ganancias-dinerario-importe-anual",
        "modelo-190-rel-111-ganancias-especie-importe-anual",
        "modelo-190-rel-111-derechos-imagen-importe-anual",
    )
    relation_values: dict[str, Decimal] = {}
    # 1 perceptor on each of the nine perception relations -> total = 9.
    for rel in perception_relations:
        relation_values[rel] = Decimal("1")
    # Distinct importe values so the sum is verifiable: 100, 200, ..., 900.
    importe_steps = (
        Decimal("100.00"),
        Decimal("200.00"),
        Decimal("300.00"),
        Decimal("400.00"),
        Decimal("500.00"),
        Decimal("600.00"),
        Decimal("700.00"),
        Decimal("800.00"),
        Decimal("900.00"),
    )
    for rel, value in zip(importe_relations, importe_steps, strict=True):
        relation_values[rel] = value
    # The single retenciones relation: 12 000 € total.
    relation_values["modelo-190-rel-111-retenciones-anual"] = Decimal("12000.00")

    date_context = {"filing_period": date(2026, 1, 31)}
    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context=date_context,
        relation_values=relation_values,
    )

    # 9 categories * 1 perceptor each = 9.
    assert result.values["decl.total-percepciones"] == Decimal("9")
    # 100 + 200 + ... + 900 = 4500.
    assert result.values["decl.percepciones-total"] == Decimal("4500.00")
    # Copy of the single retenciones relation.
    assert result.values["decl.retenciones-total"] == Decimal("12000.00")


def test_modelo_193_copies_three_relations_into_three_output_casillas() -> None:
    """Each of 193's three output casillas is a 1-to-1 copy of the matching 123 relation."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "193")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="0A")

    relation_values = {
        "modelo-193-rel-123-perceptores-anual": Decimal("12"),
        "modelo-193-rel-123-base-anual": Decimal("7000.50"),
        "modelo-193-rel-123-retenciones-anual": Decimal("1330.10"),
    }
    date_context = {"filing_period": date(2026, 1, 31)}

    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context=date_context,
        relation_values=relation_values,
    )

    assert result.values["decl.total-perceptores"] == Decimal("12")
    assert result.values["decl.base-total"] == Decimal("7000.50")
    assert result.values["decl.retenciones-total"] == Decimal("1330.10")


def test_modelo_193_floors_relation_values_through_money_2_rounding() -> None:
    """A relation value with sub-cent precision rounds to two decimals via the formula's rounding."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "193")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="0A")

    relation_values = {
        "modelo-193-rel-123-perceptores-anual": Decimal("4"),
        "modelo-193-rel-123-base-anual": Decimal("1234.567"),  # sub-cent precision
        "modelo-193-rel-123-retenciones-anual": Decimal("234.564"),
    }
    date_context = {"filing_period": date(2026, 1, 31)}

    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context=date_context,
        relation_values=relation_values,
    )

    # Both money-2 formulas round their relation values to two decimals.
    assert result.values["decl.base-total"] == Decimal("1234.57")
    assert result.values["decl.retenciones-total"] == Decimal("234.56")
