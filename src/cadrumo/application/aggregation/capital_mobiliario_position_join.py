"""Join a saver's profile positions to the ledger rows linked to them.

A linked row names its position and its capital-mobiliario concept; the registry
concept vocabulary says which official detail record the concept feeds and
whether its amount is net income credited or an expense of that record. Rows are
imputed to the ejercicio by exigibility: a row's own accrual date when it states
one, else its value date (LIRPF art. 14.1.a).

One occurrence is one position and one detail record. Its net cash and expenses
are the taxpayer's share of the rows' sum, and nothing else is computed here: the
payer's withholding and the reconciliation belong to the occurrence arithmetic.
Every row this join cannot read raises a finding that names its position and
the detail records it leaves open, rather than vanishing from the return.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Final

from ...domain.calculations.registry.capital_mobiliario_facts import (
    CapitalMobiliarioAmountRole,
    CapitalMobiliarioConcept,
    CapitalMobiliarioConceptCatalogue,
)
from ...domain.contribuyente.posicion_record import PosicionRecord
from ...domain.iva.establishment import SPAIN_COUNTRY_CODE
from ...domain.renta.capital_mobiliario_occurrences import CapitalMobiliarioOccurrence
from ...domain.transactions.dates import transaction_filing_date
from ...domain.transactions.enums import (
    BusinessClassification,
    TransactionDirection,
    TransactionLifecycleState,
)
from ...domain.transactions.models import Transaction
from .currency_predicates import effective_eur_amount, is_non_eur_without_conversion

__all__ = [
    "CapitalMobiliarioJoin",
    "CapitalMobiliarioJoinFinding",
    "CapitalMobiliarioJoinFindingKind",
    "join_capital_mobiliario_positions",
]

_ZERO: Final = Decimal(0)
_PERCENT: Final = Decimal(100)


class CapitalMobiliarioJoinFindingKind(StrEnum):
    """Why linked rows of a position are not computed."""

    POSITION_NOT_HELD = "position_not_held"
    """The rows name a position the profile does not hold on their date."""
    ROW_NOT_READABLE = "row_not_readable"
    """A concept the vocabulary or the position's kind does not admit, an unconverted currency, or a negative sum."""
    FOREIGN_SOURCE = "foreign_source"
    """The position's income comes from another state; double taxation is not computed."""


@dataclass(frozen=True, slots=True)
class CapitalMobiliarioJoinFinding:
    """One position's rows the join leaves out, and the detail records they leave open."""

    kind: CapitalMobiliarioJoinFindingKind
    position_ref: str
    detail_records: frozenset[str] | None
    """The detail records left open; ``None`` when the rows' record is unknown, which leaves every record open."""
    row_ids: tuple[str, ...]
    payer_name: str | None = None
    country: str | None = None


@dataclass(frozen=True, slots=True)
class CapitalMobiliarioJoin:
    """The occurrences the linked rows form, and the rows left out with their reason."""

    occurrences: tuple[CapitalMobiliarioOccurrence, ...]
    findings: tuple[CapitalMobiliarioJoinFinding, ...]
    occurrence_rows: Mapping[tuple[str, str], tuple[str, ...]]
    """The row ids behind each ``(position_ref, detail_record)`` occurrence."""
    payer_names: Mapping[str, str]
    """The payer's name, by payer key, as the position states it."""
    linked_payer_keys: frozenset[str]
    """Every payer a linked row of the ejercicio names through its position, computed or left out."""

    @property
    def source_transaction_ids(self) -> tuple[str, ...]:
        """Return every row an occurrence rests on, sorted."""
        return tuple(sorted({row for rows in self.occurrence_rows.values() for row in rows}))


@dataclass(slots=True)
class _Sums:
    net_cash: Decimal = _ZERO
    expenses: Decimal = _ZERO
    rows: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _Collector:
    sums: dict[tuple[str, str], _Sums] = field(default_factory=lambda: defaultdict(_Sums))
    left_out: dict[tuple[CapitalMobiliarioJoinFindingKind, str], tuple[set[str] | None, list[str]]] = field(
        default_factory=dict
    )
    linked_payers: set[str] = field(default_factory=set)

    def leave_out(
        self, kind: CapitalMobiliarioJoinFindingKind, position_ref: str, record: str | None, row_id: str
    ) -> None:
        records, rows = self.left_out.setdefault((kind, position_ref), (set(), []))
        if records is not None and record is not None:
            records.add(record)
        else:
            self.left_out[(kind, position_ref)] = (None, rows)
        rows.append(row_id)


def imputation_date(transaction: Transaction) -> date:
    """Return the date a linked row is imputed on: its accrual date, else its value date."""
    return transaction.accrual_date or transaction_filing_date(transaction)


def _in_scope(transaction: Transaction, start: date, end: date) -> bool:
    return (
        transaction.posicion_ref is not None
        and transaction.lifecycle_state is TransactionLifecycleState.ACTIVE
        and transaction.business_classification is not BusinessClassification.REVIEWED_EXCLUDED
        and start <= imputation_date(transaction) <= end
    )


def _held_on(position: PosicionRecord | None, on: date) -> bool:
    return (
        position is not None
        and position.fecha_inicio <= on
        and (position.fecha_fin is None or on <= position.fecha_fin)
    )


def _concept(
    transaction: Transaction, position: PosicionRecord, vocabulary: CapitalMobiliarioConceptCatalogue
) -> CapitalMobiliarioConcept | None:
    token = None if transaction.concepto_capital_mobiliario is None else str(transaction.concepto_capital_mobiliario)
    concept = next((item for item in vocabulary.concepts if item.token == token), None)
    if concept is None or concept.requires_position_kind not in {None, position.tipo.value}:
        return None
    return concept


def _signed(transaction: Transaction, role: CapitalMobiliarioAmountRole) -> Decimal:
    amount = effective_eur_amount(transaction)
    incoming = transaction.direction is TransactionDirection.INCOMING
    adds = incoming if role is CapitalMobiliarioAmountRole.GROSS_INCOME else not incoming
    return amount if adds else -amount


def _collect_row(
    collector: _Collector,
    transaction: Transaction,
    positions: Mapping[str, PosicionRecord],
    vocabulary: CapitalMobiliarioConceptCatalogue,
) -> None:
    ref = transaction.posicion_ref or ""
    row_id = str(transaction.transaction_id)
    position = positions.get(ref)
    if position is not None:
        collector.linked_payers.add(position.pagador_nif)
    if position is None or not _held_on(position, imputation_date(transaction)):
        collector.leave_out(CapitalMobiliarioJoinFindingKind.POSITION_NOT_HELD, ref, None, row_id)
        return
    concept = _concept(transaction, position, vocabulary)
    if concept is None or is_non_eur_without_conversion(transaction):
        record = None if concept is None else concept.detail_record
        collector.leave_out(CapitalMobiliarioJoinFindingKind.ROW_NOT_READABLE, ref, record, row_id)
        return
    if position.pais_origen != SPAIN_COUNTRY_CODE:
        collector.leave_out(CapitalMobiliarioJoinFindingKind.FOREIGN_SOURCE, ref, concept.detail_record, row_id)
        return
    sums = collector.sums[(ref, concept.detail_record)]
    if concept.amount_role is CapitalMobiliarioAmountRole.GROSS_INCOME:
        sums.net_cash += _signed(transaction, concept.amount_role)
    else:
        sums.expenses += _signed(transaction, concept.amount_role)
    sums.rows.append(row_id)


def _occurrence(
    key: tuple[str, str], sums: _Sums, position: PosicionRecord, collector: _Collector
) -> CapitalMobiliarioOccurrence | None:
    if sums.net_cash < _ZERO or sums.expenses < _ZERO:
        for row_id in sums.rows:
            collector.leave_out(CapitalMobiliarioJoinFindingKind.ROW_NOT_READABLE, key[0], key[1], row_id)
        return None
    share = position.porcentaje_titularidad / _PERCENT
    return CapitalMobiliarioOccurrence(
        position_ref=key[0],
        detail_record=key[1],
        payer_key=position.pagador_nif,
        holding_share=share,
        net_cash=sums.net_cash,
        expenses=share * sums.expenses,
    )


def _finding(
    key: tuple[CapitalMobiliarioJoinFindingKind, str],
    value: tuple[set[str] | None, list[str]],
    positions: Mapping[str, PosicionRecord],
) -> CapitalMobiliarioJoinFinding:
    kind, ref = key
    records, rows = value
    position = positions.get(ref)
    return CapitalMobiliarioJoinFinding(
        kind=kind,
        position_ref=ref,
        detail_records=None if records is None else frozenset(records),
        row_ids=tuple(sorted(rows)),
        payer_name=None if position is None else position.pagador_nombre,
        country=None if position is None else position.pais_origen,
    )


def join_capital_mobiliario_positions(
    positions: Iterable[PosicionRecord],
    transactions: Iterable[Transaction],
    vocabulary: CapitalMobiliarioConceptCatalogue,
    *,
    start: date,
    end: date,
) -> CapitalMobiliarioJoin:
    """Form the occurrences of the ejercicio ``[start, end]`` from the positions and their linked rows.

    Returns:
        The occurrences in position and detail-record order, with every row left out named in a finding.
    """
    by_ref = {str(position.clave): position for position in positions}
    collector = _Collector()
    for transaction in transactions:
        if _in_scope(transaction, start, end):
            _collect_row(collector, transaction, by_ref, vocabulary)
    occurrences: list[CapitalMobiliarioOccurrence] = []
    occurrence_rows: dict[tuple[str, str], tuple[str, ...]] = {}
    for key in sorted(collector.sums):
        sums = collector.sums[key]
        occurrence = _occurrence(key, sums, by_ref[key[0]], collector)
        if occurrence is not None:
            occurrences.append(occurrence)
            occurrence_rows[key] = tuple(sorted(sums.rows))
    return CapitalMobiliarioJoin(
        occurrences=tuple(occurrences),
        findings=tuple(_finding(key, value, by_ref) for key, value in sorted(collector.left_out.items())),
        occurrence_rows=occurrence_rows,
        payer_names={position.pagador_nif: position.pagador_nombre for position in by_ref.values()},
        linked_payer_keys=frozenset(collector.linked_payers),
    )
