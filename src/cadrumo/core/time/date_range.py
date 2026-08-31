"""Canonical inclusive date-range invariant.

A ``since``/``until`` pair names a closed interval. When ``until`` precedes
``since`` the interval is empty by construction, so every filter built from it
matches nothing — and a report rendered from it presents a window that never
existed while still claiming zero observations. That is indistinguishable from
"nothing happened in this window", which is the reason the pair has to be
rejected rather than merely producing empty output.

The bounds arrive from independently parsed CLI options, so neither parse site
can see the other's value; the invariant is a property of the *pair* and
therefore belongs at one shared authority rather than at either parse site.
Equal bounds are valid: a single-day window is a legitimate query.
"""

from __future__ import annotations

from datetime import date

from ..errors.hierarchy import CoreValidationError


def validate_inclusive_date_range(since: date | None, until: date | None) -> None:
    """Reject a bound pair whose upper bound precedes its lower bound.

    Either bound may be ``None`` (open on that side), and equal bounds are
    accepted as a single-day window.

    Args:
        since: Inclusive lower bound, or ``None`` for no lower bound.
        until: Inclusive upper bound, or ``None`` for no upper bound.

    Raises:
        CoreValidationError: When both bounds are populated and ``until`` is
            strictly earlier than ``since``.
    """
    if since is None or until is None:
        return
    if until < since:
        raise CoreValidationError(
            f"inclusive date range is empty: until {until.isoformat()} precedes since {since.isoformat()}",
        )


def validate_inclusive_iso_date_range(since: str | None, until: str | None) -> None:
    """Apply :func:`validate_inclusive_date_range` to ISO-8601 date text.

    Wire payloads carry the bounds as ``date.isoformat()`` output rather than
    :class:`~datetime.date` objects, so they need the same invariant applied
    to the serialised form. Parsing here keeps the wire boundary bound to the
    one authority instead of comparing strings and relying on ISO-8601
    ordering happening to agree with date ordering.

    Args:
        since: Inclusive lower bound as ``YYYY-MM-DD``, or ``None``.
        until: Inclusive upper bound as ``YYYY-MM-DD``, or ``None``.

    Raises:
        CoreValidationError: When either bound is populated but not an
            ISO-8601 date, or when the populated pair is reversed.
    """
    parsed: list[date | None] = []
    for raw, label in ((since, "since"), (until, "until")):
        if raw is None:
            parsed.append(None)
            continue
        try:
            parsed.append(date.fromisoformat(raw))
        except ValueError as exc:
            raise CoreValidationError(f"{label} must be an ISO-8601 date (YYYY-MM-DD); got {raw!r}") from exc
    validate_inclusive_date_range(parsed[0], parsed[1])
