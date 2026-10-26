"""Lineage-aware reference normalization used by authored-family assessment."""

from __future__ import annotations

from collections.abc import Mapping

from .compiler.identifier_lineage import identifier_lineage
from .edition_delta_types import BlockedCause


def technical_root(raw: Mapping[str, object]) -> bool:
    """Whether a no-predecessor declaration records a converter limitation."""
    declaration = raw.get("predecessor")
    if not isinstance(declaration, Mapping):
        return False
    none = declaration.get("none")
    if not isinstance(none, Mapping):
        return False
    cause = none.get("cause")
    return isinstance(cause, str) and cause in {item.value for item in BlockedCause}


def edition_neutral(value: object, revision_id: str | None) -> object:
    """Replace an edition's own key with its lineage in a reference value."""
    if revision_id is None:
        return value
    if isinstance(value, str):
        return identifier_lineage(value, revision_id)
    if isinstance(value, list | tuple):
        return [identifier_lineage(item, revision_id) if isinstance(item, str) else item for item in value]
    return value


__all__ = ("edition_neutral", "technical_root")
