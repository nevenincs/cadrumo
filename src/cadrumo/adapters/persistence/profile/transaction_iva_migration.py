"""Exact persisted IVA deduction facts and dated rate authority for schema migration."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import TYPE_CHECKING

from ....core.iva_deduction_fact import IvaDeductionFactKind
from ....domain.calculations.registry.iva_deduction_catalogue import is_iva_deduction_kind
from ....domain.calculations.registry.iva_rate_kind_catalogue import resolve_iva_rate_kind_catalogue
from ....domain.iva.deduction_facts import IvaDeductionClassificationProvenance
from ....domain.iva.lookup import unique_rate_kind_for_declared_rate
from ....domain.iva.schema import IvaCategory, IvaRateKind, spanish_eu_member_state
from ....domain.transactions.errors import LedgerStorageError
from ....domain.transactions.models import (
    Transaction,
)

if TYPE_CHECKING:  # pragma: no cover — import-cycle guard
    pass


@dataclass(frozen=True, slots=True)
class MigratedIvaDeductionFact:
    """The complete IVA authority axis required to migrate one transaction row."""

    kind: IvaDeductionFactKind
    provenance: IvaDeductionClassificationProvenance
    taxable_base: Decimal
    iva_rate: Decimal
    iva_amount: Decimal
    category: IvaCategory


def migrated_iva_deduction_fact(transaction: Transaction) -> MigratedIvaDeductionFact | None:
    """Return complete persisted IVA authority, refusing partial legacy evidence."""
    taxable_base = transaction.taxable_base
    iva_rate = transaction.iva_rate
    iva_amount = transaction.iva_amount
    category = transaction.iva_category
    if all(value is None for value in (taxable_base, iva_rate, iva_amount, category)):
        return None
    kind = transaction.deduction_fact_kind
    provenance = transaction.deduction_provenance
    if (
        kind is None
        or provenance is None
        or taxable_base is None
        or iva_rate is None
        or iva_amount is None
        or category is None
    ):
        raise LedgerStorageError(
            f"transaction {transaction.transaction_id}: exact IVA kind, provenance, "
            "amounts, rate, and category are required"
        )
    return MigratedIvaDeductionFact(
        kind=kind,
        provenance=provenance,
        taxable_base=taxable_base,
        iva_rate=iva_rate,
        iva_amount=iva_amount,
        category=category,
    )


def migrated_iva_rate_kind(
    transaction: Transaction,
    fact: MigratedIvaDeductionFact,
) -> IvaRateKind:
    """Resolve the one dated legal rate tier for persisted IVA evidence."""
    operation_date = transaction.operation_date or transaction.raw.value_date or transaction.raw.booked_date
    from ....domain.calculations.registry.authority import bundled_indexed_authority

    with bundled_indexed_authority().operation() as operation:
        if is_iva_deduction_kind(fact.kind, "kind.reagp"):
            return resolve_iva_rate_kind_catalogue(effective_date=operation_date, authority=operation).exempt_token
        rate_kind = unique_rate_kind_for_declared_rate(
            spanish_eu_member_state(effective_date=operation_date, authority=operation),
            fact.iva_rate,
            operation_date,
            operation=operation,
        )
    if rate_kind is None:
        raise LedgerStorageError(
            f"transaction {transaction.transaction_id}: persisted IVA rate does not resolve to exactly one legal tier"
        )
    return rate_kind
