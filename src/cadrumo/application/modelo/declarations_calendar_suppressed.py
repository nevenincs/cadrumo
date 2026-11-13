"""Obligations the calendar positively holds off its schedule, served with their verdict and words.

The legal calendar decides each scheduled obligation's applicability from the
taxpayer model. Only a positively applicable one earns a calendar entry; the
others are held back as suppressed rows that keep the verdict the calendar
reached and the reason it gave. This module projects the positively excluded
rows for a frontend as a separate list, so the entries stay exactly the
obligations that are owed.

Two verdicts are served: ``NOT_APPLICABLE`` and ``ATTRIBUTION_PASS_THROUGH`` say
the taxpayer's declared model files something else, or nothing of its own, for
the obligation. ``INCOMPLETE`` is not served: it says the calendar could not
decide, which is not a statement that nothing is owed, and the calendar's
coverage report already names those obligations as undetermined. The sentence
for each served verdict is worded here, in the worker's language, so a frontend
never words a tax meaning of its own.
"""

from __future__ import annotations

from datetime import date
from typing import Self

from pydantic import BaseModel, Field, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.external_constants import OutputLanguage
from ...core.filing_year import FilingYear
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.applicability_models import ApplicabilityVerdict
from ...domain.modelos.codes import ModeloCode
from ..operations.error_detail import MAX_OPERATION_ERROR_WORDS_LENGTH, served_words_language
from ..overview.calendar_models import SuppressedCalendarEntry
from ..overview.suppressed_verdict_words import EXCLUDING_VERDICTS, suppressed_verdict_words

__all__ = [
    "DeclarationsCalendarSuppressedEntryV1",
    "project_suppressed_calendar_entries",
]


class DeclarationsCalendarSuppressedEntryV1(BaseModel):
    """One scheduled obligation the calendar held back, with the verdict that held it back."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    opens_on: date
    closes_on: date
    adjusted_closes_on: date
    verdict: ApplicabilityVerdict
    """The calendar's own verdict: ``NOT_APPLICABLE`` or ``ATTRIBUTION_PASS_THROUGH``."""
    verdict_words: str = Field(min_length=1, max_length=MAX_OPERATION_ERROR_WORDS_LENGTH)
    """What the verdict means for the taxpayer, in words."""
    verdict_words_language: OutputLanguage
    reason: str = Field(min_length=1)
    """The reason the calendar gave, in the registry's own wording; no language is claimed for it."""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _is_a_held_back_obligation(self) -> Self:
        if self.verdict not in EXCLUDING_VERDICTS:
            raise ValueError(
                "a suppressed calendar entry carries a verdict that does not positively exclude the obligation"
            )
        if self.period.filing_year != self.filing_year:
            raise ValueError("suppressed calendar address year and period disagree")
        if self.opens_on > self.adjusted_closes_on or self.closes_on > self.adjusted_closes_on:
            raise ValueError("a suppressed obligation's window closes before it opens")
        return self

    def semantic_key(self) -> tuple[str, int, str]:
        """Return the public natural obligation identity."""
        return (str(self.modelo), self.filing_year, self.period.registry_token)


def project_suppressed_calendar_entries(
    entries: tuple[SuppressedCalendarEntry, ...],
) -> tuple[DeclarationsCalendarSuppressedEntryV1, ...]:
    """Serve the calendar's positively excluded rows in the worker's language, ordered by their close.

    A row whose verdict is ``INCOMPLETE`` is left out: the calendar could not
    decide it, so it is neither owed nor excluded.
    """
    language = served_words_language()
    rows = [
        DeclarationsCalendarSuppressedEntryV1(
            modelo=ModeloCode(entry.modelo),
            filing_year=entry.period.filing_year,
            period=entry.period,
            opens_on=entry.opens_on,
            closes_on=entry.closes_on,
            adjusted_closes_on=entry.adjusted_closes_on,
            verdict=entry.verdict,
            verdict_words=suppressed_verdict_words(entry.verdict, language),
            verdict_words_language=language,
            reason=entry.reason,
        )
        for entry in entries
        if entry.verdict in EXCLUDING_VERDICTS
    ]
    rows.sort(key=lambda row: (row.adjusted_closes_on, *row.semantic_key()))
    return tuple(rows)
