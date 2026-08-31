"""Bidirectional M100/2025 inventory row-template-to-casilla linkage."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from ..authority import bundled_authority
from ..binding_targets import bound_casilla_binding_ids, casillas_by_binding
from ..bindings import resolve_bound_casilla_binding_value
from ..inventory_bindings import InventorySelector
from ..schema_input_kind import InputKind

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_LINKS = {
    "renta-2025-inventory-activity-closing-increase-0177": "0177",
    "renta-2025-inventory-activity-acquisition-cost-0181": "0181",
    "renta-2025-inventory-activity-closing-decrease-0182": "0182",
}


def test_inventory_row_templates_link_bidirectionally_to_exact_casillas() -> None:
    revision = bundled_authority().snapshot("100", filing_year=2025, period="0A").revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    reverse = casillas_by_binding(revision)

    for binding_id, casilla_id in _LINKS.items():
        binding = bindings[binding_id]
        casilla = casillas[casilla_id]

        assert binding.source is BindingSourceKind.INVENTORY
        assert binding.aggregation is not None
        assert binding.aggregation.op is BindingAggregationOp.ROWS
        assert isinstance(binding.selector, InventorySelector)
        assert binding.selector.target_casilla_id == casilla_id
        assert casilla.input_kind is InputKind.BOUND
        assert bound_casilla_binding_ids(casilla) == (binding_id,)
        assert reverse[binding_id] == (casilla_id,)


def test_inventory_bindings_have_one_claim_and_no_cross_or_legacy_link() -> None:
    revision = bundled_authority().snapshot("100", filing_year=2025, period="0A").revision
    claims = {
        binding_id: tuple(
            casilla.id for casilla in revision.casillas if binding_id in bound_casilla_binding_ids(casilla)
        )
        for binding_id in _LINKS
    }

    assert claims == {binding_id: (casilla_id,) for binding_id, casilla_id in _LINKS.items()}
    legacy = next(casilla for casilla in revision.casillas if casilla.id == "0155")
    assert not set(bound_casilla_binding_ids(legacy)).intersection(_LINKS)


def test_rows_linkage_does_not_fold_row_values_into_scalar_formula_inputs() -> None:
    revision = bundled_authority().snapshot("100", filing_year=2025, period="0A").revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}

    for binding_id, casilla_id in _LINKS.items():
        value, used = resolve_bound_casilla_binding_value(casillas[casilla_id], {})
        assert value is None
        assert used == ()

        # Row values live in CalculationRevision.row_binding_values. The scalar
        # resolver accepts only BindingId -> Decimal and cannot consume a row map.
        value, used = resolve_bound_casilla_binding_value(
            casillas[casilla_id],
            {"unrelated-scalar-binding": Decimal("999.99")},
        )
        assert value is None
        assert used == ()
        assert binding_id not in used


def test_inventory_casilla_links_are_absent_from_other_m100_revisions() -> None:
    revision = bundled_authority().snapshot("100", filing_year=2024, period="0A").revision
    linked = {binding_id for casilla in revision.casillas for binding_id in bound_casilla_binding_ids(casilla)}

    assert not linked.intersection(_LINKS)
