"""Pure tax-record retention-floor assessment.

A filed tax record may only be erased once the governed retention floor has
elapsed. The floor is resolved from the dated registry at the assessment
boundary; this module contains only the calendar arithmetic and the resulting
assessment models.

This module is pure: it derives, for a set of filed records and an ``as_of``
instant, which records are still inside their retention window (and therefore
block a destructive erase) and the earliest instant at which every record
becomes safe to erase. It performs no I/O and holds no storage handle; the
application erase path feeds it the loaded :class:`ModeloRecord` set and acts
on the returned :class:`RetentionFloorAssessment`.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from pydantic import BaseModel, Field, NonNegativeInt

from ...core.calendar_shift import shift_by_calendar_years
from ...core.filing_year import FilingYear
from ...core.identity.hex_ids import FilingRecordId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.utc import UtcInstant
from ..calculations.registry.errors import RegistryValidationError
from ..calculations.registry.facts.resolution import ResolvedScalarFact, ScalarFactQuery
from ..calculations.registry.schema_base import DateAxis

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority


_RETENTION_FLOOR_FACT_ID = "lgt-tax-record-retention-floor-years"


def _resolve_retention_floor_years(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> int:
    """Resolve the dated retention scalar through the registry authority."""
    if authority is None:
        from ..calculations.registry.authority import bundled_authority

        authority = bundled_authority()
    resolved = cast(
        "ResolvedScalarFact",
        authority.resolve_governed_fact(
            ScalarFactQuery(
                fact_id=_RETENTION_FLOOR_FACT_ID,
                date_axis=DateAxis.FILING_PERIOD,
                effective_date=effective_date,
            ),
        ),
    )
    value = resolved.payload.value
    if isinstance(value, bool) or not isinstance(value, int):
        raise RegistryValidationError(
            f"retention floor fact {resolved.fact_id!r} resolved non-integer payload {value!r}",
        )
    return value


@runtime_checkable
class RetainableFilingRecord(Protocol):
    """Structural view of a filed record the retention floor assesses.

    :class:`~ModeloRecord` satisfies this view. Only the
    fields the floor needs are declared so the retention domain does not couple
    to the full filing-record schema.
    """

    @property
    def filing_record_id(self) -> FilingRecordId:
        """Content-addressed id of the filing record."""
        ...

    @property
    def modelo(self) -> object:
        """AEAT modelo code the record was filed under."""
        ...

    @property
    def filing_year(self) -> int:
        """Filing year the record belongs to."""
        ...

    @property
    def filed_at(self) -> datetime:
        """Instant the record was filed."""
        ...


class RetentionBlockingRecord(BaseModel):
    """One filed record still inside its legal retention window.

    Carries the earliest instant at which the record becomes safe to erase so
    the refusal can name a concrete date rather than a bare "still retained".
    """

    model_config = STRICT_FROZEN_CONFIG

    filing_record_id: FilingRecordId
    modelo: str = Field(min_length=1)
    filing_year: FilingYear
    filed_at: UtcInstant
    earliest_safe_erase_date: UtcInstant


class RetentionFloorAssessment(BaseModel):
    """Outcome of assessing a record set against the legal retention floor.

    ``retained`` holds every record whose retention window has not yet elapsed
    as of ``as_of``; ``latest_safe_erase_date`` is the maximum
    ``earliest_safe_erase_date`` across those records (the instant at which the
    whole set becomes erasable) or ``None`` when nothing is retained.
    """

    model_config = STRICT_FROZEN_CONFIG

    as_of: UtcInstant
    floor_years: NonNegativeInt
    retained: tuple[RetentionBlockingRecord, ...] = ()

    @property
    def blocks_erase(self) -> bool:
        """Whether any record still inside its window blocks a destructive erase."""
        return bool(self.retained)

    @property
    def latest_safe_erase_date(self) -> datetime | None:
        """Instant the whole assessed set becomes safe to erase, or ``None``."""
        if not self.retained:
            return None
        return max(record.earliest_safe_erase_date for record in self.retained)


def erase_is_blocked(*, blocks_erase: bool, override_approved: bool = False) -> bool:
    """Whether the retention floor refuses a destructive erase.

    The one place the rule is decided. Both destructive surfaces reach it, and
    they carry the two facts rather than an assessment because they hold
    different types: the all-profile reset works from a
    ``ConfigResetRetentionDecision`` it has already resolved, the single-target
    delete from a :class:`RetentionFloorAssessment` straight off the
    maintenance authority. Taking the facts keeps one rule serving both without
    forcing either into the other's model.

    ``override_approved`` defaults to false because a surface that offers no
    override must not have to say so. The single-target delete has no override
    to record, and passing nothing is the accurate statement of that.

    Before this existed the decision was written twice and the CLI verb's
    docstring said so plainly: the reset tested the flag together with an
    override, the delete tested the flag alone, and a third condition added to
    the retention contract would have reached one and not the other. The NUMBERS
    were never duplicated -- both read the retained count and the safe-erase date
    from the same assessment -- so the risk was never a wrong figure. It was the
    two surfaces coming to different conclusions about the same records.
    """
    return blocks_erase and not override_approved


def assess_retention_floor(
    records: Iterable[RetainableFilingRecord],
    *,
    as_of: datetime,
    authority: ValidatedRegistryAuthority | None = None,
) -> RetentionFloorAssessment:
    """Assess ``records`` against the registry-resolved retention floor.

    A record is retained (blocking) when ``as_of`` precedes its safe-erase
    instant, which is ``filed_at`` shifted forward by the dated registry
    scalar's whole calendar years. The floor is anchored on ``filed_at``
    rather than a deadline that is not carried by the record because the filing
    instant is the durable evidence it carries; anchoring on it is conservative for
    the common case (filing occurs at or near the deadline) and errs toward
    keeping late-filed records longer. A record whose window has elapsed is
    safe to erase and is excluded from the assessment's ``retained`` set.

    Returns:
        The :class:`RetentionFloorAssessment` for ``records``.
    """
    floor_years = _resolve_retention_floor_years(
        effective_date=as_of.date(),
        authority=authority,
    )
    retained: list[RetentionBlockingRecord] = []
    for record in records:
        safe_at = shift_by_calendar_years(record.filed_at, floor_years)
        if as_of < safe_at:
            retained.append(
                RetentionBlockingRecord(
                    filing_record_id=record.filing_record_id,
                    modelo=str(record.modelo),
                    filing_year=record.filing_year,
                    filed_at=record.filed_at,
                    earliest_safe_erase_date=safe_at,
                ),
            )
    retained.sort(key=lambda blocking: blocking.earliest_safe_erase_date)
    return RetentionFloorAssessment(
        as_of=as_of,
        floor_years=floor_years,
        retained=tuple(retained),
    )
