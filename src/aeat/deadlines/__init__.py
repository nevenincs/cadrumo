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

    from aeat.deadlines import (
        AutonomoProfile,
        DeadlineEngine,
        IVARegime,
        next_deadline,
    )

    class _InProcessCatalogue:
        def known_modelos(self):
            return ("100", "111", "115", "130", "180", "190", "303", "349", "390", "720")

        def is_known(self, modelo):
            return modelo in self.known_modelos()

    profile = AutonomoProfile(
        tax_id="X1234567L",
        iva_regime=IVARegime.GENERAL,
        has_employees=False,
        pays_rent_with_retencion=True,
        does_intracomunitario=False,
        bienes_extranjero_above_threshold=False,
    )
    engine = DeadlineEngine(_InProcessCatalogue())
    schedule = engine.compute(profile, year=2026, today=date(2026, 4, 1))
    print(next_deadline(schedule, today=date(2026, 4, 1)))
"""

from __future__ import annotations

from aeat.deadlines._applies import applies_to, explain
from aeat.deadlines._calendar import (
    CALENDAR,
    KNOWN_AUTONOMO_MODELOS,
    SUPPORTED_YEARS,
    CanonicalWindow,
    PeriodKind,
)
from aeat.deadlines._engine import DeadlineEngine, next_deadline
from aeat.deadlines._errors import (
    DeadlineError,
    ProfileError,
    ScheduleComputationError,
)
from aeat.deadlines._models import (
    AutonomoProfile,
    FilingObligation,
    IVARegime,
    ObligationStatus,
    Schedule,
)
from aeat.deadlines._protocols import (
    CorpusReader,
    ModeloCatalogueLoader,
    ModeloIdentifier,
)

__all__ = [
    "CALENDAR",
    "KNOWN_AUTONOMO_MODELOS",
    "SUPPORTED_YEARS",
    "AutonomoProfile",
    "CanonicalWindow",
    "CorpusReader",
    "DeadlineEngine",
    "DeadlineError",
    "FilingObligation",
    "IVARegime",
    "ModeloCatalogueLoader",
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
