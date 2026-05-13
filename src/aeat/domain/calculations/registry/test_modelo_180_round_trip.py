"""Tier 1 round-trip test for modelo 180 (rental withholdings annual receiver).

Modelo 180 is the annual summary of 115 rental withholdings. Like 193,
it is a pure receiver: three output casillas, each a copy-from-relation
formula. The schema declares the same three-formula shape across both
revisions (2019-2022 and 2023-y-siguientes).

The Tier 1 contract for receivers (per the chain-tier-passage ADR):
given concrete relation values, produce concrete output casilla
values.
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


def test_modelo_180_copies_three_relations_into_three_output_casillas() -> None:
    """Each of 180's three output casillas is a 1-to-1 copy of the matching 115 relation."""

    modelos, catalogues = load_registry_tree(_REGISTRY_ROOT)
    modelo = next(m for m in modelos if m.id == "180")
    snapshot = build_snapshot(modelo, catalogues, source_root=PROJECT_ROOT, filing_year=2026, period="0A")

    relation_values = {
        "modelo-180-rel-115-perceptores-anual": Decimal("5"),
        "modelo-180-rel-115-base-anual": Decimal("2149.75"),
        "modelo-180-rel-115-retenciones-anual": Decimal("418.00"),
    }
    date_context = {"filing_period": date(2026, 1, 31)}

    result = calculate_registry_snapshot(
        snapshot,
        inputs={},
        date_context=date_context,
        relation_values=relation_values,
    )

    assert result.values["decl.total-perceptores"] == Decimal("5")
    assert result.values["decl.base-total"] == Decimal("2149.75")
    assert result.values["decl.retenciones-total"] == Decimal("418.00")
