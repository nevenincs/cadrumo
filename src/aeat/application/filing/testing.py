"""Public fixture helpers for :mod:`aeat.application.filing`.

This module exposes profile/deadline helpers and draft construction helpers so
tests can exercise application filing workflows without reaching into private
builder internals. It deliberately does not expose modelo-specific casilla
schemas or formulas.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from ...core.errors import FilingFixtureError, FixtureProvisioningError
from ._testing_loader import SYNTHETIC_FIXTURES_ROOT, load_filing_history
from ._testing_schema import (
    FilingRecord,
    FilingRecordPeriodKind,
    FilingRecordScenario,
    FixtureCasilla,
    FixtureScalar,
    compute_record_id,
)
from ._testing_synthesize import (
    synthesize_filing_draft,
    synthesize_filing_draft_from_decimals,
)


class SyntheticProfile(BaseModel):
    """A frozen :class:`aeat.application.filing.FilingProfile`-conforming record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    tax_id: str
    display_name: str
    applicable_modelos: tuple[str, ...]


class SyntheticDeadlineStatus(BaseModel):
    """A frozen :class:`aeat.application.filing.DeadlineStatus`-conforming record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    due_date: date
    is_overdue: bool


class SyntheticDeadlineChecker(BaseModel):
    """A frozen :class:`aeat.application.filing.DeadlineChecker`-conforming record.

    The checker returns the same :class:`SyntheticDeadlineStatus`
    for every ``(modelo, period)`` query, which keeps tests
    deterministic.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    status: SyntheticDeadlineStatus

    def check(self, modelo: str, period: str) -> SyntheticDeadlineStatus:
        """Return the configured :class:`SyntheticDeadlineStatus`."""
        del modelo, period
        return self.status


__all__ = [
    "SYNTHETIC_FIXTURES_ROOT",
    "FilingFixtureError",
    "FilingRecord",
    "FilingRecordPeriodKind",
    "FilingRecordScenario",
    "FixtureCasilla",
    "FixtureProvisioningError",
    "FixtureScalar",
    "SyntheticDeadlineChecker",
    "SyntheticDeadlineStatus",
    "SyntheticProfile",
    "compute_record_id",
    "load_filing_history",
    "synthesize_filing_draft",
    "synthesize_filing_draft_from_decimals",
]
