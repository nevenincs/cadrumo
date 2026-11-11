"""LIVA art. 95.Tres.2.ª through the real IVA aggregator.

Every figure is worked by hand from a 100.00 base and a 21.00 cuota:

- no stated use: the general presumption, 21.00 x 0.50 = 10.50, whatever share or
  classification the row states, because a stated figure is not the proof
  regla 4.ª asks for and regla 3.ª regularizes a proven degree afterwards;
- one of the six listed uses: 21.00 x 1.00 = 21.00, whatever the row states;
- a vehicle outside regla 2.ª: regla 1.ª at the row's own degree of use, so
  21.00 x 0.30 = 6.30 for a 30 per cent MIXED row and 21.00 for a BUSINESS one.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.period import Period
from ....domain.bienes_inversion.register import BienesInversionIvaRegister
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.iva.errors import IvaValidationError
from ....domain.iva.vehicle_use import IvaVehicleUse, require_iva_vehicle_use
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..iva_ledger import IvaLedgerAggregationIssueReason, aggregate_iva_ledger_observations
from .ledger_transaction_support import iva_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application, pytest.mark.usefixtures("operation")]

_YEAR = filing_year_envelope().horizon
_QUARTER = Period.from_year_and_code(_YEAR, "1T")
_MIXED = BusinessClassification.MIXED
_BUSINESS = BusinessClassification.BUSINESS
_LISTED_USES = tuple(use for use in IvaVehicleUse if use is not IvaVehicleUse.OUTSIDE_PRESUMED_CLASSES)


def _row(
    category: str,
    *,
    use: IvaVehicleUse | None = None,
    classification: BusinessClassification = _MIXED,
    share: Decimal = Decimal("0.30"),
) -> Transaction:
    return iva_transaction(
        "vehicle-use",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
        booked_date=date(_YEAR, 2, 10),
    ).model_copy(
        update={
            "business_classification": classification,
            "business_pct": share if classification is _MIXED else None,
            "category_id": category,
            "iva_vehicle_use": use,
        }
    )


def _iva(row: Transaction, operation: PinnedAuthorityOperation) -> list[object]:
    result = aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((row,)),
        period=_QUARTER,
        ledger_profile_id="vehicle-use",
        investment_asset_register=BienesInversionIvaRegister(),
        investment_asset_profile_id="vehicle-use",
        operation=operation,
    )
    return [*(o.iva_amount for o in result.observations), *(i.reason for i in result.issues)]


@pytest.mark.parametrize("category", ["vehiculo_combustible", "vehiculo_mantenimiento", "vehiculo_peaje"])
@pytest.mark.parametrize(
    ("classification", "share"),
    [(_MIXED, Decimal("0.30")), (_MIXED, Decimal("0.80")), (_BUSINESS, Decimal("0"))],
    ids=["below-the-presumption", "above-the-presumption", "wholly-business"],
)
def test_no_stated_use_takes_the_general_presumption_over_any_stated_share(
    category: str, classification: BusinessClassification, share: Decimal, *, operation: PinnedAuthorityOperation
) -> None:
    assert _iva(_row(category, classification=classification, share=share), operation) == [Decimal("10.50")]


@pytest.mark.parametrize("use", _LISTED_USES)
@pytest.mark.parametrize("classification", [_MIXED, _BUSINESS])
def test_a_listed_use_is_presumed_whole_over_any_stated_share(
    use: IvaVehicleUse, classification: BusinessClassification, *, operation: PinnedAuthorityOperation
) -> None:
    assert _iva(_row("vehiculo_combustible", use=use, classification=classification), operation) == [Decimal("21.00")]


@pytest.mark.parametrize(
    ("classification", "expected"),
    [(_MIXED, Decimal("6.30")), (_BUSINESS, Decimal("21.00"))],
)
def test_a_vehicle_outside_the_presumption_deducts_its_degree_of_use(
    classification: BusinessClassification, expected: Decimal, *, operation: PinnedAuthorityOperation
) -> None:
    row = _row("vehiculo_combustible", use=IvaVehicleUse.OUTSIDE_PRESUMED_CLASSES, classification=classification)
    assert _iva(row, operation) == [expected]


@pytest.mark.parametrize("category", ["vehiculo_seguro", "asesoria_fiscal"])
def test_a_stated_use_grants_nothing_outside_art_95_tres_and_cuatro(
    category: str, *, operation: PinnedAuthorityOperation
) -> None:
    row = _row(category, use=IvaVehicleUse.PAID_PASSENGER_TRANSPORT)
    assert _iva(row, operation) == [IvaLedgerAggregationIssueReason.NON_DEDUCTIBLE_MIXED_USE]


def test_a_stated_use_outside_the_law_is_refused() -> None:
    assert require_iva_vehicle_use("surveillance") is IvaVehicleUse.SURVEILLANCE
    with pytest.raises(IvaValidationError):
        require_iva_vehicle_use("habitual_onerous_hire")
