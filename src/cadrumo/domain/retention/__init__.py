"""Public facade for the tax-record retention-floor domain.

A filed tax record may only be erased once the tax authority's right to review
it has prescribed. Ley 58/2003 (Ley General Tributaria) art. 66 sets that
prescription at four years, art. 67 runs it from the day after the voluntary
self-assessment deadline, and art. 70.2 ties the obligation to conserve the
supporting documentation to the same window. The whole-year floor is the
grounded regulatory constant :data:`TAX_RECORD_RETENTION_FLOOR_YEARS`.

Public surface:

* :func:`assess_retention_floor` — pure assessment of a filed-record set
  against the floor as of an instant.
* :func:`earliest_safe_erase_date` — the earliest instant one record may be
  erased.
* :class:`RetentionFloorAssessment` — the assessment outcome, exposing
  ``blocks_erase`` and ``latest_safe_erase_date``.
* :class:`RetentionBlockingRecord` — one record still inside its window.
* :class:`RetainableFilingRecord` — structural view the assessment consumes
  (satisfied by :class:`domain.modelos.ModeloRecord`).
* :class:`RetentionFloorError` / :class:`RetentionError` — the refusal raised
  when an erase would destroy a still-retained record without an override.

See Also:
    :class:`domain.modelos.ModeloRecord`
        The filed-record aggregate the floor assesses.
    :mod:`application.bucket_maintenance`
        The erase surface that enforces the floor before destroying a bucket.
"""

from __future__ import annotations

from ._errors import RetentionError, RetentionFloorError
from ._floor import (
    TAX_RECORD_RETENTION_FLOOR_YEARS,
    RetainableFilingRecord,
    RetentionBlockingRecord,
    RetentionFloorAssessment,
    add_prescription_years,
    assess_retention_floor,
    earliest_safe_erase_date,
)

__all__ = [
    "TAX_RECORD_RETENTION_FLOOR_YEARS",
    "RetainableFilingRecord",
    "RetentionBlockingRecord",
    "RetentionError",
    "RetentionFloorAssessment",
    "RetentionFloorError",
    "add_prescription_years",
    "assess_retention_floor",
    "earliest_safe_erase_date",
]
