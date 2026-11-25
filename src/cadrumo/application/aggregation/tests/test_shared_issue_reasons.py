"""Contract tests for the shared issue-reason strings.

The IVA and Renta ledger aggregators expose distinct
``StrEnum`` classes whose first five upstream-filter rejections must
emit identical string values so cross-ledger reporting, locale lookup,
and downstream consumers can key on a single vocabulary.
"""

from __future__ import annotations

from enum import StrEnum

import pytest

from ....domain.transactions.enums import BusinessClassification
from .. import shared_issue_reasons
from ..impatriado_income_ledger import ImpatriadoIncomeLedgerAggregationIssueReason
from ..iva_ledger import IvaLedgerAggregationIssueReason
from ..renta_gasto_ledger import RentaGastoLedgerAggregationIssueReason
from ..renta_income_models import RentaIncomeLedgerAggregationIssueReason
from ..renta_ledger_models import RentaLedgerAggregationIssueReason

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_both_ledgers_emit_same_string_for_shared_reason() -> None:
    names = (
        "UNSUPPORTED_DIRECTION",
        "UNSUPPORTED_CURRENCY",
        "UNCLASSIFIED_BUSINESS_STATE",
        "PERSONAL_TRANSACTION",
        "OUTSIDE_PERIOD",
    )

    for name in names:
        iva_value = IvaLedgerAggregationIssueReason[name].value
        renta_value = RentaLedgerAggregationIssueReason[name].value
        shared = getattr(shared_issue_reasons, name)
        assert iva_value == renta_value == shared, name


@pytest.mark.parametrize("classification", tuple(BusinessClassification))
@pytest.mark.parametrize(
    "lane",
    (
        IvaLedgerAggregationIssueReason,
        RentaLedgerAggregationIssueReason,
        RentaIncomeLedgerAggregationIssueReason,
        ImpatriadoIncomeLedgerAggregationIssueReason,
    ),
)
def test_every_classification_names_one_rejection_every_lane_can_carry(
    classification: BusinessClassification,
    lane: type[StrEnum],
) -> None:
    expected = (
        "personal_transaction" if classification is BusinessClassification.PERSONAL else "unclassified_business_state"
    )

    assert lane(shared_issue_reasons.business_state_issue_reason(classification)).value == expected


def test_iva_ledger_carries_its_domain_specific_reasons() -> None:
    iva_only = {
        IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE.value,
        IvaLedgerAggregationIssueReason.MISSING_IVA_AMOUNT.value,
        IvaLedgerAggregationIssueReason.MISSING_IVA_RATE.value,
        IvaLedgerAggregationIssueReason.UNSUPPORTED_IVA_RATE.value,
        IvaLedgerAggregationIssueReason.INVALID_PRORRATA_REFERENCE.value,
    }
    renta_values = {member.value for member in RentaLedgerAggregationIssueReason}
    assert iva_only.isdisjoint(renta_values)


def test_renta_ledger_carries_its_domain_specific_reasons() -> None:
    renta_only = {
        RentaLedgerAggregationIssueReason.UNSUPPORTED_PERIOD.value,
        RentaLedgerAggregationIssueReason.MISSING_CATEGORY.value,
        RentaLedgerAggregationIssueReason.UNKNOWN_CATEGORY.value,
        RentaLedgerAggregationIssueReason.MISSING_CATEGORY_PROFILE.value,
        RentaLedgerAggregationIssueReason.MISSING_PURCHASE_INVOICE_EVIDENCE.value,
        RentaLedgerAggregationIssueReason.INELIGIBLE_DEDUCTIBILITY.value,
    }
    iva_values = {member.value for member in IvaLedgerAggregationIssueReason}
    assert renta_only.isdisjoint(iva_values)


def test_annual_and_quarterly_expense_ledgers_spell_category_rule_refusals_alike() -> None:
    """A row refused by its category rule reads the same in M100 and M130 reporting."""
    names = (
        "UNKNOWN_CATEGORY",
        "MISSING_CATEGORY_PROFILE",
        "REGION_UNDECLARED_FOR_OVERRIDE",
        "INVALID_LEDGER_FACT",
        "INELIGIBLE_DEDUCTIBILITY",
    )

    for name in names:
        annual_value = RentaLedgerAggregationIssueReason[name].value
        quarterly_value = RentaGastoLedgerAggregationIssueReason[name].value
        shared = getattr(shared_issue_reasons, name)
        assert annual_value == quarterly_value == shared, name


def test_two_enums_remain_distinct_types() -> None:
    iva_member = IvaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION
    renta_member = RentaLedgerAggregationIssueReason.UNSUPPORTED_DIRECTION
    assert type(iva_member) is not type(renta_member)
    assert iva_member.value == renta_member.value
