"""Public fixture helpers for :mod:`aeat.application.filing`.

This module exposes profile/deadline helpers and draft construction helpers so
tests can exercise application filing workflows without reaching into private
builder internals. It deliberately does not expose modelo-specific casilla
schemas or formulas.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict

from ...core.errors import FixtureProvisioningError
from ._testing_registry import build_registry_filing_draft, build_registry_filing_draft_from_decimals


class FilingTestProfile(BaseModel):
    """A frozen :class:`aeat.application.filing.ModeloProfile`-conforming record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    tax_id: str
    display_name: str


class FilingTestDeadlineStatus(BaseModel):
    """A frozen :class:`aeat.application.filing.DeadlineStatus`-conforming record."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    due_date: date
    is_overdue: bool


class FilingTestDeadlineChecker(BaseModel):
    """A frozen :class:`aeat.application.filing.DeadlineChecker`-conforming record.

    The checker returns the same :class:`FilingTestDeadlineStatus`
    for every ``(modelo, period)`` query, which keeps tests
    deterministic.
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    status: FilingTestDeadlineStatus

    def check(self, modelo: str, period: str) -> FilingTestDeadlineStatus:
        """Return the configured :class:`FilingTestDeadlineStatus`."""
        del modelo, period
        return self.status


__all__ = [
    "FilingTestDeadlineChecker",
    "FilingTestDeadlineStatus",
    "FilingTestProfile",
    "FixtureProvisioningError",
    "build_registry_filing_draft",
    "build_registry_filing_draft_from_decimals",
]
