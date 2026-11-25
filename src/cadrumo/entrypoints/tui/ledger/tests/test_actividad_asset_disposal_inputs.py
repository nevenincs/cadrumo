"""A baja's amounts are stated in the TUI: blank is refused, and only a written 0.00 is zero."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal

import pytest

from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from .....domain.renta.actividad_asset.disposal import (
    ADMITTED_DISPOSAL_REASONS,
    ActivityAssetDisposalFacts,
    ActivityAssetDisposalReason,
    calculate_disposal,
)
from ..actividad_asset_inputs import InputRefusedError, stated_disposal

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DISPOSAL_ON = date(filing_year_envelope().horizon, 6, 30)


def _reader(**amounts: str) -> Callable[[str], str]:
    values = {
        "asset-disposal-date": _DISPOSAL_ON.isoformat(),
        "asset-disposal-reason": amounts.pop("reason", "sale"),
        "asset-disposal-proceeds": amounts.pop("proceeds"),
        "asset-disposal-costs": amounts.pop("costs"),
    }
    return lambda input_id: values.get(input_id, "")


@pytest.mark.parametrize(
    ("proceeds", "costs", "label_key"),
    (
        ("", "10.00", "tui.ledger.activity_asset.disposal_proceeds"),
        ("10.00", "", "tui.ledger.activity_asset.disposal_costs"),
        ("", "", "tui.ledger.activity_asset.disposal_proceeds"),
    ),
)
def test_a_blank_amount_is_refused_naming_its_field(proceeds: str, costs: str, label_key: str) -> None:
    with override_settings(cadrumo_output_language="en"):
        with pytest.raises(InputRefusedError) as refused:
            stated_disposal(_reader(proceeds=proceeds, costs=costs))
        wanted = tr("tui.ledger.activity_asset.errors.amount_required", field=tr(label_key))

    assert str(refused.value) == wanted


@pytest.mark.parametrize("reason", ADMITTED_DISPOSAL_REASONS)
def test_a_written_zero_is_accepted_for_every_admitted_reason(reason: ActivityAssetDisposalReason) -> None:
    disposal = stated_disposal(_reader(reason=reason.value, proceeds="0.00", costs="0.00")).to_domain()

    assert disposal.reason is reason
    assert disposal.proceeds == Decimal("0")
    assert disposal.transmission_costs == Decimal("0")


def test_a_stated_sale_reaches_the_worked_gain() -> None:
    disposal = stated_disposal(_reader(proceeds="7500.25", costs="300.10")).to_domain()
    assert disposal.disposal_date == _DISPOSAL_ON

    calculation = calculate_disposal(
        ActivityAssetDisposalFacts(
            disposal=disposal,
            acquisition_value=Decimal("10000.00"),
            allocation_share=Decimal("1"),
            amortizable_value=Decimal("10000.00"),
            opening_amount=Decimal("4000.00"),
            years=(),
        )
    )

    # Worked by hand: net value 10000.00 - 4000.00 = 6000.00; gain 7500.25 - 300.10 - 6000.00 = 1200.15.
    assert calculation.net_value == Decimal("6000.00")
    assert calculation.result == Decimal("1200.15")
