"""Domiciliación payment cutoff of a filing window, authored or derived from the governed rule.

A filing window may author ``payment_cutoff_on``, the last day AEAT accepts a
domiciliación (direct-debit) instruction with the filing. That authored date is an
explicit override and always wins. Where it is absent, the cutoff is derived from
the rule Orden EHA/1658/2009 declares, held as two governed mapping facts and
resolved through canonical governed-fact temporal selection:

* ``deadlines.domiciliation-cutoff-clause``: the Anexo II day for the modelo and
  period. The month it falls in and the nominal close of the filing period come
  from their single home, the filing-window clause
  (:mod:`cadrumo.domain.deadlines.filing_window_projection`).
* ``deadlines.domiciliation-procedure``: art. 3.2. Art. 3.2.b extends the Anexo II
  period by the days the filing period is extended when its last day is inhábil.
  From Orden HAC/241/2025 a minimum of días hábiles or naturales must remain
  before the voluntary close, counted on the calendar of a declared territory.
  Variants graded as AEAT's published practice record what the Orden does not
  say: the business-day minimum AEAT's calendars kept before that Orden, and the
  replacement of an Anexo II day falling on a weekend, or on any inhábil day, by
  the latest business day meeting the margin.

The margin is counted as AEAT's calendars apply it: the business days after the
domiciliación end up to and including the voluntary close, and the natural days
strictly between the two ends. An Anexo II day that is not replaced stands while
it meets the margin and otherwise yields to the latest business day that does.

Each rule part reaches the registry support floor and stays open past its
horizon, so the cutoff projects backward and forward with the projection
direction of each resolved fact retained. A derivation that needs a holiday
calendar the registry has not published, or whose territory is not verified for a
year it walks, is unavailable rather than computed against a holiday-free
calendar. Window matching stays with :func:`~cadrumo.domain.deadlines.plazo.resolve_filing_window`;
this module only resolves the cutoff of a window already matched.
"""

from __future__ import annotations

import calendar
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Literal

from pydantic import BaseModel, Field

from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.calendar_ccaa_catalogue import resolve_calendar_ccaa_catalogue
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.facts.variants import FactSelector
from ..calculations.registry.schema_base import DateAxis
from .errors import DeadlineValidationError
from .festivos import CalendarCCAA, HolidayCalendar, is_business_day, load_holiday_calendar
from .filing_window_projection import (
    FilingWindowClause,
    FilingWindowRuleEvidence,
    resolve_filing_window_clause,
    resolve_mapping_fact,
)

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from ..calculations.registry.schema_deadlines import DeadlineWindowDefinition

DOMICILIATION_CUTOFF_CLAUSE_FACT_ID: Final = "deadlines.domiciliation-cutoff-clause"
DOMICILIATION_PROCEDURE_FACT_ID: Final = "deadlines.domiciliation-procedure"

_MODELO_SELECTOR: Final = "modelo"
_SAME_DAYS: Final = "same_days"
_NO_MARGIN: Final = "none"
_BUSINESS_DAYS: Final = "business_days"
_BUSINESS_OR_CALENDAR_DAYS: Final = "business_or_calendar_days"
# ``date.weekday()`` of Saturday; Saturday and Sunday are the weekend the Orden
# names first among the inhábil days.
_SATURDAY: Final = 5
_MAX_DAY_OF_MONTH: Final = 31
# A margin walk longer than this means the calendar holds an impossible run of
# inhábil days, which is a registry defect rather than a cutoff.
_MARGIN_SEARCH_DAYS: Final = 62

_CLAUSE_REQUIRED_KEYS: Final = frozenset({"domiciliation_last_day"})
_CLAUSE_OPTIONAL_KEYS: Final = frozenset({"leap_year_domiciliation_last_day"})
_PROCEDURE_REQUIRED_KEYS: Final = frozenset(
    {"filing_extension", "margin_rule", "inhabil_base", "inhabil_base_authority"},
)
_PROCEDURE_BUSINESS_MARGIN_KEYS: Final = frozenset({"margin_min_business_days", "business_day_territory"})
_PROCEDURE_MARGIN_KEYS: Final = _PROCEDURE_BUSINESS_MARGIN_KEYS | {"margin_min_calendar_days"}


class PaymentCutoffSource(StrEnum):
    """Where a window's payment cutoff comes from."""

    AUTHORED = "authored"
    DERIVED = "derived"
    UNAVAILABLE = "unavailable"


class PaymentCutoffUnavailableReason(StrEnum):
    """Why no payment cutoff could be resolved for a window.

    * ``NO_CLAUSE`` -- no Anexo II clause, or no filing-window clause giving its
      month and nominal close, is declared for the modelo and period.
    * ``NO_PROCEDURE`` -- no art. 3.2 procedure variant covers the Anexo II day.
    * ``HOLIDAY_CALENDAR_UNAVAILABLE`` -- a year the margin walk enters has no
      published holiday calendar in the registry.
    * ``TERRITORY_UNVERIFIED`` -- the procedure's territory is not verified in the
      holiday calendar of a year the walk enters.
    """

    NO_CLAUSE = "no_clause"
    NO_PROCEDURE = "no_procedure"
    HOLIDAY_CALENDAR_UNAVAILABLE = "holiday_calendar_unavailable"
    TERRITORY_UNVERIFIED = "territory_unverified"


class InhabilBasePolicy(StrEnum):
    """What happens to an Anexo II day that falls on an inhábil day.

    * ``KEEP`` -- the day stands, subject only to the margin.
    * ``WEEKEND_TO_LATEST_MARGIN_COMPLIANT_BUSINESS_DAY`` -- a Saturday or Sunday
      is replaced by the latest business day meeting the margin; a holiday
      stands, subject only to the margin.
    * ``LATEST_MARGIN_COMPLIANT_BUSINESS_DAY`` -- any inhábil day is replaced by
      the latest business day meeting the margin.
    """

    KEEP = "keep"
    WEEKEND_TO_LATEST_MARGIN_COMPLIANT_BUSINESS_DAY = "weekend_to_latest_margin_compliant_business_day"
    LATEST_MARGIN_COMPLIANT_BUSINESS_DAY = "latest_margin_compliant_business_day"


class InhabilBaseAuthority(StrEnum):
    """What grounds the inhábil-base policy: the Orden itself or AEAT's published practice."""

    ORDEN_TEXT = "orden_text"
    AEAT_ADMINISTRATIVE_PRACTICE = "aeat_administrative_practice"


class DomiciliationHolidayCoverage(StrEnum):
    """Which holiday layers a derivation consulted.

    * ``NOT_CONSULTED`` -- the governing procedure has no margin, so no calendar
      was read.
    * ``NATIONAL_AND_TERRITORY_MUNICIPAL_UNVERIFIED`` -- weekends, national holidays
      and the verified holidays of the procedure's territory were checked. The
      Orden also names local holidays of the municipality, which have no registry
      source, so that layer stays unverified.
    """

    NOT_CONSULTED = "not_consulted"
    NATIONAL_AND_TERRITORY_MUNICIPAL_UNVERIFIED = "national_and_territory_municipal_unverified"


# ---------------------------------------------------------------------------
# Typed rule parts read from the governed facts.
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class DomiciliationClause:
    """One Anexo II clause: the domiciliación day and the nominal filing close it relates to.

    The deadline month and ``filing_last_day`` are read from the filing-window
    clause, the single home of the nominal close; ``filing_last_day`` of ``None``
    means the last day of the deadline month.
    """

    deadline_month_offset: int
    filing_last_day: int | None
    domiciliation_last_day: int
    leap_year_domiciliation_last_day: int | None = None

    def _deadline_month(self, period_end: date) -> tuple[int, int]:
        month_index = period_end.year * 12 + (period_end.month - 1) + self.deadline_month_offset
        return month_index // 12, month_index % 12 + 1

    def nominal_close(self, period_end: date) -> date:
        """Return the nominal last filing day before any extension for an inhábil day."""
        year, month = self._deadline_month(period_end)
        last = calendar.monthrange(year, month)[1]
        day = last if self.filing_last_day is None else self.filing_last_day
        if day > last:
            raise DeadlineValidationError(f"domiciliation clause filing day {day} does not exist in {year}-{month:02d}")
        return date(year, month, day)

    def anexo_day(self, period_end: date) -> date:
        """Return the Anexo II domiciliación day, using the leap-year day where the clause names one."""
        year, month = self._deadline_month(period_end)
        day = self.domiciliation_last_day
        if self.leap_year_domiciliation_last_day is not None and calendar.isleap(year):
            day = self.leap_year_domiciliation_last_day
        if day > calendar.monthrange(year, month)[1]:
            raise DeadlineValidationError(
                f"domiciliation clause day {day} does not exist in {year}-{month:02d}",
            )
        return date(year, month, day)


@dataclass(frozen=True, slots=True)
class DomiciliationMargin:
    """The minimum between the domiciliación end and the voluntary close.

    ``min_business_days`` counts the business days after the domiciliación end
    up to and including the close. ``min_calendar_days``, where declared, is an
    alternative met by that many natural days strictly between the two ends;
    ``None`` means the business-day count alone decides.
    """

    min_business_days: int
    min_calendar_days: int | None
    territory: str


@dataclass(frozen=True, slots=True)
class DomiciliationProcedure:
    """The art. 3.2 procedure in force on an Anexo II day."""

    margin: DomiciliationMargin | None
    inhabil_base: InhabilBasePolicy
    inhabil_base_authority: InhabilBaseAuthority


@dataclass(frozen=True, slots=True)
class DomiciliationCutoffArithmetic:
    """The intermediate dates of one derivation, retained as provenance."""

    cutoff_on: date
    anexo_on: date
    base_on: date
    extension_days: int
    margin_cap_on: date | None


def _subject(fact_id: str, variant_id: str) -> str:
    return f"governed fact {fact_id!r} variant {variant_id!r}"


def _entries(resolved: ResolvedMappingFact) -> dict[str, object]:
    entries: dict[str, object] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str):
            raise RegistryValidationError(f"{_subject(resolved.fact_id, resolved.variant_id)} has a non-text key")
        entries[entry.key] = entry.value
    return entries


def _require_keys(
    entries: Mapping[str, object], *, required: frozenset[str], allowed: frozenset[str], subject: str
) -> None:
    missing = required - entries.keys()
    unknown = entries.keys() - allowed
    if missing or unknown:
        raise RegistryValidationError(
            f"{subject} entries must declare {sorted(required)!r}; "
            f"missing {sorted(missing)!r}, unknown {sorted(unknown)!r}",
        )


def _integer(entries: Mapping[str, object], key: str, *, minimum: int, maximum: int, subject: str) -> int:
    value = entries[key]
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RegistryValidationError(f"{subject} {key!r} must be a whole number from {minimum} to {maximum}")
    return value


def _token(entries: Mapping[str, object], key: str, *, allowed: frozenset[str], subject: str) -> str:
    value = entries[key]
    if not isinstance(value, str) or value not in allowed:
        raise RegistryValidationError(f"{subject} {key!r} must be one of {sorted(allowed)!r}")
    return value


def domiciliation_clause_from_fact(
    resolved: ResolvedMappingFact,
    *,
    window_clause: FilingWindowClause,
) -> DomiciliationClause:
    """Read one resolved Anexo II clause onto its filing-window clause, refusing unknown keys and days."""
    subject = _subject(resolved.fact_id, resolved.variant_id)
    entries = _entries(resolved)
    _require_keys(
        entries,
        required=_CLAUSE_REQUIRED_KEYS,
        allowed=_CLAUSE_REQUIRED_KEYS | _CLAUSE_OPTIONAL_KEYS,
        subject=subject,
    )
    leap_day = (
        _integer(entries, "leap_year_domiciliation_last_day", minimum=1, maximum=_MAX_DAY_OF_MONTH, subject=subject)
        if "leap_year_domiciliation_last_day" in entries
        else None
    )
    return DomiciliationClause(
        deadline_month_offset=window_clause.deadline_month_offset,
        filing_last_day=window_clause.filing_last_day,
        domiciliation_last_day=_integer(
            entries, "domiciliation_last_day", minimum=1, maximum=_MAX_DAY_OF_MONTH, subject=subject
        ),
        leap_year_domiciliation_last_day=leap_day,
    )


def domiciliation_procedure_from_fact(resolved: ResolvedMappingFact) -> DomiciliationProcedure:
    """Read one resolved art. 3.2 procedure, refusing unknown keys and incoherent policies."""
    subject = _subject(resolved.fact_id, resolved.variant_id)
    entries = _entries(resolved)
    margin_rule = entries.get("margin_rule")
    required = _PROCEDURE_REQUIRED_KEYS
    if margin_rule == _BUSINESS_DAYS:
        required = _PROCEDURE_REQUIRED_KEYS | _PROCEDURE_BUSINESS_MARGIN_KEYS
    elif margin_rule == _BUSINESS_OR_CALENDAR_DAYS:
        required = _PROCEDURE_REQUIRED_KEYS | _PROCEDURE_MARGIN_KEYS
    _require_keys(entries, required=required, allowed=required, subject=subject)
    _token(entries, "filing_extension", allowed=frozenset({_SAME_DAYS}), subject=subject)
    _token(
        entries,
        "margin_rule",
        allowed=frozenset({_NO_MARGIN, _BUSINESS_DAYS, _BUSINESS_OR_CALENDAR_DAYS}),
        subject=subject,
    )
    inhabil_base = InhabilBasePolicy(
        _token(entries, "inhabil_base", allowed=frozenset(InhabilBasePolicy), subject=subject),
    )
    authority = InhabilBaseAuthority(
        _token(entries, "inhabil_base_authority", allowed=frozenset(InhabilBaseAuthority), subject=subject),
    )
    margin = None
    if margin_rule in {_BUSINESS_DAYS, _BUSINESS_OR_CALENDAR_DAYS}:
        territory = entries["business_day_territory"]
        if not isinstance(territory, str) or not territory.strip():
            raise RegistryValidationError(f"{subject} 'business_day_territory' must be a territory code")
        margin = DomiciliationMargin(
            min_business_days=_integer(entries, "margin_min_business_days", minimum=1, maximum=31, subject=subject),
            min_calendar_days=(
                _integer(entries, "margin_min_calendar_days", minimum=1, maximum=31, subject=subject)
                if margin_rule == _BUSINESS_OR_CALENDAR_DAYS
                else None
            ),
            territory=territory.strip(),
        )
    if margin is None and inhabil_base is not InhabilBasePolicy.KEEP:
        raise RegistryValidationError(f"{subject} moves an inhábil Anexo II day without a margin to move it to")
    return DomiciliationProcedure(margin=margin, inhabil_base=inhabil_base, inhabil_base_authority=authority)


# ---------------------------------------------------------------------------
# Pure arithmetic.
# ---------------------------------------------------------------------------


def _margin_met(
    candidate: date,
    closes_on: date,
    margin: DomiciliationMargin,
    business_day: Callable[[date], bool],
) -> bool:
    """Whether a domiciliación ending on ``candidate`` leaves the margin before ``closes_on``.

    Business days are counted after the candidate up to and including the
    voluntary close: AEAT publishes Tuesday 17 February 2026 before a Friday
    20 February close (1M 26). Natural days are counted strictly between the two
    ends: Wednesday 16 April 2025 before a Monday 21 April close leaves four, so
    AEAT publishes Tuesday 15 April (1T 25), which leaves five natural days
    although only two business days follow it.
    """
    if margin.min_calendar_days is not None and (closes_on - candidate).days - 1 >= margin.min_calendar_days:
        return True
    business_days_after = 0
    for offset in range(1, (closes_on - candidate).days + 1):
        if business_day(candidate + timedelta(days=offset)):
            business_days_after += 1
            if business_days_after >= margin.min_business_days:
                return True
    return False


def _margin_cap(closes_on: date, margin: DomiciliationMargin, business_day: Callable[[date], bool]) -> date:
    """Return the latest business day before ``closes_on`` that leaves the margin."""
    candidate = closes_on
    for _ in range(_MARGIN_SEARCH_DAYS):
        candidate -= timedelta(days=1)
        if business_day(candidate) and _margin_met(candidate, closes_on, margin, business_day):
            return candidate
    raise DeadlineValidationError(
        f"no business day leaves the domiciliation margin within {_MARGIN_SEARCH_DAYS} days of {closes_on.isoformat()}",
    )


def _replaces_base(policy: InhabilBasePolicy, base_on: date, business_day: Callable[[date], bool]) -> bool:
    """Whether the inhábil-base policy replaces this Anexo II day by the margin cap."""
    if policy is InhabilBasePolicy.WEEKEND_TO_LATEST_MARGIN_COMPLIANT_BUSINESS_DAY:
        return base_on.weekday() >= _SATURDAY
    if policy is InhabilBasePolicy.LATEST_MARGIN_COMPLIANT_BUSINESS_DAY:
        return not business_day(base_on)
    return False


def derive_domiciliation_cutoff(
    *,
    clause: DomiciliationClause,
    procedure: DomiciliationProcedure,
    period_end: date,
    closes_on: date,
    business_day: Callable[[date], bool],
) -> DomiciliationCutoffArithmetic:
    """Apply the Anexo II clause and the art. 3.2 procedure to one window's dates.

    ``closes_on`` is the window's voluntary close, already extended for an inhábil
    last day; its distance from the clause's nominal close is the art. 3.2.b
    extension. ``business_day`` is consulted only when the procedure has a margin.

    Raises:
        DeadlineValidationError: When the window closes before the nominal close,
            or the derived cutoff would fall after the window closes.
    """
    nominal_close = clause.nominal_close(period_end)
    extension_days = (closes_on - nominal_close).days
    if extension_days < 0:
        raise DeadlineValidationError(
            f"window closes on {closes_on.isoformat()}, before the nominal filing close {nominal_close.isoformat()}",
        )
    anexo_on = clause.anexo_day(period_end)
    base_on = anexo_on + timedelta(days=extension_days)
    margin_cap_on: date | None = None
    if procedure.margin is None:
        cutoff_on = base_on
    else:
        margin_cap_on = _margin_cap(closes_on, procedure.margin, business_day)
        if _replaces_base(procedure.inhabil_base, base_on, business_day) or not _margin_met(
            base_on, closes_on, procedure.margin, business_day
        ):
            cutoff_on = margin_cap_on
        else:
            cutoff_on = base_on
    if cutoff_on > closes_on:
        raise DeadlineValidationError(
            f"derived payment cutoff {cutoff_on.isoformat()} falls after the window close {closes_on.isoformat()}",
        )
    return DomiciliationCutoffArithmetic(
        cutoff_on=cutoff_on,
        anexo_on=anexo_on,
        base_on=base_on,
        extension_days=extension_days,
        margin_cap_on=margin_cap_on,
    )


# ---------------------------------------------------------------------------
# Provenance-bearing resolution.
# ---------------------------------------------------------------------------


class AuthoredPaymentCutoff(BaseModel):
    """A cutoff the window authors; it wins over the rule."""

    model_config = STRICT_FROZEN_CONFIG

    source: Literal[PaymentCutoffSource.AUTHORED] = PaymentCutoffSource.AUTHORED
    cutoff_on: date
    window_id: str = Field(min_length=1)
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class DerivedPaymentCutoff(BaseModel):
    """A cutoff derived from the governed domiciliación rule, with its full provenance."""

    model_config = STRICT_FROZEN_CONFIG

    source: Literal[PaymentCutoffSource.DERIVED] = PaymentCutoffSource.DERIVED
    cutoff_on: date
    window_id: str = Field(min_length=1)
    anexo_on: date
    base_on: date
    extension_days: int = Field(ge=0)
    margin_cap_on: date | None = None
    clause: FilingWindowRuleEvidence
    procedure: FilingWindowRuleEvidence
    inhabil_base_authority: InhabilBaseAuthority
    holiday_coverage: DomiciliationHolidayCoverage

    @property
    def legal_refs(self) -> tuple[str, ...]:
        """Every legal reference of both rule parts, in order and without repetition."""
        return tuple(dict.fromkeys((*self.clause.legal_refs, *self.procedure.legal_refs)))

    @property
    def source_refs(self) -> tuple[str, ...]:
        """Every source reference of both rule parts, in order and without repetition."""
        return tuple(dict.fromkeys((*self.clause.source_refs, *self.procedure.source_refs)))


class UnavailablePaymentCutoff(BaseModel):
    """No cutoff is known for the window; it is unknown, never open."""

    model_config = STRICT_FROZEN_CONFIG

    source: Literal[PaymentCutoffSource.UNAVAILABLE] = PaymentCutoffSource.UNAVAILABLE
    window_id: str = Field(min_length=1)
    reason: PaymentCutoffUnavailableReason
    clause: FilingWindowRuleEvidence | None = None
    procedure: FilingWindowRuleEvidence | None = None

    @property
    def cutoff_on(self) -> None:
        """An unavailable cutoff has no date."""
        return None


class CalendarGapError(CadrumoError):
    """A year the derivation walks cannot classify its days."""

    def __init__(self, reason: PaymentCutoffUnavailableReason) -> None:
        super().__init__(reason.value)
        self.reason = reason


def _territory_business_day(
    margin: DomiciliationMargin,
    *,
    anexo_on: date,
    calendars: tuple[HolidayCalendar, ...],
    operation: PinnedAuthorityOperation,
) -> Callable[[date], bool]:
    territory: CalendarCCAA = resolve_calendar_ccaa_catalogue(effective_date=anexo_on, authority=operation).require(
        margin.territory,
    )
    supplied: dict[int, HolidayCalendar] = {}
    for holiday_calendar in calendars:
        if holiday_calendar.year in supplied:
            raise DeadlineValidationError(f"more than one holiday calendar was supplied for {holiday_calendar.year}")
        supplied[holiday_calendar.year] = holiday_calendar

    def calendar_for(year: int) -> HolidayCalendar:
        cached = supplied.get(year)
        if cached is not None:
            return cached
        try:
            loaded = load_holiday_calendar(year, operation=operation)
        except DeadlineValidationError as exc:
            raise CalendarGapError(PaymentCutoffUnavailableReason.HOLIDAY_CALENDAR_UNAVAILABLE) from exc
        supplied[year] = loaded
        return loaded

    def business_day(candidate: date) -> bool:
        holiday_calendar = calendar_for(candidate.year)
        if territory not in holiday_calendar.verified_territories:
            raise CalendarGapError(PaymentCutoffUnavailableReason.TERRITORY_UNVERIFIED)
        return is_business_day(candidate, calendar=holiday_calendar, ccaa_code=territory)

    return business_day


def _calendar_not_consulted(candidate: date) -> bool:
    raise DeadlineValidationError(f"a procedure without a margin consulted the calendar for {candidate.isoformat()}")


def derive_payment_cutoff(
    modelo: str,
    window: DeadlineWindowDefinition,
    *,
    operation: PinnedAuthorityOperation,
    calendars: tuple[HolidayCalendar, ...] = (),
) -> DerivedPaymentCutoff | UnavailablePaymentCutoff:
    """Derive a window's cutoff from the governed rule, ignoring any authored date.

    ``calendars`` supplies holiday calendars ahead of the authority, year by
    year, exactly as :func:`~cadrumo.domain.deadlines.festivos.shift_deadline`
    accepts them. A year neither supplied nor published makes the cutoff
    unavailable; it is never derived against a holiday-free calendar.
    """
    period = window.period
    if not period.has_date_span():
        # Anexo II periods are counted from the end of a dated period; an event
        # filing has none, so no clause can govern it.
        return UnavailablePaymentCutoff(window_id=window.id, reason=PaymentCutoffUnavailableReason.NO_CLAUSE)
    period_end = period.end_date
    window_clause = resolve_filing_window_clause(operation, modelo=modelo, period=period)
    if window_clause is None:
        return UnavailablePaymentCutoff(window_id=window.id, reason=PaymentCutoffUnavailableReason.NO_CLAUSE)
    clause_fact = resolve_mapping_fact(
        operation,
        MappingFactQuery(
            fact_id=DOMICILIATION_CUTOFF_CLAUSE_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=period_end,
            selectors=(FactSelector(name=_MODELO_SELECTOR, value=modelo),),
            filing_year=window.filing_year,
            period=period.registry_token,
        ),
    )
    if clause_fact is None:
        return UnavailablePaymentCutoff(window_id=window.id, reason=PaymentCutoffUnavailableReason.NO_CLAUSE)
    clause = domiciliation_clause_from_fact(clause_fact, window_clause=window_clause[0])
    clause_evidence = FilingWindowRuleEvidence.from_fact(clause_fact)
    anexo_on = clause.anexo_day(period_end)
    procedure_fact = resolve_mapping_fact(
        operation,
        MappingFactQuery(
            fact_id=DOMICILIATION_PROCEDURE_FACT_ID,
            date_axis=DateAxis.SUBMISSION_DATE,
            effective_date=anexo_on,
        ),
    )
    if procedure_fact is None:
        return UnavailablePaymentCutoff(
            window_id=window.id,
            reason=PaymentCutoffUnavailableReason.NO_PROCEDURE,
            clause=clause_evidence,
        )
    procedure = domiciliation_procedure_from_fact(procedure_fact)
    procedure_evidence = FilingWindowRuleEvidence.from_fact(procedure_fact)
    business_day: Callable[[date], bool] = _calendar_not_consulted
    coverage = DomiciliationHolidayCoverage.NOT_CONSULTED
    if procedure.margin is not None:
        coverage = DomiciliationHolidayCoverage.NATIONAL_AND_TERRITORY_MUNICIPAL_UNVERIFIED
        business_day = _territory_business_day(
            procedure.margin,
            anexo_on=anexo_on,
            calendars=calendars,
            operation=operation,
        )
    try:
        arithmetic = derive_domiciliation_cutoff(
            clause=clause,
            procedure=procedure,
            period_end=period_end,
            closes_on=window.closes_on,
            business_day=business_day,
        )
    except CalendarGapError as gap:
        return UnavailablePaymentCutoff(
            window_id=window.id,
            reason=gap.reason,
            clause=clause_evidence,
            procedure=procedure_evidence,
        )
    return DerivedPaymentCutoff(
        cutoff_on=arithmetic.cutoff_on,
        window_id=window.id,
        anexo_on=arithmetic.anexo_on,
        base_on=arithmetic.base_on,
        extension_days=arithmetic.extension_days,
        margin_cap_on=arithmetic.margin_cap_on,
        clause=clause_evidence,
        procedure=procedure_evidence,
        inhabil_base_authority=procedure.inhabil_base_authority,
        holiday_coverage=coverage,
    )


def resolve_payment_cutoff(
    modelo: str,
    window: DeadlineWindowDefinition,
    *,
    operation: PinnedAuthorityOperation,
    calendars: tuple[HolidayCalendar, ...] = (),
) -> AuthoredPaymentCutoff | DerivedPaymentCutoff | UnavailablePaymentCutoff:
    """Resolve the domiciliación cutoff of one matched window.

    An authored ``payment_cutoff_on`` wins and need not agree with the rule;
    otherwise the cutoff is derived by :func:`derive_payment_cutoff`. Every
    consumer reads the cutoff here instead of the window's literal field.
    """
    if window.payment_cutoff_on is not None:
        return AuthoredPaymentCutoff(
            cutoff_on=window.payment_cutoff_on,
            window_id=window.id,
            legal_refs=tuple(window.legal_refs),
            source_refs=tuple(window.source_refs),
        )
    return derive_payment_cutoff(modelo, window, operation=operation, calendars=calendars)


__all__ = (
    "DOMICILIATION_CUTOFF_CLAUSE_FACT_ID",
    "DOMICILIATION_PROCEDURE_FACT_ID",
    "AuthoredPaymentCutoff",
    "DerivedPaymentCutoff",
    "DomiciliationClause",
    "DomiciliationCutoffArithmetic",
    "DomiciliationHolidayCoverage",
    "DomiciliationMargin",
    "DomiciliationProcedure",
    "InhabilBaseAuthority",
    "InhabilBasePolicy",
    "PaymentCutoffSource",
    "PaymentCutoffUnavailableReason",
    "UnavailablePaymentCutoff",
    "derive_domiciliation_cutoff",
    "derive_payment_cutoff",
    "domiciliation_clause_from_fact",
    "domiciliation_procedure_from_fact",
    "resolve_payment_cutoff",
)
