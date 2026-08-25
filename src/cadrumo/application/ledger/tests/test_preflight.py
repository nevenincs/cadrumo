"""Tests for ledger modelo-readiness preflight."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from ....core.config import override_settings
from ....core.i18n import clear_output_language_cache
from ....domain.categories import SpendingCategory
from ....domain.iva import EUMemberState, IvaCategory
from ....domain.transactions import (
    BusinessClassification,
    TransactionCatalogue,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...aggregation import IvaLedgerAggregationIssueReason
from ..preflight import LedgerPreflightIssueReason, preflight_transaction_catalogue
from ..preflight import (
    _PREFLIGHT_DETAIL_BY_IVA_ISSUE,
    _PREFLIGHT_REASON_BY_IVA_ISSUE,
    _preflight_detail_for_iva_issue,
    _preflight_reason_for_iva_issue,
)
from ._preflight_test_support import (
    _AD_HOC_2026,
    _BUCKET_ID,
    _Q2_2026,
    _transaction,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_preflight_refuses_non_span_period_even_with_empty_catalogue() -> None:
    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_AD_HOC_2026,
        transactions=TransactionCatalogue.from_transactions(()),
    )

    assert report.ready is False
    assert report.checked_transaction_count == 0
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.UNSUPPORTED_PERIOD]
    assert "no date span" in report.issues[0].detail


def test_preflight_refuses_non_span_period_before_touching_transactions() -> None:
    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_AD_HOC_2026,
        transactions=TransactionCatalogue.from_transactions((_transaction("row-ready"),)),
    )

    assert report.ready is False
    assert report.checked_transaction_count == 0
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.UNSUPPORTED_PERIOD]


def test_preflight_reports_all_missing_modelo_readiness_facts() -> None:
    unclassified = _transaction(
        "row-unclassified",
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    missing_business_facts = _transaction(
        "row-missing-facts",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    mixed_missing_ratio = _transaction(
        "row-mixed",
        business_classification=BusinessClassification.MIXED,
        business_pct=Decimal("0.40"),
        category_id=SpendingCategory.TELEFONIA_MOVIL.value,
        usage_ratio_id=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions(
            (unclassified, missing_business_facts, mixed_missing_ratio),
        ),
    )

    assert report.ready is False
    assert report.checked_transaction_count == 3
    assert sorted(issue.reason for issue in report.issues) == sorted(
        (
            LedgerPreflightIssueReason.MISSING_BUSINESS_CLASSIFICATION,
            LedgerPreflightIssueReason.MISSING_CATEGORY,
            LedgerPreflightIssueReason.MISSING_TAXABLE_BASE,
            LedgerPreflightIssueReason.MISSING_IVA_AMOUNT,
            LedgerPreflightIssueReason.MISSING_IVA_RATE,
            LedgerPreflightIssueReason.MISSING_PROPORTIONALITY_REFERENCE,
        ),
    )


def test_preflight_ignores_personal_internal_transfer_and_out_of_period_rows() -> None:
    personal = _transaction(
        "row-personal",
        business_classification=BusinessClassification.PERSONAL,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    transfer = _transaction(
        "row-transfer",
        direction=TransactionDirection.INTERNAL_TRANSFER,
        business_classification=BusinessClassification.NOT_YET_PROCESSED,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )
    old = _transaction(
        "row-old",
        booked_date=date(2026, 1, 5),
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((personal, transfer, old)),
    )

    assert report.checked_transaction_count == 2
    assert report.issues == ()
    assert report.ready is True


def test_preflight_ignores_archived_and_stashed_rows() -> None:
    ready = _transaction("row-ready")
    archived_missing_facts = _transaction(
        "row-archived",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        lifecycle_state=TransactionLifecycleState.ARCHIVED,
    )
    stashed_missing_facts = _transaction(
        "row-stashed",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
        lifecycle_state=TransactionLifecycleState.STASHED,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((ready, archived_missing_facts, stashed_missing_facts)),
    )

    assert report.checked_transaction_count == 1
    assert report.issues == ()
    assert report.ready is True


def test_preflight_reports_unsupported_currency_before_modelo_aggregation() -> None:
    usd = _transaction("row-usd", currency="USD")

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((usd,)),
    )

    assert report.ready is False
    assert [issue.reason for issue in report.issues] == [LedgerPreflightIssueReason.UNSUPPORTED_CURRENCY]


def test_preflight_blocks_intracom_sale_with_domestic_counterparty_before_aggregation() -> None:
    transaction = _transaction(
        "row-intracom-es",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("1000.00"),
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_identification_state=EUMemberState.ES,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((transaction,)),
    )

    assert report.ready is False
    assert [issue.reason for issue in report.issues] == [
        LedgerPreflightIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
    ]
    assert not report.issues[0].detail.startswith("aggregation.")


def test_preflight_renders_intracom_domestic_identification_detail_in_hungarian() -> None:
    transaction = _transaction(
        "row-intracom-es-hu",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("1000.00"),
        taxable_base=Decimal("1000.00"),
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0"),
        iva_category=IvaCategory.INTRA_COMMUNITY_SUPPLY,
        counterparty_identification_state=EUMemberState.ES,
    )

    with override_settings(cadrumo_output_language="hu"):
        clear_output_language_cache()
        report = preflight_transaction_catalogue(
            bucket_id=_BUCKET_ID,
            period=_Q2_2026,
            transactions=TransactionCatalogue.from_transactions((transaction,)),
        )
    clear_output_language_cache()

    assert [issue.reason for issue in report.issues] == [
        LedgerPreflightIssueReason.DOMESTIC_IDENTIFICATION_ON_INTRA_COMMUNITY_TRANSACTION,
    ]
    # The narrowed concept, in the operator's own language: the refusal names the
    # IVA IDENTIFICATION, not where the counterparty is established.
    assert "héa-azonosító" in report.issues[0].detail
    assert not report.issues[0].detail.startswith("aggregation.")


def test_preflight_blocks_export_sale_with_eu_member_state_before_aggregation() -> None:
    transaction = _transaction(
        "row-export-de",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("800.00"),
        taxable_base=Decimal("800.00"),
        iva_rate=Decimal("0"),
        iva_amount=Decimal("0"),
        iva_category=IvaCategory.EXPORT_THIRD_COUNTRY_ZERO_RATED,
        counterparty_country="DE",
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((transaction,)),
    )

    assert report.ready is False
    assert [issue.reason for issue in report.issues] == [
        LedgerPreflightIssueReason.EU_MEMBER_STATE_ON_EXPORT_TRANSACTION,
    ]
    assert EUMemberState.DE.value in report.issues[0].detail


class TestEveryMappedIvaReasonResolves:
    """The reason mapping is a dict LITERAL, so every key evaluates on every call.

    That is the whole failure class and it is why this needs covering by
    exhaustion rather than by example. A single stale member name does not break
    the branch that names it -- it raises ``AttributeError`` while the literal is
    being built, so EVERY reason crashes, including ones with nothing to do with
    it. A missing taxable base took down the whole preflight surface once, and
    the outage read as an exotic intra-community bug because the only tests
    reaching this mapping went through the intra-community branch.
    """

    def test_every_mapped_reason_resolves_without_raising(self) -> None:
        """Exhaustive over the mapping's own keys, so a stale member cannot hide."""
        for reason in _PREFLIGHT_REASON_BY_IVA_ISSUE:
            resolved = _preflight_reason_for_iva_issue(reason)

            assert isinstance(resolved, LedgerPreflightIssueReason), reason

    def test_a_missing_taxable_base_resolves(self) -> None:
        """The non-intra-community case whose absence let a whole-surface outage hide."""
        resolved = _preflight_reason_for_iva_issue(IvaLedgerAggregationIssueReason.MISSING_TAXABLE_BASE)

        assert resolved is LedgerPreflightIssueReason.MISSING_TAXABLE_BASE

    def test_every_missing_fact_reason_has_a_detail_sentence(self) -> None:
        """The detail map is a second literal with the same exposure."""
        for reason in _PREFLIGHT_DETAIL_BY_IVA_ISSUE:
            detail = _preflight_detail_for_iva_issue(reason)

            assert detail and not detail.startswith("aggregation."), reason
