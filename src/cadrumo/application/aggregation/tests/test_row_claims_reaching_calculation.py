"""What a row that carries no taxable operation can and cannot prove to the real aggregation.

Worked by hand: a 100.00 purchase at 21% has a 21.00 cuota, of which a row wholly
for the activity deducts 21.00 and one used half for it 10.50 where its category
allows a share at all. An internal transfer is no supply (LIVA art. 4), so nothing
it says can support a deduction (LIVA art. 92).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....core.period import Period
from ....domain.bienes_inversion.register import (
    BienesInversionIvaRegister,
    BienInversionIvaRecord,
    BienInversionValidationError,
)
from ....domain.bienes_inversion.vocabulary import BienInversionKind
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ....domain.calculations.registry.tests.authored_editions import filing_year_envelope
from ....domain.transactions.classification_effects import fields_refused_by_classification
from ....domain.transactions.enums import BusinessClassification, TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ...ledger.preflight import HeldTransactionCatalogue, LedgerPreflightIssueReason, preflight_transaction_catalogue
from ..iva_ledger import IvaLedgerAggregation, IvaLedgerAggregationIssueReason, aggregate_iva_ledger_observations
from .ledger_transaction_support import iva_transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_YEAR = filing_year_envelope().horizon
_Q1 = Period.from_year_and_code(_YEAR, "1T")
_Q2 = Period.from_year_and_code(_YEAR, "2T")


def _register(row: Transaction) -> BienesInversionIvaRegister:
    return BienesInversionIvaRegister(
        records=(
            BienInversionIvaRecord(
                identifier="asset-1",
                description="Synthetic asset",
                acquisition_year=_YEAR,
                cuota_soportada=Decimal("210.00"),
                prorrata_inicial_pct=Decimal("100"),
                kind=BienInversionKind.from_registry("mueble"),
                acquisition_ledger_id=row.transaction_id,
            ),
        )
    )


def _purchase(**updates: object) -> Transaction:
    row = iva_transaction(
        "claim-row",
        direction=TransactionDirection.OUTGOING,
        amount=Decimal("121.00"),
        taxable_base=Decimal("100.00"),
        iva_amount=Decimal("21.00"),
    )
    return row.model_copy(update=updates)


def _aggregate(
    row: Transaction,
    period: Period,
    operation: PinnedAuthorityOperation,
    register: BienesInversionIvaRegister | None = None,
) -> IvaLedgerAggregation:
    return aggregate_iva_ledger_observations(
        TransactionCatalogue.from_transactions((row,)),
        period=period,
        ledger_profile_id="claims",
        investment_asset_register=register or BienesInversionIvaRegister(),
        investment_asset_profile_id="claims",
        operation=operation,
    )


def _investment_claim(row: Transaction) -> Transaction:
    return row.model_copy(
        update={
            "deduction_fact_kind": IvaDeductionFactKind.from_registry("domestic_investment"),
            "investment_asset_id": "asset-1",
        }
    )


@pytest.mark.parametrize(
    "updates",
    [
        {
            "direction": TransactionDirection.INTERNAL_TRANSFER,
            "business_classification": BusinessClassification.PERSONAL,
            **dict.fromkeys(fields_refused_by_classification(BusinessClassification.PERSONAL)),
        },
        {
            "business_classification": BusinessClassification.PERSONAL,
            **dict.fromkeys(fields_refused_by_classification(BusinessClassification.PERSONAL)),
        },
    ],
)
def test_a_row_with_no_operation_does_not_prove_an_asset_from_another_period(
    updates: dict[str, object], *, operation: PinnedAuthorityOperation
) -> None:
    claim = _investment_claim(_purchase(**updates))
    with pytest.raises(BienInversionValidationError):
        _aggregate(claim, _Q2, operation, _register(claim))


def test_a_business_acquisition_still_proves_its_asset_in_the_other_periods(
    *, operation: PinnedAuthorityOperation
) -> None:
    claim = _investment_claim(_purchase())
    result = _aggregate(claim, _Q2, operation, _register(claim))
    assert result.observations == ()


@pytest.mark.parametrize(
    ("updates", "expected_blocking"),
    [
        (
            {
                "category_id": None,
                "business_classification": BusinessClassification.MIXED,
                "business_pct": Decimal("0.5"),
            },
            LedgerPreflightIssueReason.MISSING_CATEGORY,
        ),
        ({"category_id": None}, LedgerPreflightIssueReason.MISSING_CATEGORY),
    ],
)
def test_an_uncategorized_split_part_is_held_before_any_calculation_reads_its_cuota(
    updates: dict[str, object],
    expected_blocking: LedgerPreflightIssueReason,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    report = preflight_transaction_catalogue(
        invoices=(),
        movement_reader=HeldTransactionCatalogue(TransactionCatalogue.from_transactions(())),
        cash_accounting_enrolled=False,
        bucket_id="claims",
        period=_Q1,
        transactions=TransactionCatalogue.from_transactions((_purchase(**updates),)),
        operation=operation,
    )
    assert expected_blocking in {issue.reason for issue in report.issues}
    assert report.ready is False


def test_the_aggregation_alone_refuses_the_share_of_an_uncategorized_mixed_row(
    *, operation: PinnedAuthorityOperation
) -> None:
    row = _purchase(category_id=None, business_classification=BusinessClassification.MIXED, business_pct=Decimal("0.5"))
    result = _aggregate(row, _Q1, operation)
    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [
        IvaLedgerAggregationIssueReason.UNDETERMINED_MIXED_USE_TREATMENT
    ]


def test_a_mixed_row_in_a_category_with_no_share_reports_instead_of_deducting(
    *, operation: PinnedAuthorityOperation
) -> None:
    row = _purchase(business_classification=BusinessClassification.MIXED, business_pct=Decimal("0.5"))
    result = _aggregate(row, _Q1, operation)
    assert result.observations == ()
    assert [issue.reason for issue in result.issues] == [IvaLedgerAggregationIssueReason.NON_DEDUCTIBLE_MIXED_USE]
