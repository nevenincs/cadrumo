"""Calculate-path advisory for business expenses the ledger holds without an invoice.

Modelo 347 relates the operations the invoice catalogue records, but the
operations RD 1065/2007 art. 33.1 has the filer relate are not limited to
invoiced ones: art. 35.1 dates them by the entry of "la factura o documento
contable que sirva de justificante de las mismas". An outgoing business ledger
transaction carrying a taxable base and linked to no invoice is therefore an
operation the declaration cannot see: it names no counterparty NIF the
declarado record needs, so it is neither declared nor counted towards any
counterparty's floor.

The advisory reads the same transaction catalogue the calculation already
holds for the ejercicio, one advisory per calculation, and decides nothing: the
remedy is to record the invoice so the operation reaches the declaration.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from ...core.modelo import Modelo
from ...core.period import Period
from ...domain.calculations.registry.ids import LegalRefId
from ...domain.transactions.enums import BUSINESS_BEARING_STATES, TransactionDirection, TransactionLifecycleState
from ...domain.transactions.models import Transaction
from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol
from ..aggregation.source_mesh import CalculationSourceDiagnostic

__all__ = ["M347_UNINVOICED_EXPENSE_SOURCE_KIND", "collect_m347_uninvoiced_expense_diagnostics"]

#: Diagnostic ``source_kind`` for business expenses Modelo 347 cannot see.
M347_UNINVOICED_EXPENSE_SOURCE_KIND: Final[str] = "m347_uninvoiced_ledger_expense"

#: The provisions the message is a claim about: the duty to relate operations
#: above the floor, and their dating by the invoice or accounting document.
_ASSERTED_LEGAL_REFS: Final[tuple[LegalRefId, ...]] = ("rd-1065-2007:art-33", "rd-1065-2007:art-35")


def _is_uninvoiced_business_expense(transaction: Transaction) -> bool:
    return (
        transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and transaction.direction is TransactionDirection.OUTGOING
        and transaction.business_classification in BUSINESS_BEARING_STATES
        and transaction.taxable_base is not None
        and transaction.taxable_base > Decimal("0")
        and transaction.invoice_id is None
    )


def collect_m347_uninvoiced_expense_diagnostics(
    *,
    modelo: str,
    period_token: str,
    filing_year: int,
    transaction_repository: TransactionCatalogueRepositoryProtocol,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Advise that the ejercicio's uninvoiced business expenses are missing from Modelo 347.

    Args:
        modelo: Target modelo identifier; every modelo other than 347 is silent.
        period_token: Bare registry period token for the filing.
        filing_year: Filing year whose ledger window is read.
        transaction_repository: The calculation's bucket-bound transaction catalogue.

    Returns:
        One advisory naming the transactions, or an empty tuple when the modelo
        is not 347 or every business expense of the ejercicio is invoiced.
    """
    if modelo != Modelo("347").value:
        return ()
    period = Period.from_year_and_code(filing_year, period_token)
    catalogue = transaction_repository.load_for_date_range(period.start_date, period.end_date)
    uninvoiced = sorted(
        transaction.transaction_id
        for transaction in catalogue.transactions.values()
        if _is_uninvoiced_business_expense(transaction)
    )
    if not uninvoiced:
        return ()
    return (
        CalculationSourceDiagnostic(
            reason="source_issue",
            source_kind=M347_UNINVOICED_EXPENSE_SOURCE_KIND,
            message=(
                f"{len(uninvoiced)} business expenses of ejercicio {filing_year} carry a taxable base but no "
                "invoice, so Modelo 347 neither declares nor counts them: it relates the invoiced operations, while "
                "RD 1065/2007 art. 35.1 also dates operations by the accounting document that justifies them "
                f"({', '.join(uninvoiced)})."
            ),
            remedy=(
                "Record the invoice of each listed expense and link it to its transaction, then recalculate; an "
                "expense without one must be checked against its counterparty's annual total by hand."
            ),
            asserted_legal_refs=_ASSERTED_LEGAL_REFS,
        ),
    )
