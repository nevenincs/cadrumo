"""The filing periods a ledger window selects among, served so a frontend does no period arithmetic.

:class:`~cadrumo.core.period.Period` is the one owner of what a period is: its
code, its cadence, its first and last day, its neighbours and the period a day
falls in. This module only presents that model: the periods of one year with
their dates, their neighbours across year ends and their names in the language
asked for; the periods that hold a reference day (today unless one is given); the
shortest period that holds a span of days; and the periods that hold each of a few
days a frontend is about to bucket.

A quarter is named by its own token, which no language translates; a month and the
whole year are named by the catalogue, so the words are the application's and a
frontend shows them as served. The periods listed are the calendar ones. An
instalment clave or a scheme period is a filing event, not a span of days, and a
ledger cannot be filtered by it.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from types import MappingProxyType
from typing import Annotated, Final, Literal

from pydantic import AfterValidator, BaseModel, Field, model_validator

from ...core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OutputLanguage
from ...core.filing_year import FourDigitYear, is_four_digit_year
from ...core.i18n.render import tr
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.period import CALENDAR_PERIOD_KINDS, Period, PeriodKind, StandardPeriodCode
from ...core.time.clock import today_madrid
from ..operations.public_period import PublicPeriod

MAX_PERIOD_LOOKUP_DAYS: Final = 64
"""The most days one request may ask the periods of."""

MAX_PERIOD_WORDS_LENGTH: Final = 64
"""The longest name or label of a period."""

type LedgerPeriodKind = Literal["annual", "quarterly", "monthly"]

_KIND_TOKENS: Final[Mapping[PeriodKind, LedgerPeriodKind]] = MappingProxyType(
    {
        PeriodKind.ANNUAL: "annual",
        PeriodKind.QUARTERLY: "quarterly",
        PeriodKind.MONTHLY: "monthly",
    }
)
"""The served token of each calendar cadence; the cadence owner's own spelling."""

_ANNUAL_NAME_LOCALE_KEY: Final = "application.ledger.periods.served.annual"
_LABEL_LOCALE_KEY: Final = "application.ledger.periods.served.label"
_MONTH_NAME_LOCALE_KEYS: Final[tuple[str, ...]] = (
    "application.ledger.periods.served.january",
    "application.ledger.periods.served.february",
    "application.ledger.periods.served.march",
    "application.ledger.periods.served.april",
    "application.ledger.periods.served.may",
    "application.ledger.periods.served.june",
    "application.ledger.periods.served.july",
    "application.ledger.periods.served.august",
    "application.ledger.periods.served.september",
    "application.ledger.periods.served.october",
    "application.ledger.periods.served.november",
    "application.ledger.periods.served.december",
)
"""The words of the twelve months, in calendar order."""


def _written_year(day: date) -> date:
    """Refuse a day in a year no period can be named for."""
    if not is_four_digit_year(day.year):
        raise ValueError("a day's year must be written with four digits")
    return day


type PeriodDay = Annotated[date, AfterValidator(_written_year)]
"""A day whose year is written with four digits, the years a period can be named for."""


class LedgerPeriodSpanRequest(BaseModel):
    """Two days, the first and the last of a span to find the shortest holding period of."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    first_day: PeriodDay
    last_day: PeriodDay

    @model_validator(mode="after")
    def _ordered(self) -> LedgerPeriodSpanRequest:
        if self.last_day < self.first_day:
            raise ValueError("the span ends before it begins")
        return self


class LedgerPeriodsQuery(BaseModel):
    """What period facts a read asks for, apart from the language its words are said in."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    year: FourDigitYear | None = None
    covering: LedgerPeriodSpanRequest | None = None
    days: tuple[PeriodDay, ...] = Field(default=(), max_length=MAX_PERIOD_LOOKUP_DAYS)


class LedgerPeriodProjection(BaseModel):
    """One selectable period: its code, cadence, days, neighbours and words.

    ``name_words`` is the period on its own (the year, a quarter token, a month);
    ``label_words`` is it with its year, as a heading or a chosen value writes it.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    period: PublicPeriod
    kind: LedgerPeriodKind
    first_day: date
    last_day: date
    previous: PublicPeriod | None
    next: PublicPeriod | None
    name_words: str = Field(min_length=1, max_length=MAX_PERIOD_WORDS_LENGTH)
    name_words_language: OutputLanguage
    label_words: str = Field(min_length=1, max_length=MAX_PERIOD_WORDS_LENGTH)
    label_words_language: OutputLanguage


class LedgerDayPeriodsProjection(BaseModel):
    """The year, the quarter and the month that hold one day."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    day: date
    annual: PublicPeriod
    quarterly: PublicPeriod
    monthly: PublicPeriod


class LedgerPeriodCoveringProjection(BaseModel):
    """The shortest period that holds a span, or none where the span crosses a year end."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    first_day: date
    last_day: date
    period: PublicPeriod | None


class LedgerPeriodsProjection(BaseModel):
    """The periods of one year, the periods of the reference day, and what else was asked."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    year: FourDigitYear
    annual_code: str = Field(min_length=1, max_length=MAX_PERIOD_WORDS_LENGTH)
    periods: tuple[LedgerPeriodProjection, ...]
    containing: LedgerDayPeriodsProjection
    covering: LedgerPeriodCoveringProjection | None = None
    days: tuple[LedgerDayPeriodsProjection, ...] = ()


def _name_words(period: Period, language: OutputLanguage) -> str:
    match period.kind:
        case PeriodKind.ANNUAL:
            return tr(_ANNUAL_NAME_LOCALE_KEY, locale=language.value)
        case PeriodKind.MONTHLY:
            return tr(_MONTH_NAME_LOCALE_KEYS[int(period.code) - 1], locale=language.value)
        case _:
            return period.code


def _label_words(period: Period, name: str, language: OutputLanguage) -> str:
    if period.kind is PeriodKind.ANNUAL:
        return str(period.filing_year)
    return tr(_LABEL_LOCALE_KEY, locale=language.value, year=period.filing_year, name=name)


def _public(period: Period | None) -> PublicPeriod | None:
    return None if period is None else PublicPeriod.from_period(period)


def _required_public(period: Period) -> PublicPeriod:
    return PublicPeriod.from_period(period)


def _period_projection(period: Period, language: OutputLanguage) -> LedgerPeriodProjection:
    name = _name_words(period, language)
    return LedgerPeriodProjection(
        period=_required_public(period),
        kind=_KIND_TOKENS[period.kind],
        first_day=period.start_date,
        last_day=period.end_date,
        previous=_public(period.shifted(-1)),
        next=_public(period.shifted(1)),
        name_words=name,
        name_words_language=language,
        label_words=_label_words(period, name, language),
        label_words_language=language,
    )


def _day_periods(day: date) -> LedgerDayPeriodsProjection:
    return LedgerDayPeriodsProjection(
        day=day,
        annual=_required_public(Period.containing(day, PeriodKind.ANNUAL)),
        quarterly=_required_public(Period.containing(day, PeriodKind.QUARTERLY)),
        monthly=_required_public(Period.containing(day, PeriodKind.MONTHLY)),
    )


def ledger_periods(
    query: LedgerPeriodsQuery,
    *,
    reference_day: date | None = None,
    language: OutputLanguage = DEFAULT_OUTPUT_LANGUAGE,
) -> LedgerPeriodsProjection:
    """Serve the periods of ``query.year`` and what else ``query`` asks for.

    The year listed is the asked one, else the year of the reference day, which is
    today in Spain when none is given.

    Raises:
        PeriodError: When the reference day falls in a year no period can be named for.
    """
    day = today_madrid() if reference_day is None else reference_day
    year = day.year if query.year is None else query.year
    covering = (
        None
        if query.covering is None
        else LedgerPeriodCoveringProjection(
            first_day=query.covering.first_day,
            last_day=query.covering.last_day,
            period=_public(Period.covering(query.covering.first_day, query.covering.last_day)),
        )
    )
    return LedgerPeriodsProjection(
        year=year,
        annual_code=StandardPeriodCode.ANNUAL.value,
        periods=tuple(_period_projection(period, language) for period in Period.calendar_periods(year)),
        containing=_day_periods(day),
        covering=covering,
        days=tuple(_day_periods(each) for each in query.days),
    )


def _require_total_tables() -> None:
    if set(_KIND_TOKENS) != set(CALENDAR_PERIOD_KINDS):
        raise ValueError("every calendar cadence needs its served token")
    if len(_MONTH_NAME_LOCALE_KEYS) != len(set(_MONTH_NAME_LOCALE_KEYS)):
        raise ValueError("every month needs its own word")


_require_total_tables()

__all__ = [
    "MAX_PERIOD_LOOKUP_DAYS",
    "MAX_PERIOD_WORDS_LENGTH",
    "LedgerDayPeriodsProjection",
    "LedgerPeriodCoveringProjection",
    "LedgerPeriodKind",
    "LedgerPeriodProjection",
    "LedgerPeriodSpanRequest",
    "LedgerPeriodsProjection",
    "LedgerPeriodsQuery",
    "PeriodDay",
    "ledger_periods",
]
