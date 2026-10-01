"""Compose the installed calendar's local encrypted AEAT observation reader."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

from ..application.overview.calendar_models import (
    OverviewAeatSubmissionState,
    OverviewCalendarEvent,
    OverviewCalendarEventType,
)
from ..application.overview.evidence import AeatCalendarEvidenceSources, CalendarEvidenceReadOutcome
from ..application.overview.home import HomeAvailability, HomeZoneState
from ..core.errors.hierarchy import CadrumoError

if TYPE_CHECKING:
    from ..domain.calculations.registry.authority import PinnedAuthorityOperation


def compose_calendar_aeat_reader(
    operation: PinnedAuthorityOperation,
) -> Callable[[], CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]]:
    """Read retained official facts without contacting AEAT or requiring a linked receipt."""
    from ..adapters.outbound.aeat.sede.observation_store import FiledDeclaracionObservationStore
    from ..application.calculations.revision_carry_gate import revision_carry_outcome
    from ..core.config import load_settings

    retained: tuple[OverviewCalendarEvent, ...] = ()
    retained_at: datetime | None = None

    def read() -> CalendarEvidenceReadOutcome[AeatCalendarEvidenceSources]:
        nonlocal retained, retained_at
        try:
            store = FiledDeclaracionObservationStore(load_settings().cadrumo_filed_declarations_dir)
            observations = store.list_observations()
            if not observations:
                return CalendarEvidenceReadOutcome(
                    state=HomeZoneState(
                        availability=HomeAvailability.STALE if retained else HomeAvailability.NEVER_CAPTURED,
                        reason_code="workbench.calendar.no_aeat_observations",
                        observed_at=retained_at,
                    ),
                    value=AeatCalendarEvidenceSources(observed_events=retained) if retained else None,
                )
            healthy = tuple(
                item
                for item in observations
                if not revision_carry_outcome(item.registry_snapshot_ref, operation=operation).refused
            )
            partial = len(healthy) != len(observations)
            retained_at = max(artefact.captured_at for item in observations for artefact in item.artefacts)
            retained = tuple(
                OverviewCalendarEvent(
                    event_type=OverviewCalendarEventType.FILING,
                    event_date=item.presented_at.date(),
                    source="filed_declaration_observation",
                    summary="filed_declaration_observation",
                    reference_id=str(item.expediente_id),
                    modelo=item.modelo,
                    filing_year=item.ejercicio,
                    period=item.period,
                    status=item.status,
                    authenticated_identity=item.authenticated_identity,
                    aeat_submission_state=OverviewAeatSubmissionState.SUBMITTED_OBSERVED,
                    aeat_submitted_at=item.presented_at,
                    justificante_verified=False,
                )
                for item in healthy
            )
            return CalendarEvidenceReadOutcome(
                state=HomeZoneState(
                    availability=HomeAvailability.STALE if partial else HomeAvailability.AVAILABLE,
                    reason_code="workbench.calendar.aeat_coordinate_unconfirmed" if partial else None,
                    observed_at=retained_at,
                ),
                value=AeatCalendarEvidenceSources(filed_declaration_observations=healthy),
            )
        except (CadrumoError, ValueError, OSError):
            return CalendarEvidenceReadOutcome(
                state=HomeZoneState(
                    availability=HomeAvailability.STALE if retained else HomeAvailability.UNAVAILABLE,
                    reason_code="workbench.calendar.aeat_reader_unavailable",
                    observed_at=retained_at if retained else None,
                ),
                value=AeatCalendarEvidenceSources(observed_events=retained) if retained else None,
            )

    return read
