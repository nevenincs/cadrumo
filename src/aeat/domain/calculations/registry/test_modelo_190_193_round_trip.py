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
