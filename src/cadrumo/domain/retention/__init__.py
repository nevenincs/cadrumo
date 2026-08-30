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
* :class:`RetentionFloorAssessment` — the assessment outcome, exposing
  ``blocks_erase`` and ``latest_safe_erase_date``.
* :class:`RetentionBlockingRecord` — one record still inside its window.
* :class:`RetainableFilingRecord` — structural view the assessment consumes
  (satisfied by :class:`~ModeloRecord`).
* :class:`RetentionFloorError` / :class:`RetentionError` — the refusal
  RESERVED for an erase that would destroy a still-retained record without an
  override. Nothing raises it today; the erase it guarded was withdrawn with
  it, and :mod:`application.bucket_maintenance` refuses every existing target
  rather than erasing one it cannot assess.

See Also:
    :class:`~ModeloRecord`
        The filed-record aggregate the floor assesses.
    :mod:`application.bucket_maintenance`
        The surface that once enforced the floor. Its destructive erase is
        withdrawn; it now refuses an existing target outright, naming the
        authenticated retention assessment it can no longer make.
"""

from __future__ import annotations

from ._floor import (
    TAX_RECORD_RETENTION_FLOOR_YEARS,
    RetainableFilingRecord,
    RetentionBlockingRecord,
    RetentionFloorAssessment,
    assess_retention_floor,
)
from .errors import RetentionError, RetentionFloorError

__all__ = [
    "TAX_RECORD_RETENTION_FLOOR_YEARS",
    "RetainableFilingRecord",
    "RetentionBlockingRecord",
    "RetentionError",
    "RetentionFloorAssessment",
    "RetentionFloorError",
    "assess_retention_floor",
]
