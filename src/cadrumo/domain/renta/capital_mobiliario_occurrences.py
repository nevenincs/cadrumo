"""Occurrence arithmetic for capital-mobiliario interest and dividends.

An occurrence is one position and one detail record of the official design, as
the registry concept vocabulary names it. Its net cash is what the linked income
rows credited, already imputed to the ejercicio by the caller.
The payer record states the taxpayer's own share of what the payer paid and
withheld (RIRPF art. 108.3), so reconciliation is per payer and never per
position. A payer feeding one occurrence has that occurrence's withholding
read off its record. A payer feeding several occurrences has each withholding
rebuilt from the governed rate on the full consideration (RIRPF art. 93.1);
nothing is ever split proportionally.

This module is pure arithmetic. The rate is a caller-supplied registry value,
and every disagreement or missing piece of evidence is a typed refusal that
names the payer.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final, Protocol

from ...core.money.rounding import CENT, round_to_cents
from .errors import RentaValidationError

__all__ = [
    "AttestedNoWithholding",
    "CapitalMobiliarioOccurrence",
    "ComputedOccurrence",
    "PayerComputed",
    "PayerEvidence",
    "PayerOutcome",
    "PayerRecordEvidence",
    "PayerRecordView",
    "PayerRefusal",
    "PayerRefusalKind",
    "compute_capital_mobiliario_occurrences",
]

_ZERO: Final = Decimal(0)
_ONE: Final = Decimal(1)


class PayerRecordView(Protocol):
    """The two figures of a payer record that the arithmetic reads."""

    @property
    def importe_integro(self) -> Decimal:
        """Return the gross income the payer certifies for the taxpayer."""
        ...

    @property
    def retencion(self) -> Decimal:
        """Return the retención the payer certifies for the taxpayer."""
        ...


@dataclass(frozen=True, slots=True)
class CapitalMobiliarioOccurrence:
    """One position and one detail record, with the cash its linked rows credited."""

    position_ref: str
    detail_record: str
    """The official detail record the registry concept vocabulary routes the rows to."""
    payer_key: str
    holding_share: Decimal
    """The taxpayer's ownership share, greater than zero and at most one."""
    net_cash: Decimal
    """The sum of the linked income rows, imputed to the ejercicio."""
    expenses: Decimal

    def __post_init__(self) -> None:
        """Refuse an unnamed occurrence, a share outside (0, 1] or a negative amount."""
        if not self.position_ref or not self.payer_key or not self.detail_record:
            raise RentaValidationError("an occurrence names its position, its detail record and its payer")
        if not _ZERO < self.holding_share <= _ONE:
            raise RentaValidationError(f"holding share of {self.position_ref} is outside (0, 1]")
        if self.net_cash < _ZERO or self.expenses < _ZERO:
            raise RentaValidationError(f"net cash or expenses of {self.position_ref} is negative")

    @property
    def share_of_cash(self) -> Decimal:
        """Return the taxpayer's share of the net cash, unrounded."""
        return self.holding_share * self.net_cash


@dataclass(frozen=True, slots=True)
class PayerRecordEvidence:
    """A payer record that backs the payer's occurrences."""

    record: PayerRecordView


@dataclass(frozen=True, slots=True)
class AttestedNoWithholding:
    """The operator's attestation that this payer practised no withholding."""


type PayerEvidence = PayerRecordEvidence | AttestedNoWithholding


class PayerRefusalKind(StrEnum):
    """Why a payer's occurrences are not computed."""

    PAYER_EVIDENCE_MISSING = "payer_evidence_missing"
    """Linked rows, but neither a payer record nor an attested absence."""
    PAYER_CHECK_MISMATCH = "payer_check_mismatch"
    """Rebuilt gross and the record's importe integro differ by more than a cent."""
    WITHHOLDING_SUM_MISMATCH = "withholding_sum_mismatch"
    """Rebuilt withholdings and the record's retención differ by more than a cent per occurrence."""


@dataclass(frozen=True, slots=True)
class ComputedOccurrence:
    """One occurrence's cent-rounded figures."""

    position_ref: str
    detail_record: str
    payer_key: str
    gross: Decimal
    withholding: Decimal
    expenses: Decimal


@dataclass(frozen=True, slots=True)
class PayerComputed:
    """A payer whose occurrences were computed."""

    payer_key: str
    occurrences: tuple[ComputedOccurrence, ...]


@dataclass(frozen=True, slots=True)
class PayerRefusal:
    """A payer whose occurrences are not computed, with both figures where two disagree."""

    payer_key: str
    kind: PayerRefusalKind
    position_refs: tuple[str, ...]
    computed: Decimal | None = None
    """The figure rebuilt from the ledger rows."""
    recorded: Decimal | None = None
    """The figure the payer record states."""


type PayerOutcome = PayerComputed | PayerRefusal


def _within(first: Decimal, second: Decimal, occurrence_count: int) -> bool:
    return abs(first - second) <= CENT * occurrence_count


def _refusal(
    group: tuple[CapitalMobiliarioOccurrence, ...],
    kind: PayerRefusalKind,
    computed: Decimal | None = None,
    recorded: Decimal | None = None,
) -> PayerRefusal:
    return PayerRefusal(
        payer_key=group[0].payer_key,
        kind=kind,
        position_refs=tuple(o.position_ref for o in group),
        computed=None if computed is None else round_to_cents(computed),
        recorded=recorded,
    )


def _computed(
    group: tuple[CapitalMobiliarioOccurrence, ...],
    figures: Iterable[tuple[Decimal, Decimal]],
) -> PayerComputed:
    return PayerComputed(
        payer_key=group[0].payer_key,
        occurrences=tuple(
            ComputedOccurrence(
                position_ref=o.position_ref,
                detail_record=o.detail_record,
                payer_key=o.payer_key,
                gross=round_to_cents(gross),
                withholding=round_to_cents(withholding),
                expenses=round_to_cents(o.expenses),
            )
            for o, (gross, withholding) in zip(group, figures, strict=True)
        ),
    )


def _single(group: tuple[CapitalMobiliarioOccurrence, ...], evidence: PayerRecordEvidence) -> PayerOutcome:
    retencion = evidence.record.retencion
    rebuilt = group[0].share_of_cash + retencion
    if not _within(rebuilt, evidence.record.importe_integro, 1):
        return _refusal(group, PayerRefusalKind.PAYER_CHECK_MISMATCH, rebuilt, evidence.record.importe_integro)
    return _computed(group, [(rebuilt, retencion)])


def _multiple(
    group: tuple[CapitalMobiliarioOccurrence, ...],
    evidence: PayerRecordEvidence,
    rate: Decimal,
) -> PayerOutcome:
    record = evidence.record
    rebuilt_total = sum((o.share_of_cash for o in group), _ZERO) + record.retencion
    if not _within(rebuilt_total, record.importe_integro, 1):
        return _refusal(group, PayerRefusalKind.PAYER_CHECK_MISMATCH, rebuilt_total, record.importe_integro)
    grosses = [round_to_cents(o.share_of_cash / (_ONE - rate)) for o in group]
    withholdings = [round_to_cents(rate * gross) for gross in grosses]
    withheld_total = sum(withholdings, _ZERO)
    if not _within(withheld_total, record.retencion, len(group)):
        return _refusal(group, PayerRefusalKind.WITHHOLDING_SUM_MISMATCH, withheld_total, record.retencion)
    return _computed(group, zip(grosses, withholdings, strict=True))


def _resolve_payer(
    group: tuple[CapitalMobiliarioOccurrence, ...],
    evidence: PayerEvidence | None,
    rate: Decimal,
) -> PayerOutcome:
    match evidence:
        case None:
            return _refusal(group, PayerRefusalKind.PAYER_EVIDENCE_MISSING)
        case AttestedNoWithholding():
            return _computed(group, [(o.share_of_cash, _ZERO) for o in group])
        case PayerRecordEvidence() if len(group) == 1:
            return _single(group, evidence)
        case PayerRecordEvidence():
            return _multiple(group, evidence, rate)


def compute_capital_mobiliario_occurrences(
    occurrences: Iterable[CapitalMobiliarioOccurrence],
    evidence_by_payer: Mapping[str, PayerEvidence],
    withholding_rate: Decimal,
) -> tuple[PayerOutcome, ...]:
    """Compute every occurrence payer by payer, in order of each payer's first occurrence.

    ``withholding_rate`` is the governed rate as a fraction in (0, 1), supplied
    from the registry by the caller. A payer is either computed in full or
    refused in full.

    Raises:
        RentaValidationError: When the rate is outside (0, 1) or an occurrence repeats a
            position and detail record.
    """
    if not _ZERO < withholding_rate < _ONE:
        raise RentaValidationError("the withholding rate is outside (0, 1)")
    groups: dict[str, list[CapitalMobiliarioOccurrence]] = defaultdict(list)
    seen: set[tuple[str, str]] = set()
    for occurrence in occurrences:
        identity = (occurrence.position_ref, occurrence.detail_record)
        if identity in seen:
            raise RentaValidationError(
                f"position {occurrence.position_ref} repeats detail record {occurrence.detail_record}"
            )
        seen.add(identity)
        groups[occurrence.payer_key].append(occurrence)
    return tuple(
        _resolve_payer(tuple(group), evidence_by_payer.get(payer_key), withholding_rate)
        for payer_key, group in groups.items()
    )
