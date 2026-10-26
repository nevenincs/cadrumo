"""Ledger readiness reports an inadmissible input-IVA deduction classification.

A declared deduction kind that the IVA deduction applicability catalogue does not
pair with the row's category, flow or evidence authority makes the row
unprojectable. Reporting it here is what turns it into an operator-facing
readiness gap with a transaction id and a remedy, and what makes a Modelo
303/390 calculation refuse instead of failing on an internal payload boundary.

The screen reads the real classification pipeline rather than re-deriving the
row's category, tier and flow, so a readiness verdict cannot disagree with what
calculation will do. The last test is that parity: a row an earlier gate excludes
must produce no deduction finding, because calculation never reaches the
observation for it either.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation

from ....core.period import Period
from ....domain.iva.schema import IvaCategory, IvaExemptionArticle
from ....domain.transactions.enums import TransactionDirection
from ....domain.transactions.models import Transaction, TransactionCatalogue
from ..preflight import LedgerPreflightIssueReason, preflight_transaction_catalogue
from ._preflight_test_support import _BUCKET_ID, _Q2_2026, _transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INVOICE_PROVENANCE: dict[str, object] = {
    "authority": "invoice_evidence",
    "source_locator": "invoice:REC-2026-1",
    "evidence_digest": "a" * 64,
}


def _classified_purchase(provider_id: str, **updates: object) -> Transaction:
    """An invoice-backed domestic purchase carrying an explicit deduction kind."""
    taxable_base = updates.pop("taxable_base", Decimal("100.00"))
    iva_amount = updates.pop("iva_amount", Decimal("21.00"))
    booked_date = updates.pop("booked_date", date(2026, 4, 5))
    assert isinstance(taxable_base, Decimal)
    assert isinstance(iva_amount, Decimal)
    assert isinstance(booked_date, date)
    purchase = _transaction(
        provider_id,
        direction=TransactionDirection.OUTGOING,
        amount=taxable_base + iva_amount,
        taxable_base=taxable_base,
        iva_amount=iva_amount,
        iva_category=IvaCategory("domestic_general"),
        booked_date=booked_date,
    )
    return Transaction.model_validate(
        purchase.model_dump()
        | {
            "deduction_fact_kind": "domestic_current",
            "deduction_provenance": _INVOICE_PROVENANCE,
        }
        | updates,
    )


def _reasons(
    *transactions: Transaction,
    period: Period = _Q2_2026,
    operation: PinnedAuthorityOperation,
) -> list[LedgerPreflightIssueReason]:
    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=period,
        transactions=TransactionCatalogue.from_transactions(transactions),
        operation=operation,
    )
    return [issue.reason for issue in report.issues]


def test_readiness_passes_an_admissible_deduction_classification(*, operation: PinnedAuthorityOperation) -> None:
    assert _reasons(_classified_purchase("admissible"), operation=operation) == []


def test_readiness_reports_an_exempt_purchase_declared_as_an_ordinary_deduction(
    *, operation: PinnedAuthorityOperation
) -> None:
    exempt = _classified_purchase(
        "exempt-purchase",
        iva_amount=Decimal("0.00"),
        iva_rate=Decimal("0"),
        iva_category=IvaCategory("domestic_exempt"),
        exemption_article=IvaExemptionArticle("art_20_other"),
    )

    assert _reasons(exempt, operation=operation) == [
        LedgerPreflightIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]


def test_readiness_reports_an_investment_deduction_without_its_asset_identity(
    *, operation: PinnedAuthorityOperation
) -> None:
    investment = _classified_purchase(
        "investment-purchase",
        taxable_base=Decimal("3600.00"),
        iva_amount=Decimal("756.00"),
        deduction_fact_kind="domestic_investment",
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((investment,)),
        operation=operation,
    )

    assert [issue.reason for issue in report.issues] == [
        LedgerPreflightIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION,
    ]
    assert report.ready is False
    assert "investment_asset_id" in report.issues[0].detail
    assert report.issues[0].transaction_id == investment.transaction_id


def test_readiness_stays_silent_for_a_row_carrying_no_deduction_facts(*, operation: PinnedAuthorityOperation) -> None:
    """An absent classification is the ledger write's business, not this screen's.

    The row cannot be inadmissible on this axis at all, and reporting an absence
    here would block every 303 period whose purchases are not yet invoice-linked
    -- a state the aggregation already reports as its own distinct exclusion.
    """
    unclassified = _transaction(
        "unclassified-purchase",
        direction=TransactionDirection.OUTGOING,
        iva_category=IvaCategory("domestic_general"),
    )

    assert _reasons(unclassified, operation=operation) == []


def test_readiness_does_not_report_a_row_an_earlier_gate_already_excludes(
    *, operation: PinnedAuthorityOperation
) -> None:
    """The parity contract: a row calculation never projects yields no deduction finding.

    The row below declares an inadmissible deduction AND a non-EUR movement with
    no EUR substrate. The currency screen owns it, and the classification
    pipeline stops on the same fact, so the deduction verdict is never reached.
    Reported anyway, this would attach a second finding to a row whose first
    finding is the one to act on.
    """
    foreign = _classified_purchase(
        "foreign-exempt-purchase",
        iva_amount=Decimal("0.00"),
        iva_rate=Decimal("0"),
        iva_category=IvaCategory("domestic_exempt"),
        exemption_article=IvaExemptionArticle("art_20_other"),
    )
    foreign = Transaction.model_validate(
        foreign.model_dump()
        | {
            "raw": foreign.raw.model_dump() | {"currency": "GBP"},
            "value_in_eur": Decimal("118.00"),
            "fx_rate": Decimal("1.18"),
        },
    )

    assert _reasons(foreign, operation=operation) == [LedgerPreflightIssueReason.MISSING_EUR_TAX_SUBSTRATE]


def test_readiness_ignores_a_row_outside_the_checked_period(*, operation: PinnedAuthorityOperation) -> None:
    """Period scope is the readiness window, and the screen does not widen it."""
    exempt = _classified_purchase(
        "exempt-purchase-q1",
        iva_amount=Decimal("0.00"),
        iva_rate=Decimal("0"),
        iva_category=IvaCategory("domestic_exempt"),
        exemption_article=IvaExemptionArticle("art_20_other"),
        booked_date=date(2026, 2, 10),
    )

    assert _reasons(exempt, operation=operation) == []
