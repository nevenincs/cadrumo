"""Income-concept base membership for one ledger row, refused when the pinned authority lacks the concept.

The domain predicates in :mod:`~domain.transactions.volumen_ingresos` decide
whether a concept belongs in a base. They take a concept, not a row, so their
own refusal of an undeclared concept cannot say which ledger entry carries it.
These wrappers judge the row's concept against the same vocabulary, on the same
date and authority the predicate then classifies it with, and refuse with the
row named before the predicate is asked.
"""

from __future__ import annotations

from datetime import date

from ...domain.calculations.registry.concepto_ingreso import resolve_concepto_ingreso_catalogue
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource
from ...domain.transactions.models import Transaction
from ...domain.transactions.volumen_ingresos import (
    counts_toward_art_109_activity_income,
    counts_toward_volumen_de_ingresos,
)
from .errors import UnacceptedLedgerRegistryValueError


def _require_declared_concepto_ingreso(
    transaction: Transaction,
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> None:
    concepto = transaction.concepto_ingreso
    if concepto is None:
        return
    catalogue = resolve_concepto_ingreso_catalogue(effective_date=effective_date, authority=authority)
    try:
        catalogue.require(concepto)
    except RegistryValidationError as exc:
        raise UnacceptedLedgerRegistryValueError(
            field="concepto_ingreso",
            value=str(concepto),
            transaction_id=transaction.transaction_id,
            effective_date=effective_date,
        ) from exc


def row_counts_toward_volumen_de_ingresos(
    transaction: Transaction,
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> bool:
    """Return whether the row's receipt belongs in the art. 110.1.c) volumen de ingresos.

    Raises:
        UnacceptedLedgerRegistryValueError: When the row's declared concept is
            not in the income-concept vocabulary ``authority`` selects for
            ``effective_date``.
    """
    _require_declared_concepto_ingreso(transaction, effective_date=effective_date, authority=authority)
    return counts_toward_volumen_de_ingresos(
        transaction.concepto_ingreso,
        effective_date=effective_date,
        authority=authority,
    )


def row_counts_toward_art_109_activity_income(
    transaction: Transaction,
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> bool:
    """Return whether the row's receipt belongs in the art. 109 retention-coverage base.

    Raises:
        UnacceptedLedgerRegistryValueError: When the row's declared concept is
            not in the income-concept vocabulary ``authority`` selects for
            ``effective_date``.
    """
    _require_declared_concepto_ingreso(transaction, effective_date=effective_date, authority=authority)
    return counts_toward_art_109_activity_income(
        transaction.concepto_ingreso,
        effective_date=effective_date,
        authority=authority,
    )


__all__ = ["row_counts_toward_art_109_activity_income", "row_counts_toward_volumen_de_ingresos"]
