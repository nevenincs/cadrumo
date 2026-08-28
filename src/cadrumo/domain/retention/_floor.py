"""Pure tax-record retention-floor assessment.

A filed tax record may only be erased once the Administration's right to
review it has prescribed. Ley 58/2003 (LGT) art. 66 sets that prescription at
four years; art. 67 runs the period from the day after the voluntary
self-assessment deadline; art. 70.2 ties the obligation to conserve the
supporting documentation to the same window. The whole-year floor is the
regulatory constant :data:`TAX_RECORD_RETENTION_FLOOR_YEARS`.

This module is pure: it derives, for a set of filed records and an ``as_of``
instant, which records are still inside their retention window (and therefore
block a destructive erase) and the earliest instant at which every record
becomes safe to erase. It performs no I/O and holds no storage handle; the
application erase path feeds it the loaded :class:`ModeloRecord` set and acts
on the returned :class:`RetentionFloorAssessment`.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Final, Protocol, runtime_checkable

from pydantic import BaseModel, Field

from ...core import STRICT_FROZEN_CONFIG
from ...core.calendar_shift import shift_by_calendar_years
from ...core.identity import FilingRecordId

#: Legal retention floor (in whole years) for a filed tax record before it may
#: be erased. Binding provision: Ley 58/2003 (Ley General Tributaria) art. 66 —
#: "Prescribirán a los cuatro años" the Administration's right to determine and
#: to demand the tax debt and the taxpayer's right to refunds; art. 67 runs that
#: period from the day after the voluntary self-assessment deadline; art. 70.2
#: ties the obligation to conserve the supporting documentation to the
#: prescription period. BOE-A-2003-23186
#: (https://www.boe.es/buscar/act.php?id=BOE-A-2003-23186#a66). A filed record
#: whose four-year prescription window has not yet elapsed is still reviewable by
#: AEAT and MUST NOT be erased without an explicit operator override. This is the
#: LGT tax-record floor; the Código de Comercio art. 30 six-year accounting-book
#: obligation is a separate, longer regime and is out of scope here. This
#: regulatory constant is the retention domain's authoritative home for the
#: floor (the schema-central re-export surface may later mirror it).
TAX_RECORD_RETENTION_FLOOR_YEARS: Final[int] = 4


@runtime_checkable
class RetainableFilingRecord(Protocol):
    """Structural view of a filed record the retention floor assesses.

    :class:`~domain.modelos.ModeloRecord` satisfies this view. Only the
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
    filing_year: int = Field(ge=2000, le=2099)
    filed_at: datetime
    earliest_safe_erase_date: datetime


class RetentionFloorAssessment(BaseModel):
    """Outcome of assessing a record set against the legal retention floor.

    ``retained`` holds every record whose retention window has not yet elapsed
    as of ``as_of``; ``latest_safe_erase_date`` is the maximum
    ``earliest_safe_erase_date`` across those records (the instant at which the
    whole set becomes erasable) or ``None`` when nothing is retained.
    """

    model_config = STRICT_FROZEN_CONFIG

    as_of: datetime
    floor_years: int = Field(ge=0)
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


def assess_retention_floor(
    records: Iterable[RetainableFilingRecord],
    *,
    as_of: datetime,
    floor_years: int = TAX_RECORD_RETENTION_FLOOR_YEARS,
) -> RetentionFloorAssessment:
    """Assess ``records`` against the legal retention floor as of ``as_of``.

    A record is retained (blocking) when ``as_of`` precedes its safe-erase
    instant, which is ``filed_at`` shifted forward by ``floor_years`` whole
    calendar years. The floor is anchored on ``filed_at`` rather than the
    voluntary-deadline end (LGT art. 67) because the filing instant is the
    durable evidence the record carries; anchoring on it is conservative for
    the common case (filing occurs at or near the deadline) and errs toward
    keeping late-filed records longer. A record whose window has elapsed is
    safe to erase and is excluded from the assessment's ``retained`` set.

    Returns:
        The :class:`RetentionFloorAssessment` for ``records``.
    """
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
