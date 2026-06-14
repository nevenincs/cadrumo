"""Public fixture helpers for :mod:`aeat.application.filing`.

This module exposes profile/deadline helpers and draft construction helpers so
tests can exercise application filing workflows without reaching into private
builder internals. It deliberately does not expose modelo-specific casilla
schemas or formulas.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG, Period
from ...core.errors import FixtureProvisioningError
from ._testing_registry import build_registry_filing_draft, build_registry_filing_draft_from_decimals


class ModeloTestProfile(BaseModel):
    """A frozen :class:`aeat.application.filing.ModeloProfile`-conforming record."""

    model_config = STRICT_FROZEN_CONFIG

    tax_id: str
    display_name: str


class ModeloTestDeadlineStatus(BaseModel):
    """A frozen :class:`aeat.application.filing.DeadlineStatus`-conforming record."""

    model_config = STRICT_FROZEN_CONFIG

    due_date: date
    is_overdue: bool


class ModeloTestDeadlineChecker(BaseModel):
    """A frozen :class:`aeat.application.filing.DeadlineChecker`-conforming record.

    The checker returns the same :class:`ModeloTestDeadlineStatus`
    for every ``(modelo, period)`` query, which keeps tests
    deterministic.
    """

    model_config = STRICT_FROZEN_CONFIG

    status: ModeloTestDeadlineStatus

    def check(self, modelo: str, period: Period) -> ModeloTestDeadlineStatus:
        """Return the configured :class:`ModeloTestDeadlineStatus`."""
        del modelo, period
        return self.status


__all__ = [
    "FixtureProvisioningError",
    "ModeloTestDeadlineChecker",
    "ModeloTestDeadlineStatus",
    "ModeloTestProfile",
    "build_registry_filing_draft",
    "build_registry_filing_draft_from_decimals",
]
