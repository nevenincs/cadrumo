"""Filing-deadline computation engine for autónomo profiles.

The :class:`DeadlineEngine` is the project's first user-visible
"answer-the-user" surface: given an :class:`AutonomoProfile` and a
year, it produces a deterministic, typed :class:`Schedule` of every
filing the autónomo is obliged to submit, with concrete opens/closes
dates and a current :class:`ObligationStatus`.

The engine is read-only - it never touches the storage layer, never
files anything, never mutates its inputs. See
``[[2026-04-12-deadline-engine-adr]]`` for the architectural decisions.

Usage::

    from datetime import date

    from . import (
        AutonomoProfile,
        DeadlineEngine,
        IVARegime,
        next_deadline,
    )

    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=True,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    engine = DeadlineEngine()
    schedule = engine.compute(profile, year=2026, today=date(2026, 4, 1))
    print(next_deadline(schedule, today=date(2026, 4, 1)))
"""

from __future__ import annotations

from ._applies import applies_to, explain
from ._calendar import (
    CALENDAR,
    KNOWN_AUTONOMO_MODELOS,
    SUPPORTED_YEARS,
    CanonicalWindow,
    PeriodKind,
)
from ._engine import DeadlineEngine, next_deadline
from ._errors import (
    DeadlineError,
    ProfileError,
    ScheduleComputationError,
)
from ._models import (
    AutonomoProfile,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
)
from ._protocols import ModeloIdentifier

__all__ = [
    "CALENDAR",
    "KNOWN_AUTONOMO_MODELOS",
    "SUPPORTED_YEARS",
    "AutonomoProfile",
    "CanonicalWindow",
    "DeadlineEngine",
    "DeadlineError",
    "FilingObligation",
    "IVARegime",
    "ModeloIdentifier",
    "ObligationStatus",
    "PeriodKind",
    "ProfileError",
    "Schedule",
    "ScheduleComputationError",
    "applies_to",
    "explain",
    "next_deadline",
]
