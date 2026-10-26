"""Low-level token parsers shared across adapters and domain modules.

These helpers sit at the ``core`` layer so they carry no domain
dependencies. They are pure functions: no I/O, no registry access.
"""

from __future__ import annotations

from ..logging import get_logger

_log = get_logger(__name__)

# Tokens that unambiguously mean "true" in AEAT-facing string fields.
#
# This is the ONE vocabulary. Every reader of an operator-written boolean
# resolves through it rather than restating its own set, because a set restated
# per reader diverges per reader: the maritime reader accepted no Spanish at
# all while the filing layer accepted "si", so the same word meant yes in one
# place and no in another with nothing raised in between.
#
# The Spanish half is deliberately complete rather than partial. "si"/"sí" were
# recognised while "s" -- the abbreviation the filing layer has always taken --
# and "verdadero", the ordinary word, were not; accepting one spelling of yes
# and not another is arbitrary from the operator's side, and the spellings that
# were missing are precisely the ones a reader then turned silently into "no".
#
# Hungarian joined the set when a shipped prompt was found asking for words this
# vocabulary did not know: the flows confirm widget renders "Válaszolj igennel
# vagy nemmel" under the `hu` catalogue, so a Hungarian speaker was instructed to
# type `igen` and then refused -- unable to answer either way, since `nem` was
# missing too. A locale that ships a prompt has to ship the words that prompt
# asks for; the alternative is telling a taxpayer to say something the product
# cannot hear.
_TRUTHY: frozenset[str] = frozenset(
    {"true", "1", "yes", "y", "si", "sí", "s", "verdadero", "igen"},
)

# Tokens that unambiguously mean "false", paired spelling-for-spelling with the
# affirmative set above so neither half is more Spanish than the other.
_FALSY: frozenset[str] = frozenset({"false", "0", "no", "n", "falso", "nem"})


def _parse_bool(raw: str | None) -> bool | None:
    """Parse a raw string token into a three-state boolean.

    Args:
        raw: The candidate string token; ``None`` and empty string
            both map to the ``None`` sentinel.

    Returns:
        ``True`` when the token is a recognised affirmative form,
        ``False`` when it is a recognised negative form, and ``None``
        when the token is absent (``None`` or empty string) or
        unrecognised. The ``None`` return for unrecognised tokens lets
        each call-site choose its own sentinel or raise a typed error
        rather than silently coercing garbage to ``False``.
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


#: Public alias — cross-package callers must import ``parse_bool`` rather than
#: the private ``_parse_bool`` implementation name.
parse_bool = _parse_bool


def _enum_value(value: object) -> str:
    """Return ``Enum.value`` when present, otherwise ``str(value)``.

    ``None`` maps to ``""`` -- an absent value never renders as the literal
    string ``"None"``, which every caller of this helper is comparing against
    a closed vocabulary of real wire tokens (a status code, a severity
    level). A non-enum value with no ``.value`` attribute (a plain ``str``,
    an ``int``, a ``bool``) round-trips through ``str()`` unchanged.

    This was two independently-defined, byte-identical functions --
    ``application/workflow/engine_helpers.py::enum_value`` and
    ``domain/submission/preflight.py::_enum_value`` -- before converging
    here. ``core`` is imported by both layers and owned by neither, so it is
    the only home that does not force one layer to depend on the other; the
    domain-layer copy could not have imported the application-layer one, and
    was correctly local before this convergence existed.
    """
    if value is None:
        return ""
    raw = getattr(value, "value", value)
    return str(raw)


#: Public alias — cross-package callers must import ``enum_value`` rather than
#: the private ``_enum_value`` implementation name.
enum_value = _enum_value
