"""A purchase booked the wrong way never deducts twice, and its value is weighed against the register."""

from __future__ import annotations

from decimal import Decimal

import pytest

from cadrumo.domain.renta.actividad_asset.lifecycle import (
    AcquisitionShape,
    ActivityAssetRevision,
    FurtherAcquisitionRow,
)

from ...actividad_asset.history import ActivityAssetHistory
from ..source_mesh import CalculationSourceResolution
from .test_modelo_source_mesh_ledger import (
    _machine_acquisition_transaction,
    _reasons,
    register_asset,
    resolve_m100,
    resolve_m130,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_UNREGISTERED = "ledger_amortization_row_unregistered"
_WITHHELD = "register_owned_capital_acquisition"
_EXCEEDS = "register_acquisition_exceeds_ledger"
_PARTLY = "register_acquisition_partly_accounted"
_OFFICE = "material_oficina"


def _history(*assets: ActivityAssetRevision) -> ActivityAssetHistory:
    return ActivityAssetHistory(revisions=assets)


def _expense_total(resolution: CalculationSourceResolution) -> Decimal:
    return sum(resolution.binding_values.values(), Decimal("0"))


def test_a_registered_purchase_booked_as_office_material_is_withheld_from_both_returns() -> None:
    row = _machine_acquisition_transaction(_OFFICE)
    history = _history(register_asset("monitor", transaction_id=row.transaction_id, basis=Decimal("1000.00")))

    for resolution in (resolve_m100(history, rows=(row,)), resolve_m130(history, "2T", rows=(row,))):
        assert _WITHHELD in _reasons(resolution)
        assert row.transaction_id not in resolution.source_transaction_ids
        assert _EXCEEDS not in _reasons(resolution)
        assert _PARTLY not in _reasons(resolution)


def test_the_same_row_with_no_element_deducts_as_the_expense_it_was_booked_as() -> None:
    row = _machine_acquisition_transaction(_OFFICE)

    assert _expense_total(resolve_m100(_history(), rows=(row,))) == Decimal("1000.00")


def test_a_capital_good_for_iva_booked_as_an_expense_deducts_nothing_and_is_named_once() -> None:
    row = _machine_acquisition_transaction(_OFFICE).model_copy(update={"deduction_fact_kind": "domestic_investment"})

    for resolution in (resolve_m100(_history(), rows=(row,)), resolve_m130(_history(), "2T", rows=(row,))):
        assert _reasons(resolution).count(_UNREGISTERED) == 1
        assert _expense_total(resolution) == Decimal("0")


def test_a_row_lowered_after_registration_is_found_on_both_returns() -> None:
    row = _machine_acquisition_transaction(
        _OFFICE, amount=Decimal("121.00"), taxable_base=Decimal("100.00"), iva_amount=Decimal("21.00")
    )
    history = _history(register_asset("monitor", transaction_id=row.transaction_id, basis=Decimal("1000.00")))

    for resolution in (resolve_m100(history, rows=(row,)), resolve_m130(history, "2T", rows=(row,))):
        assert _reasons(resolution).count(_EXCEEDS) == 1


def test_two_elements_that_each_fit_a_row_but_not_together_are_found_once() -> None:
    row = _machine_acquisition_transaction("hardware_amortizable")
    history = _history(
        register_asset("first", transaction_id=row.transaction_id, basis=Decimal("800.00")),
        register_asset("second", transaction_id=row.transaction_id, basis=Decimal("800.00")),
    )

    assert _reasons(resolve_m100(history, rows=(row,))).count(_EXCEEDS) == 1


def test_two_elements_that_share_a_row_exactly_raise_nothing() -> None:
    row = _machine_acquisition_transaction("hardware_amortizable")
    history = _history(
        register_asset("first", transaction_id=row.transaction_id, basis=Decimal("600.00")),
        register_asset("second", transaction_id=row.transaction_id, basis=Decimal("400.00")),
    )

    reasons = _reasons(resolve_m100(history, rows=(row,)))

    assert _EXCEEDS not in reasons
    assert _PARTLY not in reasons


def test_a_price_below_its_row_is_named_and_the_remainder_deducts_nothing() -> None:
    row = _machine_acquisition_transaction("hardware_amortizable")
    history = _history(register_asset("monitor", transaction_id=row.transaction_id, basis=Decimal("300.00")))

    resolution = resolve_m100(history, rows=(row,))

    assert _reasons(resolution).count(_PARTLY) == 1
    assert row.transaction_id not in resolution.source_transaction_ids


def test_a_further_row_counts_toward_its_element() -> None:
    first = _machine_acquisition_transaction("hardware_amortizable", provider_id="first-instalment")
    second = _machine_acquisition_transaction("hardware_amortizable", provider_id="second-instalment")
    asset = register_asset("press", transaction_id=first.transaction_id, basis=Decimal("2000.00"))
    further = asset.acquisition.model_copy(update={"observed_transaction_id": second.transaction_id})
    history = _history(
        asset.model_copy(
            update={
                "further_acquisitions": (FurtherAcquisitionRow(shape=AcquisitionShape.SPLIT_PAYMENT, lineage=further),)
            }
        )
    )

    reasons = _reasons(resolve_m100(history, rows=(first, second)))

    assert _EXCEEDS not in reasons
    assert _PARTLY not in reasons
