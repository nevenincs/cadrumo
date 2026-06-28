"""Public fixture helpers for :mod:`aeat.application.filing`.

This module exposes frozen records that structurally satisfy the filing
profile/deadline protocols, plus registry-backed draft construction helpers.
Tests can exercise application filing workflows without reaching into private
builder internals or replacing the production registry schema provider. It
deliberately does not expose modelo-specific casilla schemas or formulas.

See Also:
    :mod:`aeat.application.filing._testing_registry`
        Registry-backed draft builders re-exported by this facade.
    :mod:`aeat.application.filing.runtime`
        Production profile and schema-provider wiring used outside tests.
"""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from ...core import STRICT_FROZEN_CONFIG, Period
from ...core.errors import FixtureProvisioningError
from ._testing_registry import build_registry_filing_draft, build_registry_filing_draft_from_decimals


class ModeloTestProfile(BaseModel):
    """Frozen :class:`aeat.application.filing.ModeloProfile` test record.

    Only ``tax_id`` and ``display_name`` are carried because those are the
    fields the filing application consumes when constructing a
    :class:`aeat.domain.filing.ModeloDraft`.
    """

    model_config = STRICT_FROZEN_CONFIG

    tax_id: str
    display_name: str


class ModeloTestDeadlineStatus(BaseModel):
    """Frozen :class:`aeat.application.filing.DeadlineStatus` test record."""

    model_config = STRICT_FROZEN_CONFIG

    due_date: date
    is_overdue: bool


class ModeloTestDeadlineChecker(BaseModel):
    """Frozen :class:`aeat.application.filing.DeadlineChecker` test record.

    The checker returns the same :class:`ModeloTestDeadlineStatus`
    for every ``(modelo, period)`` query, which keeps
    :class:`aeat.application.filing.ModeloValidator` deadline checks
    deterministic.
    """

    model_config = STRICT_FROZEN_CONFIG

    status: ModeloTestDeadlineStatus

    def check(self, modelo: str, period: Period) -> ModeloTestDeadlineStatus:
        """Return the configured :class:`ModeloTestDeadlineStatus`.

        The ``modelo`` and typed :class:`~aeat.core.Period` inputs are accepted
        to satisfy :class:`aeat.application.filing.DeadlineChecker`; this helper
        intentionally ignores them and returns the configured status.
        """
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
