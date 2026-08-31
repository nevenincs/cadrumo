"""ISO-8601 date validation at the CLI boundary.

One shared gate for every operator-supplied date option. Only the ISO ordering
parses, so the DD/MM-versus-MM/DD ambiguity never arises, and a blank value
refuses with the same localised message as a malformed one.

See Also:
    :class:`~cadrumo.core.Period`
        The period boundary these dates are compared against downstream.
"""

from __future__ import annotations

from datetime import date as _date

from ...core.i18n import tr
from ._common import _bad

__all__ = ["_parse_iso_date", "_parse_iso_date_str", "_parse_optional_iso_date_str"]


def _parse_iso_date(
    raw: str,
    *,
    label: str,
    translation_key: str = "cli.common.errors.invalid_iso_date",
    default: str | None = None,
) -> _date:
    from ...core.parsing import parse_iso8601_date

    message = tr(
        translation_key,
        label=label,
        raw=raw,
        option=label,
        value=raw,
        default=default or f"{label} must be an ISO date (YYYY-MM-DD); got {raw!r}.",
    )
    try:
        parsed = parse_iso8601_date(raw.strip())
    except ValueError as exc:
        raise _bad(message) from exc
    if parsed is None:
        # ``parse_iso8601_date`` treats a blank/empty string as "absent" and
        # returns ``None`` rather than raising; this gate requires a value,
        # so blank input refuses with the same message as a malformed one.
        raise _bad(message)
    return parsed


def _parse_iso_date_str(raw: str, *, label: str) -> str:
    """Validate ``raw`` as an ISO-8601 date and return its canonical string.

    The shared ISO gate (:func:`_parse_iso_date`)
    refuses every non-ISO ordering by construction (``15/01/2026``,
    ``01-15-2026``, ``2026/01/15``); this wrapper returns the canonical
    ``YYYY-MM-DD`` form for the several service contracts that persist the date
    as a 10-character string rather than a :class:`~datetime.date`. The
    DD/MM-vs-MM/DD ambiguity never arises because only the ISO ordering parses.
    """
    return _parse_iso_date(raw, label=label).isoformat()


def _parse_optional_iso_date_str(raw: str | None, *, label: str) -> str | None:
    """Validate an optional ISO-8601 date, returning its canonical string or ``None``.

    Returns ``None`` when ``raw`` is ``None`` (the date was not supplied);
    otherwise delegates to
    :func:`_parse_iso_date_str`, so a supplied
    non-ISO date refuses at the CLI boundary.
    """
    if raw is None:
        return None
    return _parse_iso_date_str(raw, label=label)
