"""Readiness for the two inputs that bore no IVA: the RETA quota and an exempt premium.

Readiness is what a Modelo 303 calculation refuses on, so these rows have to
clear it or the quarter cannot be filed. A Social Security contribution sits
outside the IVA taxable event (LIVA art. 7) and an insurance premium is exempt
(LIVA art. 20.Uno.16); neither bore a cuota, so LIVA art. 92.Uno grants no
deduction on either and none needs classifying.

What readiness still owes the operator is the other three answers: the IVA
substrate is asked for rather than inferred from the gross, a deduction claimed on
a cuota-less row is reported, and an ordinary taxable purchase still needs its
classification supplied at the ledger write.
"""

from __future__ import annotations

from collections.abc import Callable
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

type _ZeroCuotaRowFactory = Callable[..., Transaction]
"""One of the two cuota-less rows, built by a case that varies its fields."""

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_BOOKED = date(2026, 4, 5)
_RETA_QUOTA = Decimal("314.40")
_PREMIUM = Decimal("240.00")
_INVOICE_PROVENANCE: dict[str, object] = {
    "authority": "invoice_evidence",
    "source_locator": "invoice:REC-2026-1",
    "evidence_digest": "a" * 64,
}


def _zero_cuota_row(
    provider_id: str,
    *,
    amount: Decimal,
    iva_category: str,
    category_id: str,
    declare_substrate: bool = True,
    **updates: object,
) -> Transaction:
    """One received business row whose operation raised no IVA cuota."""
    row = _transaction(
        provider_id,
        direction=TransactionDirection.OUTGOING,
        amount=amount,
        category_id=category_id,
        taxable_base=amount if declare_substrate else None,
        iva_rate=Decimal("0") if declare_substrate else None,
        iva_amount=Decimal("0") if declare_substrate else None,
        iva_category=IvaCategory(iva_category),
        booked_date=_BOOKED,
    )
    return Transaction.model_validate(row.model_dump() | updates) if updates else row


def _reta_quota(*, declare_substrate: bool = True, **updates: object) -> Transaction:
    return _zero_cuota_row(
        "reta-quota",
        amount=_RETA_QUOTA,
        iva_category="operacion_no_sujeta",
        category_id="cuotas_autonomos_ss",
        declare_substrate=declare_substrate,
        **updates,
    )


def _exempt_premium(*, declare_substrate: bool = True, **updates: object) -> Transaction:
    return _zero_cuota_row(
        "insurance-premium",
        amount=_PREMIUM,
        iva_category="domestic_exempt",
        category_id="seguros_responsabilidad_civil",
        declare_substrate=declare_substrate,
        exemption_article=IvaExemptionArticle("art_20_other"),
        **updates,
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


def test_the_quarter_is_ready_with_both_zero_cuota_inputs(*, operation: PinnedAuthorityOperation) -> None:
    """The blocked quarter now clears readiness with both rows in it."""
    assert _reasons(_reta_quota(), _exempt_premium(), operation=operation) == []


def test_the_iva_substrate_is_still_asked_for_rather_than_inferred(*, operation: PinnedAuthorityOperation) -> None:
    """A row carrying no base, tipo or cuota is reported, not filled from the gross.

    The remedy is the operator declaring the three facts, which for these
    categories means the amount with a zero tipo and a zero cuota. Deriving them
    from the movement would put an undeclared base on a return.
    """
    assert _reasons(_reta_quota(declare_substrate=False), operation=operation) == [
        LedgerPreflightIssueReason.MISSING_TAXABLE_BASE,
        LedgerPreflightIssueReason.MISSING_IVA_AMOUNT,
        LedgerPreflightIssueReason.MISSING_IVA_RATE,
    ]


@pytest.mark.parametrize("row_factory", [_reta_quota, _exempt_premium])
def test_a_deduction_claimed_on_a_cuota_less_row_is_reported(
    row_factory: _ZeroCuotaRowFactory,
    *,
    operation: PinnedAuthorityOperation,
) -> None:
    """Relaxing the requirement must not make the claim pass readiness."""
    assert _reasons(
        row_factory(
            deduction_fact_kind="domestic_current",
            deduction_provenance=_INVOICE_PROVENANCE,
        ),
        operation=operation,
    ) == [LedgerPreflightIssueReason.INADMISSIBLE_DEDUCTION_CLASSIFICATION]


def test_an_ordinary_taxable_purchase_keeps_passing_readiness_unclassified(
    *, operation: PinnedAuthorityOperation
) -> None:
    """The exclusion case, and the boundary readiness deliberately does not own.

    An absent classification on a row that DOES bear a deducible cuota is
    supplied at the ledger write, not corrected here, so readiness stays silent
    and the calculation's own gate withholds the row. This asserts the
    distinction survived: readiness reports only a present classification the law
    does not grant.
    """
    assert _reasons(_transaction("taxable-purchase", booked_date=_BOOKED), operation=operation) == []
