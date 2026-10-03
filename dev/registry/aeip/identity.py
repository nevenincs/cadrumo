"""Canonical AEIP event-title normalisation and continuity-id construction."""

from __future__ import annotations

import re
import unicodedata

from pydantic import TypeAdapter, ValidationError

from cadrumo.core.identity.continuidad import ContinuidadId

from .constants import CHAIN_COLUMN_LEAF, CHAIN_PREFIX

__all__ = ("CHAIN_ID_MAX_LENGTH", "chain_id_for", "chain_id_is_wellformed", "derive_slug")

_CHAIN_ID_ADAPTER = TypeAdapter(ContinuidadId)
CHAIN_ID_MAX_LENGTH: int = int(_CHAIN_ID_ADAPTER.json_schema()["maxLength"])
_WHITESPACE = re.compile(r"\s+")
_NON_SLUG = re.compile(r"[^a-z0-9]+")
_SLUG_RUNS = re.compile(r"-{2,}")


def chain_id_is_wellformed(candidate: str) -> bool:
    """Report whether ``candidate`` satisfies the canonical continuidad-id shape."""
    try:
        _CHAIN_ID_ADAPTER.validate_python(candidate)
    except ValidationError:
        return False
    return True


def _normalise(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return _WHITESPACE.sub(" ", folded).strip().rstrip(".,;:")


def derive_slug(title: str) -> str:
    """Fold an official programme title into the chain-id slug segment.

    Accent-strips, lowercases, and collapses every non-alphanumeric run to a
    single hyphen. ``ñ`` folds to ``n`` and the ordinal indicators ``º``/``ª``
    to ``o``/``a`` before stripping, so "150.º aniversario" and "4ª Edición"
    keep a readable slug instead of losing the ordinal entirely.
    """
    decomposed = unicodedata.normalize("NFKD", title)
    stripped = "".join(char for char in decomposed if not unicodedata.combining(char))
    folded = stripped.replace("ñ", "n").replace("Ñ", "n").replace("º", "o").replace("ª", "a")
    slug = _NON_SLUG.sub("-", folded.lower()).strip("-")
    return _SLUG_RUNS.sub("-", slug)


def chain_id_for(slug: str, *, column: str = CHAIN_COLUMN_LEAF) -> str:
    """Compose the full continuity chain id for one event slug."""
    return f"{CHAIN_PREFIX}{slug}-{column}"
