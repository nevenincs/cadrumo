"""Every amount on the activity-asset screen is read by one hand-typed euro grammar."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Final

import pytest

from .....core.config import override_settings
from .....core.i18n.render import tr
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ..actividad_asset_inputs import InputRefusedError, stated_disposal, stated_revision
from .actividad_asset_fixtures import activity_asset_revision

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DISPOSAL_ON = date(filing_year_envelope().horizon, 6, 30)

_REVISION_FIELDS: Final = ("asset-price", "asset-non-deductible-iva")
_DISPOSAL_FIELDS: Final = ("asset-disposal-proceeds", "asset-disposal-costs", "asset-disposal-market-value")


def _disposal_reader(field: str, text: str) -> Callable[[str], str]:
    values = {
        "asset-disposal-date": _DISPOSAL_ON.isoformat(),
        "asset-disposal-reason": "sale",
        "asset-disposal-proceeds": "10.00",
        "asset-disposal-costs": "10.00",
        field: text,
    }
    return lambda input_id: values.get(input_id, "")


def _read_amount(field: str, text: str) -> Decimal | None:
    """Submit ``text`` in one field of the screen and return the amount the request carries for it."""
    if field in _REVISION_FIELDS:
        revision = stated_revision(
            lambda input_id: text if input_id == field else "",
            activity_asset_revision("tui-amount-grammar").model_dump_json(),
        )
        return revision.basis.basis_amount if field == "asset-price" else revision.basis.non_deductible_iva
    disposal = stated_disposal(_disposal_reader(field, text)).to_domain()
    return {
        "asset-disposal-proceeds": disposal.proceeds,
        "asset-disposal-costs": disposal.transmission_costs,
        "asset-disposal-market-value": disposal.market_value,
    }[field]


@pytest.mark.parametrize("field", (*_REVISION_FIELDS, *_DISPOSAL_FIELDS))
@pytest.mark.parametrize("text", ("1.000", "1e3"))
def test_an_ambiguous_or_scientific_amount_is_refused_on_every_field(field: str, text: str) -> None:
    """``1.000`` reads as one euro or one thousand, and ``1e3`` is no hand-typed amount."""
    with override_settings(cadrumo_output_language="en"):
        with pytest.raises(InputRefusedError) as refused:
            _read_amount(field, text)
        wanted = tr("tui.ledger.activity_asset.errors.amount_invalid")

    assert str(refused.value) == wanted


@pytest.mark.parametrize("field", (*_REVISION_FIELDS, *_DISPOSAL_FIELDS))
def test_a_canonical_amount_is_read_alike_on_every_field(field: str) -> None:
    assert _read_amount(field, "1500.00") == Decimal("1500.00")
