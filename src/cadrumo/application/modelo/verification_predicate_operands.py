"""Operand readings shared by the blocking and advisory registry predicate evaluators."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date as _date
from decimal import Decimal

from ...core.casilla_id import CasillaId
from ...core.casilla_value_absence import AbsentCasillaReading
from ...core.money.rounding import CENT
from ...core.parsing.dates import parse_date
from ...domain.calculations.registry.schema_verification import ParsedVerificationPredicate
from ...domain.deadlines.models import TaxpayerProfile
from .action_errors import ModeloPredicateDateRequiredError
from .refusal_door_verdicts import caller_defect_verdict

_UE_EEE_STATUS_FIELD = "ue_eee_status"


@dataclass(frozen=True, slots=True)
class AdmittedPredicate:
    """A registry predicate admitted to one evaluation route, its operands already read.

    ``threshold`` and ``cutoff`` are the registry-authored literals of the
    operators that carry them, read once at admission so no evaluator can meet
    an unreadable one.
    """

    parsed: ParsedVerificationPredicate
    casilla_ids: tuple[CasillaId, ...]
    threshold: Decimal | None = None
    cutoff: _date | None = None


def parse_predicate_date(raw: str) -> _date | None:
    """Parse a date string, or ``None`` when absent/unparseable.

    Accepts the ISO form (the cutoff literal shape) and the Spanish day-first
    operator-entry forms ``DD/MM/YYYY`` and ``DD-MM-YYYY``, both resolved by the
    canonical :func:`core.parsing.dates.parse_date` contract rather than a local
    format list. Used by the ``deduccion_requires_adquisicion_before`` advisory
    to read the acquisition-date TEXT casilla and the cutoff literal.

    The canonical parser requires two-digit day and month components, so a
    partially-typed ``1/2/2024`` is no longer silently resolved to a date. That
    matters here specifically: the value decides a deduction's eligibility
    against a statutory cutoff, and an under-specified entry is a date the
    operator has not actually stated. For the operator-entered acquisition date
    it returns ``None`` like any other unparseable value, so the advisory treats
    it as "no eligibility signal" rather than acting on a guess; an unreadable
    registry cutoff is instead refused at predicate admission.
    """
    text = raw.strip()
    if not text:
        return None
    for fmt in ("iso8601", "ddmmyyyy"):
        parsed = parse_date(text, fmt=fmt, on_error="none")
        if parsed is not None:
            return parsed
    return None


def roll_forward_balance_reconciles(
    ids: tuple[CasillaId, ...],
    casilla_values: Mapping[CasillaId, Decimal],
) -> bool:
    """Return whether a carry-forward closing balance reconciles to its roll-forward.

    ``ids`` is ``[closing, opening, applied, base]``, its arity fixed by
    predicate admission. The carry-forward stock continuity invariant is::

        closing == opening − applied + max(0, −base)

    the opening stock less the amount applied plus any stock newly generated
    this period. Holds within a one-cent tolerance to absorb per-detail
    rounding. A missing casilla reads as ``Decimal(0)`` via ``.get``.
    """
    closing_id, opening_id, applied_id, base_id = ids
    closing = casilla_values.get(closing_id, Decimal(0))
    opening = casilla_values.get(opening_id, Decimal(0))
    applied = casilla_values.get(applied_id, Decimal(0))
    base = casilla_values.get(base_id, Decimal(0))
    generated = max(Decimal(0), -base)
    expected = opening - applied + generated
    # Bounded at the cent quantum: absorbs the sub-cent drift a
    # total-of-per-year-detail figure accumulates, without masking a genuine
    # discontinuity, which is euros rather than cents.
    return abs(closing - expected) <= CENT


def profile_flag(profile: TaxpayerProfile, field: str, fact_date: _date | None) -> bool:
    """Read one named profile flag; the EU/EEA status is a fact of ``fact_date``.

    Parameter types: ``profile`` (:class:`~cadrumo.domain.deadlines.models.TaxpayerProfile`).
    """
    if field == _UE_EEE_STATUS_FIELD:
        if fact_date is None:
            raise ModeloPredicateDateRequiredError(
                f"Reading {field} needs the date of the filing period; none was given",
                translated_message="errors.refused.refused_modelo_predicate_date_required",
                context={"fact": field},
                precondition_verdict=caller_defect_verdict("predicate_date"),
            )
        return profile.ue_eee_status_on(fact_date)
    return bool(getattr(profile, field, False))


def equals_sum_operands(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
) -> tuple[CasillaId, Decimal, Decimal]:
    """Return the total casilla, its value, and the sum of its addends.

    Admission guarantees a total and at least two addends; a missing casilla
    reads as ``Decimal(0)`` like every other operator.
    """
    total_id, *addend_ids = predicate.casilla_ids
    addend_sum = sum((casilla_values.get(cid, Decimal(0)) for cid in addend_ids), Decimal(0))
    return total_id, casilla_values.get(total_id, Decimal(0)), addend_sum


@dataclass(frozen=True, slots=True)
class FloorSubtractionReading:
    """What a ``limited_subtractions_respect_floor`` predicate reads from the casilla values.

    ``after_limited`` is the base less the pre-floor and the limited
    subtractions; ``unresolved_ids`` are the unclassified subtractions that
    carry an amount, in the order the predicate names them, and
    ``unresolved_total`` is what they add up to.
    """

    floor_id: CasillaId
    floor: Decimal
    limited_total: Decimal
    after_limited: Decimal
    unresolved_ids: tuple[CasillaId, ...]
    unresolved_total: Decimal

    @property
    def floor_applies(self) -> bool:
        """Whether there is a positive floor to compare with."""
        return self.floor > Decimal(0)

    @property
    def breached(self) -> bool:
        """Whether the limited subtractions take the base below the floor."""
        return self.floor_applies and self.limited_total > Decimal(0) and self.after_limited < self.floor

    @property
    def unresolved(self) -> bool:
        """Whether the classification of the unclassified subtractions could change the outcome.

        Read as exempt they never breach; read as pre-floor or limited they
        breach only when they take what is left after the limited subtractions
        below the floor. With no certain breach and room for them either way,
        the outcome holds whatever their classification.
        """
        return (
            self.floor_applies
            and not self.breached
            and bool(self.unresolved_ids)
            and self.after_limited - self.unresolved_total < self.floor
        )


def floor_subtraction_reading(
    predicate: AdmittedPredicate,
    casilla_values: Mapping[CasillaId, Decimal],
) -> FloorSubtractionReading:
    """Read the floor, the subtractions by group and their outcome as the return declares them.

    Admission guarantees the five groups, a floor and base pair and at least
    one limited subtraction. The exempt group is never read: those amounts
    apply whatever the floor. A box the return leaves out declares zero. For
    the floor that holds only where the minimum does not apply: where it
    applies, the registry leaves the minimum open until the floor box is
    stated, and verification refuses before this reading matters.
    """
    admitted = dict(zip(predicate.parsed.casilla_ids, predicate.casilla_ids, strict=True))
    (floor_id, base_id), pre_floor_ids, limited_ids, unclassified_ids, _exempt_ids = (
        tuple(admitted[token] for token in group) for group in predicate.parsed.casilla_groups()
    )
    declared = AbsentCasillaReading.OMITTED_BOX_DECLARES_ZERO

    def total(ids: tuple[CasillaId, ...]) -> Decimal:
        return sum((declared.read(casilla_values, cid) for cid in ids), Decimal(0))

    limited_total = total(limited_ids)
    unresolved_ids = tuple(cid for cid in unclassified_ids if declared.read(casilla_values, cid) != Decimal(0))
    return FloorSubtractionReading(
        floor_id=floor_id,
        floor=declared.read(casilla_values, floor_id),
        limited_total=limited_total,
        after_limited=declared.read(casilla_values, base_id) - total(pre_floor_ids) - limited_total,
        unresolved_ids=unresolved_ids,
        unresolved_total=total(unresolved_ids),
    )
