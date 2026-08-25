"""Income IVA fact checks for ledger modelo preflight."""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.transactions import (
    TransactionCatalogue,
    TransactionDirection,
    has_employment_irpf_category,
)
from ..preflight import LedgerPreflightIssueReason, preflight_transaction_catalogue
from ._preflight_test_support import _BUCKET_ID, _Q2_2026, _transaction

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_preflight_skips_iva_facts_on_trabajo_income_rows() -> None:
    """Nómina income is IVA-exempt and should not surface missing IVA facts."""
    nomina = _transaction(
        "row-nomina",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("1850.00"),
        irpf_category="trabajo",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((nomina,)),
    )

    assert report.ready is True, [issue.reason for issue in report.issues]
    assert report.issues == ()


def test_preflight_still_flags_iva_facts_on_non_trabajo_income_rows() -> None:
    """The trabajo guard must not silence general income rows."""
    income_no_irpf = _transaction(
        "row-income-no-irpf",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("500.00"),
        irpf_category=None,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((income_no_irpf,)),
    )

    assert report.ready is False
    surfaced = {issue.reason for issue in report.issues}
    assert LedgerPreflightIssueReason.MISSING_TAXABLE_BASE in surfaced
    assert LedgerPreflightIssueReason.MISSING_IVA_AMOUNT in surfaced
    assert LedgerPreflightIssueReason.MISSING_IVA_RATE in surfaced


@pytest.mark.parametrize(
    "spelling",
    ["trabajo", "TRABAJO", "Trabajo", "  trabajo  "],
    ids=["canonical", "upper", "mixed", "padded"],
)
def test_preflight_reads_the_same_normalized_trabajo_token_as_the_domain(spelling: str) -> None:
    """Every spelling the domain catalogue accepts also skips the IVA-fact checks.

    The preflight used to strip and lowercase the raw token while the gross
    invariant matched the catalogue exactly, so ``TRABAJO`` was employment
    income here and an unknown category there. Both now resolve through the
    one catalogue helper, so this parity holds by construction.
    """
    nomina = _transaction(
        "row-nomina",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("1850.00"),
        irpf_category=spelling,
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((nomina,)),
    )

    assert has_employment_irpf_category(spelling, direction=TransactionDirection.INCOMING) is True
    assert report.ready is True, [issue.reason for issue in report.issues]
    assert report.issues == ()


def test_preflight_does_not_treat_a_near_miss_token_as_employment() -> None:
    """Normalisation folds case and whitespace only; it does not widen the catalogue."""
    not_nomina = _transaction(
        "row-not-nomina",
        direction=TransactionDirection.INCOMING,
        amount=Decimal("1850.00"),
        irpf_category="trabajos",
        category_id=None,
        taxable_base=None,
        iva_rate=None,
        iva_amount=None,
    )

    report = preflight_transaction_catalogue(
        bucket_id=_BUCKET_ID,
        period=_Q2_2026,
        transactions=TransactionCatalogue.from_transactions((not_nomina,)),
    )

    assert has_employment_irpf_category("trabajos", direction=TransactionDirection.INCOMING) is False
    assert report.ready is False
    assert LedgerPreflightIssueReason.MISSING_TAXABLE_BASE in {issue.reason for issue in report.issues}
