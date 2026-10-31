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
from ..binding_targets import BindingConsumerKind, binding_consumers
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


@pytest.mark.parametrize("revision_id", ["2022", "2023", "2024", "2025"])
def test_application_row_consumers_match_the_disposal_columns_actually_resolved(revision_id: str) -> None:
    revision = _revision(revision_id)
    sales = (
        _Sale("sale-a", {field: Decimal("10") for field in ActivityAssetDisposalRowField}),
        _Sale("sale-b", {field: Decimal("20") for field in ActivityAssetDisposalRowField}),
    )
    values, identities = resolve_activity_asset_disposal_row_values(revision, sales)
    emitted = {binding_id for binding_id, _index in values}
    assert len(emitted) == 10
    consumers = binding_consumers(revision)
    application_rows = {
        binding_id
        for binding_id, refs in consumers.items()
        if any(ref.kind is BindingConsumerKind.APPLICATION_ROW_VALUE for ref in refs)
    }
    # Compare against real resolver output, not merely row declarations or names.
    assert application_rows == emitted
    assert set(values) == set(identities) == {(binding_id, row) for binding_id in emitted for row in (1, 2)}
    assert {identities[(binding_id, 2)] for binding_id in emitted} == {"sale-b"}


def test_a_disposal_column_without_a_field_earns_no_application_consumer() -> None:
    revision = _revision("2025")
    column_id = activity_asset_disposal_row_binding_ids(revision)[0]
    column = next(binding for binding in revision.bindings if binding.id == column_id)
    malformed = column.model_copy(update={"provider": column.provider.model_copy(update={"row_field": None})})
    changed = revision.model_copy(
        update={"bindings": tuple(malformed if binding.id == column_id else binding for binding in revision.bindings)}
    )
    values, _identities = resolve_activity_asset_disposal_row_values(
        changed, (_Sale("sale-a", {field: Decimal("10") for field in ActivityAssetDisposalRowField}),)
    )
    assert not any(binding_id == column_id for binding_id, _index in values)
    assert not any(
        ref.kind is BindingConsumerKind.APPLICATION_ROW_VALUE for ref in binding_consumers(changed)[column_id]
    )
