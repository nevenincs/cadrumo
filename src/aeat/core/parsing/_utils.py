"""Low-level token parsers shared across adapters and domain modules.

These helpers sit at the ``core`` layer so they carry no domain
dependencies. They are pure functions: no I/O, no registry access.
"""

from __future__ import annotations

from ..logging import get_logger

_log = get_logger(__name__)

# Tokens that unambiguously mean "true" in AEAT-facing string fields.
# Includes Spanish affirmative forms ("sí"/"si") used in G313 exports.
_TRUTHY: frozenset[str] = frozenset({"true", "1", "yes", "y", "si", "sí"})

# Tokens that unambiguously mean "false".
_FALSY: frozenset[str] = frozenset({"false", "0", "no", "n"})


def _parse_bool(raw: str | None) -> bool | None:
    """Parse a raw string token into a three-state boolean.

    Returns:
        ``True``  — token is a recognised affirmative form.
        ``False`` — token is a recognised negative form.
        ``None``  — token is absent (``None`` or empty string) or
                    unrecognised; the caller decides the fallback.

    The ``None`` return for unrecognised tokens lets each call-site
    choose its own sentinel or raise a typed error rather than silently
    coercing garbage to ``False``.
    """
    if raw is None or raw == "":
        return None
    token = raw.strip().lower()
    if token in _TRUTHY:
        return True
    if token in _FALSY:
        return False
    _log.debug("_parse_bool: unrecognised token %r — returning None", token)
    return None
