"""Canonical time and :class:`~datetime.datetime` helpers for the AEAT domain.

This namespace is inert. Import every contract below directly from the module
that defines it.

* :mod:`cadrumo.core.time.clock` — :func:`~cadrumo.core.time.clock.now` (the
  current UTC-aware instant), :func:`~cadrumo.core.time.clock.today_madrid`
  (the current Europe/Madrid civil date, the authority for regulated
  date-boundary reference-date defaults), :data:`~cadrumo.core.time.clock.MADRID_TZ`
  (Spain's peninsular civil timezone), and the replay/test-scoped
  :func:`~cadrumo.core.time.clock.frozen_clock` seam with its
  :func:`~cadrumo.core.time.clock.clock_is_frozen` predicate.
* :mod:`cadrumo.core.time.utc` — :func:`~cadrumo.core.time.utc.parse_iso_datetime`
  (policy-neutral ISO-8601 parsing), :func:`~cadrumo.core.time.utc.coerce_utc_aware`,
  :func:`~cadrumo.core.time.utc.validate_utc_aware`, and the
  :data:`~cadrumo.core.time.utc.UtcInstant` pydantic field annotation carrying the
  same contract declaratively.
* :mod:`cadrumo.core.time.date_range` —
  :func:`~cadrumo.core.time.date_range.validate_inclusive_date_range` and its
  serialised-bounds counterpart
  :func:`~cadrumo.core.time.date_range.validate_inclusive_iso_date_range`.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
