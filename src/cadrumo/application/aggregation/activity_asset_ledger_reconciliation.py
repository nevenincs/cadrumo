"""Weigh what the activity-asset register says was paid against what the ledger says today.

Registration checks one element against its rows, once.  A row can be edited
afterwards, and two elements can each fit a row while together exceeding it, so
the calculation weighs the whole register against the ledger it reads now.  The
outcome is a finding and never a refusal: the register's basis stays the
register's, and the filer decides which side is wrong.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.external_constants import DEFAULT_CURRENCY
from ...domain.calculations.registry.iva_deduction_catalogue import is_iva_deduction_kind
from ...domain.renta.actividad_asset.claims import current_revisions
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import Transaction
from ..invoices.catalogue_reads_ports import TransactionCatalogueReader
from .source_diagnostic_reason import CalculationSourceDiagnosticReason
from .source_mesh import CalculationSourceDiagnostic

_INVESTMENT_ACQUISITION_KINDS = "kind.investment_acquisition"


@dataclass(frozen=True, slots=True)
class _AcquisitionGroup:
    """Elements joined by a shared ledger row, and every row any of them names."""

    revisions: tuple[ActivityAssetRevision, ...]
    transaction_ids: frozenset[str]


def _acquisition_groups(revisions: Iterable[ActivityAssetRevision]) -> tuple[_AcquisitionGroup, ...]:
    groups: list[_AcquisitionGroup] = []
    for revision in revisions:
        joined = frozenset(revision.acquisition_transaction_ids)
        members = (revision,)
        apart: list[_AcquisitionGroup] = []
        for group in groups:
            if group.transaction_ids & joined:
                joined |= group.transaction_ids
                members = (*group.revisions, *members)
            else:
                apart.append(group)
        groups = [*apart, _AcquisitionGroup(members, joined)]
    return tuple(groups)


def _in_year(revision: ActivityAssetRevision, *, tax_year: int) -> bool:
    baja = revision.disposal
    return (
        bool(revision.acquisition_transaction_ids)
        and revision.in_service_date.year <= tax_year
        and (baja is None or baja.disposal_date.year >= tax_year)
    )


def _paid_in_euro(row: Transaction) -> Decimal | None:
    return row.raw.amount if row.raw.currency == DEFAULT_CURRENCY else row.value_in_eur


def activity_asset_ledger_findings(
    revisions: tuple[ActivityAssetRevision, ...],
    *,
    ledger: TransactionCatalogueReader,
    tax_year: int,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Report the elements of ``tax_year`` whose cost the ledger does not bear out, or only partly explains.

    An element acquired outside the ledger names no row, and one whose rows are all
    absent from the ledger read leaves nothing to weigh.
    Paying less than the cost, or a price above the declared bases, reads as
    ``register_acquisition_exceeds_ledger``.  A price below the declared bases of a
    row booked this year reads as ``register_acquisition_partly_accounted``: the row
    is withheld whole, so the remainder deducts nothing, whether it is another
    purchase, a private share or an understated price.

    Returns:
        At most one finding per group of elements sharing a row.
    """
    current = current_revisions(revisions)
    groups = _acquisition_groups(
        current[asset_id] for asset_id in sorted(current) if _in_year(current[asset_id], tax_year=tax_year)
    )
    if not groups:
        return ()
    found = ledger.load().transactions
    findings: list[CalculationSourceDiagnostic] = []
    for group in groups:
        rows = tuple(found[row] for row in sorted(group.transaction_ids) if row in found)
        if not rows:
            continue
        finding = _group_finding(group, rows, tax_year=tax_year)
        if finding is None:
            continue
        reason, message, remedy = finding
        findings.append(
            CalculationSourceDiagnostic(
                reason=reason,
                source_kind=source_kind,
                resolver_id=resolver_id,
                source_ref=f"activity-asset:{group.revisions[0].asset_id}",
                message=message,
                remedy=remedy,
            ),
        )
    return tuple(findings)


def _group_finding(
    group: _AcquisitionGroup,
    rows: tuple[Transaction, ...],
    *,
    tax_year: int,
) -> tuple[CalculationSourceDiagnosticReason, str, str] | None:
    names = ", ".join(repr(revision.asset_id) for revision in group.revisions)
    cost = sum((revision.basis.acquisition_cost() for revision in group.revisions), Decimal("0"))
    price = sum((revision.basis.basis_amount for revision in group.revisions), Decimal("0"))
    payments = tuple(_paid_in_euro(row) for row in rows if row.direction is TransactionDirection.OUTGOING)
    exceeds = "correct the element's price in the register, or the ledger entry it names"
    if all(amount is not None for amount in payments):
        paid = sum((amount for amount in payments if amount is not None), Decimal("0"))
        if cost > paid:
            return (
                "register_acquisition_exceeds_ledger",
                f"elements {names} state a cost of {cost} EUR and the ledger entries they name paid {paid} EUR",
                exceeds,
            )
    if len(rows) != len(group.transaction_ids) or any(row.raw.currency != DEFAULT_CURRENCY for row in rows):
        return None
    bases = tuple(row.taxable_base for row in rows)
    if any(row_base is None for row_base in bases):
        return None
    base = sum((row_base for row_base in bases if row_base is not None), Decimal("0"))
    if price > base:
        return (
            "register_acquisition_exceeds_ledger",
            f"elements {names} state a price of {price} EUR and the ledger entries they name declare a base of "
            f"{base} EUR",
            exceeds,
        )
    if price < base and any(row.raw.booked_date.year == tax_year for row in rows):
        return (
            "register_acquisition_partly_accounted",
            f"the ledger entries of elements {names} declare a base of {base} EUR and the elements account for "
            f"{price} EUR; the remaining {base - price} EUR deducts nothing",
            "register what else those entries paid for, or correct the element's price if it is understated",
        )
    return None


def capital_good_transaction_ids(
    transaction_ids: Iterable[str],
    *,
    ledger: TransactionCatalogueReader,
    tax_year: int,
) -> frozenset[str]:
    """Return the rows whose IVA treatment already declares them a bien de inversión.

    A bien de inversión is durable (LIVA art. 108), so the same purchase cannot also
    be a current expense of the Renta: its deduction is the amortization, whatever
    category the row carries.

    Returns:
        The addressed rows carrying an investment-acquisition deduction kind.
    """
    addressed = frozenset(transaction_ids)
    if not addressed:
        return frozenset[str]()
    return frozenset(
        str(transaction_id)
        for transaction_id, row in ledger.load().transactions.items()
        if transaction_id in addressed
        and row.deduction_fact_kind is not None
        and is_iva_deduction_kind(
            row.deduction_fact_kind,
            _INVESTMENT_ACQUISITION_KINDS,
            effective_date=date(tax_year, 12, 31),
        )
    )


__all__ = ["activity_asset_ledger_findings", "capital_good_transaction_ids"]
