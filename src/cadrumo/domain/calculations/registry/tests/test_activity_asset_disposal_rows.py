"""A sale of an element states its own row on the columns the published revision declares."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

import pytest

from ..actividad_asset_disposal_bindings import (
    ActivityAssetDisposalRoute,
    ActivityAssetDisposalRowField,
    activity_asset_disposal_route_casillas,
    activity_asset_disposal_row_binding_ids,
    resolve_activity_asset_disposal_binding_values,
    resolve_activity_asset_disposal_row_values,
)
from ..authority import bundled_indexed_authority
from ..schema import ModeloRevision

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@dataclass(frozen=True)
class _Sale:
    source_identity: str
    columns: dict[ActivityAssetDisposalRowField, Decimal | str]

    def column(self, row_field: ActivityAssetDisposalRowField) -> Decimal | str | None:
        return self.columns.get(row_field)


@dataclass(frozen=True)
class _Figure:
    route: ActivityAssetDisposalRoute
    amount: Decimal


def _revision(revision_id: str) -> ModeloRevision:
    with bundled_indexed_authority().operation() as operation:
        return operation.revision("100", revision_id)


@pytest.mark.parametrize("revision_id", ["2022", "2023", "2024", "2025"])
def test_two_sales_fill_two_rows_each_with_its_own_gain(revision_id: str) -> None:
    revision = _revision(revision_id)
    sales = (
        _Sale("sale-a", {ActivityAssetDisposalRowField.GAIN: Decimal("100.00")}),
        _Sale("sale-b", {ActivityAssetDisposalRowField.GAIN: Decimal("250.00")}),
    )

    values, identities = resolve_activity_asset_disposal_row_values(revision, sales)

    gain = next(
        binding_id
        for binding_id in activity_asset_disposal_row_binding_ids(revision)
        if binding_id.endswith("-gain-1654")
    )
    clave = next(binding_id for binding_id in activity_asset_disposal_row_binding_ids(revision) if "type" in binding_id)
    assert values[(gain, 1)] == Decimal("100.00")
    assert values[(gain, 2)] == Decimal("250.00")
    assert identities[(gain, 2)] == "sale-b"
    assert values[(clave, 1)] == values[(clave, 2)] == "5"


def test_a_column_a_sale_has_no_value_for_stays_off_its_row() -> None:
    revision = _revision("2025")
    values, _identities = resolve_activity_asset_disposal_row_values(
        revision,
        (_Sale("sale-a", {ActivityAssetDisposalRowField.GAIN: Decimal("1.00")}),),
    )
    loss = next(binding_id for binding_id in activity_asset_disposal_row_binding_ids(revision) if "loss" in binding_id)
    assert (loss, 1) not in values


def test_the_columns_move_no_scalar_total() -> None:
    revision = _revision("2025")
    route_box = activity_asset_disposal_route_casillas(revision)
    assert ActivityAssetDisposalRoute.TRANSMISSION_GAIN_ELEMENT in route_box

    totals = resolve_activity_asset_disposal_binding_values(
        revision,
        (
            _Figure(ActivityAssetDisposalRoute.TRANSMISSION_GAIN_ELEMENT, Decimal("100.00")),
            _Figure(ActivityAssetDisposalRoute.TRANSMISSION_GAIN_ELEMENT, Decimal("250.00")),
        ),
    )

    row_ids = set(activity_asset_disposal_row_binding_ids(revision))
    assert row_ids
    assert not row_ids & set(totals)
    assert Decimal("350.00") in totals.values()
