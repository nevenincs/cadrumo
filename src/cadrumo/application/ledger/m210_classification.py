"""Assembling one explicit Modelo 210 income classification from operator intent.

``M210IncomeClassification`` is a domain record that only accepts a complete,
valid set. Deciding whether the operator supplied one -- and whether the
transaction they named can carry it at all -- is the work in front of that
record, and it lived in the CLI option object.

Two rules travel with it. Modelo 210 declares non-resident INCOME, so an
outgoing row cannot carry the classification whatever else is supplied. And the
four facts that constitute a declaration are answered together or not at all:
a code with no rate, or a rate with no gross amount, describes no filing
position. Half of one would persist a classification the IRNR projection cannot
compute from, which is worse than the operator being told to finish answering.
"""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Final

from ...core.irnr import M210PayerMode
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.errors import TransactionValidationError
from ...domain.transactions.m210_income_classification import M210IncomeClassification
from .actions_common import resolve_transaction_repository

if TYPE_CHECKING:
    from ...domain.transactions.protocols import TransactionCatalogueRepositoryProtocol

#: The four answers that together constitute one M210 declaration.
_REQUIRED_ANSWERS: Final[tuple[str, ...]] = (
    "tipo_renta_code",
    "gross_income_amount",
    "applicable_rate",
    "payer_mode",
)


def resolve_m210_income_classification(
    *,
    bucket_id: str,
    transaction_id: str,
    tipo_renta_code: str | None = None,
    gross_income_amount: Decimal | None = None,
    applicable_rate: Decimal | None = None,
    payer_mode: M210PayerMode | None = None,
    payer_id: str | None = None,
    asset_or_right_id: str | None = None,
    transaction_repository: TransactionCatalogueRepositoryProtocol | None = None,
) -> M210IncomeClassification | None:
    """Build the explicit M210 classification the operator asked for, if any.

    Args:
        bucket_id: The owning profile bucket.
        transaction_id: The transaction being classified.
        tipo_renta_code: The two-character official income-type code.
        gross_income_amount: The gross income declared for the row.
        applicable_rate: The rate applied, as a unit proportion.
        payer_mode: Single or multiple payer.
        payer_id: The payer, when identified.
        asset_or_right_id: The asset or right the income arises from.
        transaction_repository: Injected catalogue; resolved when omitted.

    Returns:
        The classification, or ``None`` when no M210 answer was supplied at all.

    Raises:
        TransactionValidationError: When the four required answers are
            partially supplied, or the named transaction is absent or not
            incoming.
    """
    supplied = {
        "tipo_renta_code": tipo_renta_code,
        "gross_income_amount": gross_income_amount,
        "applicable_rate": applicable_rate,
        "payer_mode": payer_mode,
    }
    answered = [name for name, value in supplied.items() if value is not None]
    if not answered:
        return None
    if tipo_renta_code is None or gross_income_amount is None or applicable_rate is None or payer_mode is None:
        raise TransactionValidationError(
            "an explicit Modelo 210 classification requires every declaration answer",
            context={
                "transaction_id": transaction_id,
                "answered": ", ".join(answered),
                "missing": ", ".join(name for name in _REQUIRED_ANSWERS if supplied[name] is None),
            },
        )

    repository = resolve_transaction_repository(bucket_id=bucket_id, repository=transaction_repository)
    transaction = repository.load().get(transaction_id)
    if transaction is None or transaction.direction is not TransactionDirection.INCOMING:
        raise TransactionValidationError(
            "Modelo 210 declares non-resident income, so only an incoming transaction carries it",
            context={
                "transaction_id": transaction_id,
                "required_direction": TransactionDirection.INCOMING.value,
                "actual_direction": "absent" if transaction is None else transaction.direction.value,
            },
        )

    return M210IncomeClassification(
        official_tipo_renta_code=tipo_renta_code,
        gross_income_amount=gross_income_amount,
        applicable_rate=applicable_rate,
        payer_mode=payer_mode,
        payer_id=payer_id,
        asset_or_right_id=asset_or_right_id,
    )


__all__ = ["resolve_m210_income_classification"]
