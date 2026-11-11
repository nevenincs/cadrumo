"""Bidirectional M100 inventory row-template-to-casilla linkage, in every supported edition."""

from __future__ import annotations

from decimal import Decimal

import pytest

from .....core.aggregation import BindingAggregationOp, BindingSourceKind
from ..binding_targets import bound_casilla_binding_ids, casillas_by_binding
from ..bindings import resolve_bound_casilla_binding_value
from ..inventory_bindings import InventoryProvider
from ..schema_input_kind import InputKind
from .authored_editions import newest_authored_edition
from .published_authority import PublishedGovernedFactSource, published_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVIEWED_EDITION = newest_authored_edition("100")

_LINKS = {
    "renta-inventory-activity-closing-increase-0177": "0177",
    "renta-inventory-activity-acquisition-cost-0181": "0181",
    "renta-inventory-activity-closing-decrease-0182": "0182",
}


def test_inventory_row_templates_link_bidirectionally_to_exact_casillas() -> None:
    revision = published_snapshot("100", filing_year=_REVIEWED_EDITION, period="0A").revision
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    bindings = {binding.id: binding for binding in revision.bindings}
    reverse = casillas_by_binding(revision)

    for binding_id, casilla_id in _LINKS.items():
        binding = bindings[binding_id]
        casilla = casillas[casilla_id]

        assert binding.source is BindingSourceKind.INVENTORY
        assert binding.aggregation is not None
        assert binding.aggregation.op is BindingAggregationOp.ROWS
        assert isinstance(binding.provider, InventoryProvider)
        assert binding.provider.target_casilla_id == casilla_id
        assert casilla.input_kind is InputKind.BOUND
        assert bound_casilla_binding_ids(casilla) == (binding_id,)
        assert reverse[binding_id] == (casilla_id,)


def test_inventory_bindings_have_one_claim_and_no_cross_or_legacy_link() -> None:
    revision = published_snapshot("100", filing_year=_REVIEWED_EDITION, period="0A").revision
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
    revision = published_snapshot("100", filing_year=_REVIEWED_EDITION, period="0A").revision
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


@pytest.mark.parametrize("filing_year", PublishedGovernedFactSource().supported_filing_years().years)
def test_inventory_casillas_are_linked_in_every_supported_m100_revision(filing_year: int) -> None:
    revision = published_snapshot("100", filing_year=filing_year, period="0A").revision
    reverse = casillas_by_binding(revision)

    assert {binding_id: reverse.get(binding_id) for binding_id in _LINKS} == {
        binding_id: (casilla_id,) for binding_id, casilla_id in _LINKS.items()
    }
