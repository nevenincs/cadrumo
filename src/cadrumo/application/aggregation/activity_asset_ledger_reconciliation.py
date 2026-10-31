"""Weigh what the activity-asset register says was paid against what the ledger says today.

Registration checks one element against its rows, once.  It reads rows from
the :class:`InvoiceCatalogue` alongside the ledger, and a row can be edited
afterwards, and two elements can each fit a row while together exceeding it, so
the calculation weighs the whole register against the ledger it reads now.  The
outcome is a finding and never a refusal: the register's basis stays the
register's, and the filer decides which side is wrong.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from ...core.external_constants import DEFAULT_CURRENCY, SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n.render import lookup_translation
from ...core.i18n.translatable import Translatable as tr
from ...core.text_fold import fold_diacritics
from ...domain.calculations.registry.iva_deduction_catalogue import is_iva_deduction_kind
from ...domain.categories.spending_category import SpendingCategory, SpendingCategoryFamily
from ...domain.categories.spending_category_catalogue import (
    amortizable_spending_categories,
    resolve_spending_category_catalogue,
)
from ...domain.invoices.catalogue import InvoiceCatalogue
from ...domain.invoices.models import Invoice
from ...domain.iva.schema import InvoiceKind
from ...domain.modelos.calculation_revision_sources import CalculationNoteFact, CalculationNoteSentence
from ...domain.renta.actividad_asset.claims import current_revisions
from ...domain.renta.actividad_asset.lifecycle import ActivityAssetRevision
from ...domain.transactions.enums import TransactionDirection
from ...domain.transactions.models import Transaction
from ..invoices.catalogue_reads_ports import (
    InvoiceCatalogueReader,
    InvoiceCatalogueReadPersistenceError,
    TransactionCatalogueReader,
)
from ._modelo_bindings_support import STORAGE_DEGRADATION_ERRORS
from .source_diagnostic_reason import CalculationSourceDiagnosticReason
from .source_mesh import CalculationSourceDiagnostic

_INVESTMENT_ACQUISITION_KINDS = "kind.investment_acquisition"
_CATEGORY_KEYWORDS_ROOT = "desktop.ledger.category_keywords"
_WORD = re.compile(r"[^\W_]+")


type _GroupFinding = tuple[CalculationSourceDiagnosticReason, str, str, CalculationNoteFact]


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

    An element acquired outside the ledger names no row, so nothing is weighed.  A row
    an element names and the ledger no longer holds reads as
    ``register_acquisition_row_missing``: what remains cannot be weighed against the
    whole cost, so that finding stands alone for its group.
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
        missing = tuple(row for row in sorted(group.transaction_ids) if row not in found)
        finding = (
            _missing_row_finding(group, missing)
            if missing
            else _group_finding(group, tuple(found[row] for row in sorted(group.transaction_ids)), tax_year=tax_year)
        )
        if finding is None:
            continue
        reason, message, remedy, fact = finding
        findings.append(
            CalculationSourceDiagnostic(
                reason=reason,
                source_kind=source_kind,
                resolver_id=resolver_id,
                source_ref=f"activity-asset:{group.revisions[0].asset_id}",
                message=message,
                remedy=remedy,
                fact=fact,
            ),
        )
    return tuple(findings)


def _element_words(group: _AcquisitionGroup) -> str:
    return ", ".join(revision.asset_id for revision in group.revisions)


def _missing_row_finding(
    group: _AcquisitionGroup,
    missing: tuple[str, ...],
) -> _GroupFinding:
    names = ", ".join(repr(revision.asset_id) for revision in group.revisions)
    return (
        "register_acquisition_row_missing",
        f"elements {names} name ledger entries the ledger no longer holds: {', '.join(missing)}",
        "enter the missing ledger entry again, or correct the element's acquisition in the register",
        CalculationNoteFact.of(
            CalculationNoteSentence.REGISTER_ROW_MISSING,
            elements=_element_words(group),
            rows=", ".join(row[-12:] for row in missing),
        ),
    )


def _group_finding(
    group: _AcquisitionGroup,
    rows: tuple[Transaction, ...],
    *,
    tax_year: int,
) -> _GroupFinding | None:
    names = ", ".join(repr(revision.asset_id) for revision in group.revisions)
    cost = sum((revision.basis.acquisition_cost() for revision in group.revisions), Decimal("0"))
    price = sum((revision.basis.basis_amount for revision in group.revisions), Decimal("0"))
    payment_finding = _payment_finding(group, rows, names=names, cost=cost)
    if payment_finding is not None:
        return payment_finding
    return _base_finding(group, rows, names=names, price=price, tax_year=tax_year)


def _payment_finding(
    group: _AcquisitionGroup, rows: tuple[Transaction, ...], *, names: str, cost: Decimal
) -> _GroupFinding | None:
    payments = tuple(_paid_in_euro(row) for row in rows if row.direction is TransactionDirection.OUTGOING)
    if all(amount is not None for amount in payments):
        paid = sum((amount for amount in payments if amount is not None), Decimal("0"))
        if cost > paid:
            return (
                "register_acquisition_exceeds_ledger",
                f"elements {names} state a cost of {cost} EUR and the ledger entries they name paid {paid} EUR",
                "correct the element's price in the register, or the ledger entry it names",
                CalculationNoteFact.of(
                    CalculationNoteSentence.REGISTER_COST_EXCEEDS_PAID,
                    elements=_element_words(group),
                    cost=cost,
                    paid=paid,
                ),
            )
    return None


def _base_finding(
    group: _AcquisitionGroup,
    rows: tuple[Transaction, ...],
    *,
    names: str,
    price: Decimal,
    tax_year: int,
) -> _GroupFinding | None:
    base = _total_taxable_base(group, rows)
    if base is None:
        return None
    if price > base:
        return (
            "register_acquisition_exceeds_ledger",
            f"elements {names} state a price of {price} EUR and the ledger entries they name declare a base of "
            f"{base} EUR",
            "correct the element's price in the register, or the ledger entry it names",
            CalculationNoteFact.of(
                CalculationNoteSentence.REGISTER_PRICE_EXCEEDS_BASE,
                elements=_element_words(group),
                price=price,
                base=base,
            ),
        )
    if price < base and any(row.raw.booked_date.year == tax_year for row in rows):
        return (
            "register_acquisition_partly_accounted",
            f"the ledger entries of elements {names} declare a base of {base} EUR and the elements account for "
            f"{price} EUR; the remaining {base - price} EUR deducts nothing",
            "register what else those entries paid for, or correct the element's price if it is understated",
            CalculationNoteFact.of(
                CalculationNoteSentence.REGISTER_PARTLY_ACCOUNTED,
                elements=_element_words(group),
                price=price,
                base=base,
                remainder=base - price,
            ),
        )
    return None


def _total_taxable_base(group: _AcquisitionGroup, rows: tuple[Transaction, ...]) -> Decimal | None:
    if any(row.raw.currency != DEFAULT_CURRENCY for row in rows):
        return None
    bases = tuple(row.taxable_base for row in rows)
    if any(row_base is None for row_base in bases):
        return None
    return sum((row_base for row_base in bases if row_base is not None), Decimal("0"))


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


def _words(text: str) -> frozenset[str]:
    return frozenset(str(word) for word in _WORD.findall(fold_diacritics(text).casefold()))


def _amortizable_keywords(categories: Iterable[SpendingCategory]) -> frozenset[str]:
    """Return the search words of ``categories`` across every supported catalogue.

    Reading every catalogue, never the operator's, keeps a return's findings the same
    in any interface language.  Each catalogue carries the Spanish words plus its own.
    """
    return frozenset(
        word
        for category in categories
        for locale in SUPPORTED_OUTPUT_LANGUAGES
        for word in _words(lookup_translation(f"{_CATEGORY_KEYWORDS_ROOT}.{category.value}", locale=locale) or "")
    )


def _purchase_invoice_lines(rows: Iterable[Transaction], catalogue: InvoiceCatalogue) -> dict[str, tuple[str, ...]]:
    """Return the line descriptions of the purchase invoices each row names or is linked from."""
    received = tuple(invoice for invoice in catalogue.invoices.values() if invoice.kind is InvoiceKind.RECEIVED)
    lines = _linked_invoice_lines(received)
    named = {invoice.invoice_id: invoice for invoice in received}
    words: dict[str, tuple[str, ...]] = {}
    for row in rows:
        evidence = named.get(row.purchase_invoice_evidence_id or "")
        own = () if evidence is None else tuple(line.description for line in evidence.lines)
        words[row.transaction_id] = (*own, *lines.get(row.transaction_id, ()))
    return words


def _linked_invoice_lines(received: Iterable[Invoice]) -> dict[str, list[str]]:
    lines: dict[str, list[str]] = {}
    for invoice in received:
        descriptions = [line.description for line in invoice.lines]
        for transaction_id in invoice.linked_transaction_ids:
            lines.setdefault(transaction_id, []).extend(descriptions)
    return lines


def possibly_durable_expense_findings(
    transaction_ids: Iterable[str],
    *,
    revisions: tuple[ActivityAssetRevision, ...],
    ledger: TransactionCatalogueReader,
    invoices: InvoiceCatalogueReader,
    tax_year: int,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    """Ask about the deducted rows whose own words describe an amortizable element.

    A durable element deducts only by amortization (LIS art. 12.1, RIS art. 3.2), even
    one of 300 EUR or less, which is libertad de amortización (LIS art. 12.3.e).  So no
    amount separates durable from consumable, and the ledger cannot prove durability:
    the row keeps deducting and the filer answers.  An unreadable invoice catalogue
    reports its degradation and leaves only the rows' own descriptions to weigh, so
    this question never costs a return its figures.

    Returns:
        One finding per row, naming it through ``source_ref``.
    """
    owned = frozenset(
        row for revision in current_revisions(revisions).values() for row in revision.acquisition_transaction_ids
    )
    addressed = frozenset(transaction_ids) - owned
    if not addressed:
        return ()
    amortizable = amortizable_spending_categories(effective_date=date(tax_year, 12, 31))
    excluded = {category.value for category in amortizable}
    capital_goods = capital_good_transaction_ids(addressed, ledger=ledger, tax_year=tax_year)
    found = ledger.load().transactions
    candidates = tuple(
        found[row]
        for row in sorted(addressed - capital_goods)
        if row in found and found[row].category_id not in excluded
    )
    if not candidates:
        return ()
    # Goods only: a dwelling's own words ("casa", "vivienda") also describe rent and IBI rows.
    office = resolve_spending_category_catalogue(effective_date=date(tax_year, 12, 31)).categories_for_family(
        SpendingCategoryFamily.OFFICE
    )
    keywords = _amortizable_keywords(category for category in amortizable if category in office)
    degraded: tuple[CalculationSourceDiagnostic, ...] = ()
    catalogue = InvoiceCatalogue()
    try:
        catalogue = invoices.load()
    except (InvoiceCatalogueReadPersistenceError, *STORAGE_DEGRADATION_ERRORS):
        degraded = (
            CalculationSourceDiagnostic(
                reason="storage_degraded",
                source_kind=source_kind,
                resolver_id=resolver_id,
                message=tr("errors.integrity.integrity_storage_secure_object_unreadable"),
            ),
        )
    invoice_lines = _purchase_invoice_lines(candidates, catalogue)
    findings = _durable_findings(candidates, invoice_lines, keywords, source_kind=source_kind, resolver_id=resolver_id)
    return (*degraded, *findings)


def _durable_findings(
    candidates: tuple[Transaction, ...],
    invoice_lines: dict[str, tuple[str, ...]],
    keywords: frozenset[str],
    *,
    source_kind: str,
    resolver_id: str,
) -> tuple[CalculationSourceDiagnostic, ...]:
    findings: list[CalculationSourceDiagnostic] = []
    for row in candidates:
        matched = keywords & _words(" ".join((row.raw.description, *invoice_lines[row.transaction_id])))
        if matched:
            findings.append(
                CalculationSourceDiagnostic(
                    reason="ledger_expense_may_be_durable",
                    source_kind=source_kind,
                    resolver_id=resolver_id,
                    source_ref=f"transaction:{row.transaction_id}",
                    message=(
                        f"ledger transaction {row.transaction_id!r} (category={row.category_id!r}) deducts as a "
                        f"current expense and its description reads as a durable element: {', '.join(sorted(matched))}"
                    ),
                    remedy="register the element if it is durable, or leave the entry if it is a consumable",
                    fact=CalculationNoteFact.of(
                        CalculationNoteSentence.POSSIBLY_DURABLE_EXPENSE,
                        row=row.transaction_id[-12:],
                        category=row.category_id or "",
                    ),
                ),
            )
    return tuple(findings)


__all__ = [
    "activity_asset_ledger_findings",
    "capital_good_transaction_ids",
    "possibly_durable_expense_findings",
]
