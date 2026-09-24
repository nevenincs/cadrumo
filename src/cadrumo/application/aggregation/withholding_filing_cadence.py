"""The withholding filing periods a filer's canonical schedule assigns, and the refusal when none is quarterly.

Captured withholding and the annual summaries built from it use quarterly
windows only. Whether a filer's Modelo 111, 115 or 123 is quarterly is decided
by the profile conditions on the modelo revision's filing schedules. The
deadline engine reads the same schedules through
:func:`~cadrumo.domain.calculations.registry.schedules.applicable_filing_schedules`
to decide which windows the calendar shows, so this module asks that one
resolver the same question for each quarter.

A filer whose schedule does not assign a quarter (a large company filing
monthly, or a filer no schedule covers at all) is refused before anything is
written. The annual summary sources refuse the same way instead of returning a
total that silently omits the months that quarterly windows cannot hold.
"""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, Field

from ...core.i18n.translatable import Translatable as tr
from ...core.modelo import Modelo
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...domain.calculations.registry.schedules import applicable_filing_schedules
from ...domain.calculations.registry.temporal import select_revision_metadata
from ._preconditions import AggregationPreconditionCondition, aggregation_no_recovery_verdict
from .errors import AggregationError

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ...domain.calculations.registry.authority import PinnedAuthorityOperation
    from ...domain.deadlines.models import TaxpayerProfile
    from ..modelo.work_profile import ModeloWorkProfile

#: The periodic withholding modelos captured withholding is placed in.
PERIODIC_WITHHOLDING_MODELOS: Final[tuple[Modelo, ...]] = (Modelo("111"), Modelo("115"), Modelo("123"))

_QUARTERS: Final[tuple[str, ...]] = ("1T", "2T", "3T", "4T")


class WithholdingFilingCadenceRefusal(StrEnum):
    """Why withholding could not be placed in, or read from, quarterly windows."""

    QUARTERLY_WINDOW_NOT_SCHEDULED = "withholding_quarterly_window_not_scheduled"
    ANNUAL_SOURCE_NOT_QUARTERLY = "withholding_annual_source_not_quarterly"
    FILER_PROFILE_ABSENT = "withholding_filer_profile_absent"


class WithholdingFilingCadenceError(AggregationError):
    """Refusal to place or total withholding in quarterly windows the filer's schedule does not assign.

    ``refusal_code`` is the stable token transports surface without echoing
    financial evidence; the precondition verdict carries the observed facts and
    no command action, because monthly withholding windows are not supported
    yet and no step the application can offer recovers from that.
    """

    def __init__(
        self,
        refusal: WithholdingFilingCadenceRefusal,
        message: tr,
        *,
        facts: Mapping[str, str | int | bool],
    ) -> None:
        """Build the refusal from its reason and observed facts."""
        condition = (
            AggregationPreconditionCondition.WITHHOLDING_FILER_PROFILE_PRESENT
            if refusal is WithholdingFilingCadenceRefusal.FILER_PROFILE_ABSENT
            else AggregationPreconditionCondition.WITHHOLDING_QUARTERLY_WINDOW_SCHEDULED
        )
        super().__init__(
            message,
            context=dict(facts),
            precondition_verdict=aggregation_no_recovery_verdict(condition, facts=facts),
        )
        self.refusal_code = refusal.value


class WithholdingModeloSchedule(BaseModel):
    """What the filer's canonical schedule assigns one periodic withholding modelo in one year.

    ``scheduled_periods`` lists every period of the applicable schedules in
    authored order, monthly ones included. ``quarterly_periods`` lists the
    quarters the schedule assigns, decided per quarter exactly as the deadline
    engine decides whether a quarterly window applies.
    """

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    filing_year: int = Field(ge=1)
    scheduled_periods: tuple[str, ...]
    quarterly_periods: tuple[str, ...]

    @property
    def unscheduled_quarters(self) -> tuple[str, ...]:
        """Return the quarters the schedule does not assign."""
        return tuple(quarter for quarter in _QUARTERS if quarter not in self.quarterly_periods)


class WithholdingFilerCadence(BaseModel):
    """The filer's schedule for every periodic withholding modelo in one filing year."""

    model_config = STRICT_FROZEN_CONFIG

    filing_year: int = Field(ge=1)
    schedules: tuple[WithholdingModeloSchedule, ...]

    def schedule_for(self, modelo: str) -> WithholdingModeloSchedule:
        """Return the resolved schedule for ``modelo``; an unresolved modelo is a programming error."""
        normalized = Modelo(modelo).value
        for schedule in self.schedules:
            if schedule.modelo == normalized:
                return schedule
        raise LookupError(f"no withholding schedule was resolved for modelo {normalized}")


def _modelo_schedule(
    taxpayer_profile: TaxpayerProfile,
    *,
    modelo: Modelo,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> WithholdingModeloSchedule:
    directory = operation.modelo_directory(modelo)
    scheduled: list[str] = []
    quarterly: list[str] = []
    for quarter in _QUARTERS:
        revision = select_revision_metadata(directory, filing_year=filing_year, period=quarter)
        if not revision.filing_schedules:
            quarterly.append(quarter)
            if quarter not in scheduled:
                scheduled.append(quarter)
            continue
        if applicable_filing_schedules(revision, taxpayer_profile, period=quarter):
            quarterly.append(quarter)
        for schedule in applicable_filing_schedules(revision, taxpayer_profile):
            scheduled.extend(period for period in schedule.periods if period not in scheduled)
    return WithholdingModeloSchedule(
        modelo=modelo.value,
        filing_year=filing_year,
        scheduled_periods=tuple(scheduled),
        quarterly_periods=tuple(quarterly),
    )


def resolve_withholding_filer_cadence(
    taxpayer_profile: TaxpayerProfile,
    *,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> WithholdingFilerCadence:
    """Resolve which withholding periods the filer's canonical filing schedule assigns in ``filing_year``."""
    return WithholdingFilerCadence(
        filing_year=filing_year,
        schedules=tuple(
            _modelo_schedule(taxpayer_profile, modelo=modelo, filing_year=filing_year, operation=operation)
            for modelo in PERIODIC_WITHHOLDING_MODELOS
        ),
    )


def _filer_profile_absent(filing_year: int) -> WithholdingFilingCadenceError:
    return WithholdingFilingCadenceError(
        WithholdingFilingCadenceRefusal.FILER_PROFILE_ABSENT,
        tr("aggregation.retenciones.errors.withholding_filer_profile_absent"),
        facts={"filing_year": str(filing_year), "profile_present": False},
    )


def withholding_filer_cadence_for_work_profile(
    profile: ModeloWorkProfile | None,
    *,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> WithholdingFilerCadence:
    """Resolve the cadence from a loaded work profile, refusing when none was loaded."""
    if profile is None:
        raise _filer_profile_absent(filing_year)
    from ..user_profile.projections import projection_for_taxpayer

    taxpayer_profile = projection_for_taxpayer(profile.record, schema=profile.profile_decode_context.schema)
    return resolve_withholding_filer_cadence(taxpayer_profile, filing_year=filing_year, operation=operation)


def load_bucket_withholding_filer_cadence(
    *,
    bucket_id: str,
    filing_year: int,
    operation: PinnedAuthorityOperation,
) -> WithholdingFilerCadence:
    """Load the bucket's profile through its authenticated session and resolve its cadence."""
    from ...domain.user_profile.errors import ProfileNotFoundError
    from ..user_profile.profile_record_repository import ProfileRecordRepository
    from ..user_profile.projections import projection_for_taxpayer

    profile_decode_context = operation.profile_decode_context()
    try:
        record = ProfileRecordRepository.for_current_session(
            bucket_id,
            profile_decode_context=profile_decode_context,
        ).load(bucket_id)
    except ProfileNotFoundError as exc:
        raise _filer_profile_absent(filing_year) from exc
    taxpayer_profile = projection_for_taxpayer(record, schema=profile_decode_context.schema)
    return resolve_withholding_filer_cadence(taxpayer_profile, filing_year=filing_year, operation=operation)


def quarterly_withholding_capture_period(
    cadence: WithholdingFilerCadence,
    *,
    modelo: str,
    recognized_on: date,
) -> Period:
    """Return the quarterly window for withholding recognised on ``recognized_on``.

    Refuses when the filer's schedule does not assign that quarter, because the
    only other windows the schedule can assign are monthly ones, which capture
    cannot place withholding in yet. A cadence resolved for another year is a
    caller defect and is refused rather than read as this year's schedule.
    """
    if cadence.filing_year != recognized_on.year:
        raise ValueError("withholding filer cadence was resolved for a different year than the recognition")
    quarter = f"{((recognized_on.month - 1) // 3) + 1}T"
    schedule = cadence.schedule_for(modelo)
    if quarter not in schedule.quarterly_periods:
        raise WithholdingFilingCadenceError(
            WithholdingFilingCadenceRefusal.QUARTERLY_WINDOW_NOT_SCHEDULED,
            tr("aggregation.retenciones.errors.withholding_quarterly_window_not_scheduled"),
            facts={
                "modelo": schedule.modelo,
                "filing_year": str(schedule.filing_year),
                "period": quarter,
                "scheduled_periods": "|".join(schedule.scheduled_periods),
                "monthly_windows_supported": False,
            },
        )
    return Period.from_year_and_code(recognized_on.year, quarter)


def require_quarterly_withholding_source(
    cadence: WithholdingFilerCadence,
    *,
    annual_modelo: str,
    source_modelo: str,
) -> None:
    """Refuse an annual summary whose source modelo the filer does not file quarterly all year.

    The annual source reads quarterly windows only, so any unassigned quarter
    means months of withholding it cannot see; totalling the rest would look
    complete while under-declaring.
    """
    schedule = cadence.schedule_for(source_modelo)
    unscheduled = schedule.unscheduled_quarters
    if not unscheduled:
        return
    raise WithholdingFilingCadenceError(
        WithholdingFilingCadenceRefusal.ANNUAL_SOURCE_NOT_QUARTERLY,
        tr("aggregation.retenciones.errors.withholding_annual_source_not_quarterly"),
        facts={
            "annual_modelo": Modelo(annual_modelo).value,
            "modelo": schedule.modelo,
            "filing_year": str(schedule.filing_year),
            "unscheduled_quarters": "|".join(unscheduled),
            "scheduled_periods": "|".join(schedule.scheduled_periods),
            "monthly_windows_supported": False,
        },
    )


__all__ = [
    "PERIODIC_WITHHOLDING_MODELOS",
    "WithholdingFilerCadence",
    "WithholdingFilingCadenceError",
    "WithholdingFilingCadenceRefusal",
    "WithholdingModeloSchedule",
    "load_bucket_withholding_filer_cadence",
    "quarterly_withholding_capture_period",
    "require_quarterly_withholding_source",
    "resolve_withholding_filer_cadence",
    "withholding_filer_cadence_for_work_profile",
]
