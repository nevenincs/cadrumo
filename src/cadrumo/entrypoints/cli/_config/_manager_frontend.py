"""Frontend-neutral selection helpers for CLI profile commands.

The CLI uses these small parser and capability projections to decide whether
an invocation carries explicit profile facts and whether the host supports a
full-screen frontend.  Constructing or presenting that frontend belongs to
``cadrumo.entrypoints.tui``; the CLI remains a line-mode projection over the
application contracts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from collections.abc import Mapping


_ROUTING_META_KEYS = frozenset(
    {
        "ctx",
        "profile_name",
        "quiet",
        "accept_defaults",
        "tui",
        "secrets_stdin",
        "secrets_fd",
        "recovery_handoff_fd",
        "recovery_verification_fd",
    }
)


def _field_value_was_supplied(value: object) -> bool:
    """Return whether a parsed wizard value represents an explicit flag.

    Typer materialises repeated options with an empty list when the operator
    did not pass them. An empty collection is therefore a parser default, not
    an explicit field value; non-empty collections and every scalar value
    (including ``False`` and ``0``) are explicit.
    """
    if value is None:
        return False
    if isinstance(value, list | tuple):
        items = cast(list[object] | tuple[object, ...], value)
        return any(str(item) for item in items)
    return True


def has_explicit_profile_fields(kwargs: Mapping[str, object]) -> bool:
    """Whether parsed wizard kwargs contain a field the caller supplied."""
    return any(_field_value_was_supplied(value) for key, value in kwargs.items() if key not in _ROUTING_META_KEYS)


__all__ = [
    "has_explicit_profile_fields",
]
