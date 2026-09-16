"""The edition-independent lineage of a formula or binding identifier.

A formula or binding is redeclared by every edition that uses it, so the same
declaration in two editions is recognised by its lineage, not by its
identifier. An identifier may embed the key of the edition that declares it,
as in ``modelo-131-2024-cuota`` beside ``modelo-131-2019-2023-cuota``. Its
lineage is the identifier with that edition's own revision identifier replaced
by a fixed placeholder wherever it sits as a whole segment, bounded by an
identifier separator or by either end of the identifier.

Identifiers that do not embed their edition's key are their own lineage, so for
them the function is the identity. The placeholder cannot occur in a registry
identifier, so within one edition the mapping is injective: two distinct
identifiers of the same edition never share a lineage.

Only the declaring edition's own key is replaced. A segment naming some other
edition is part of the lineage, because nothing here can tell a stale key from
a deliberate reference to another edition's declaration.
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Final

EDITION_PLACEHOLDER: Final = "<edition>"
"""Stands in for the declaring edition's key; ``<`` and ``>`` are outside the registry identifier grammar."""

_IDENTIFIER_SEPARATORS: Final = "-._:"


def identifier_lineage(identifier: str, revision_id: str) -> str:
    """Return ``identifier`` with ``revision_id`` replaced by :data:`EDITION_PLACEHOLDER` as a whole segment.

    Args:
        identifier: A formula or binding identifier as the edition declares or references it.
        revision_id: The edition the identifier belongs to.

    Returns:
        The identifier's lineage; ``identifier`` itself when it does not embed ``revision_id``.
    """
    return _edition_segment(revision_id).sub(EDITION_PLACEHOLDER, identifier)


@lru_cache(maxsize=512)
def _edition_segment(revision_id: str) -> re.Pattern[str]:
    separators = re.escape(_IDENTIFIER_SEPARATORS)
    return re.compile(rf"(?<![^{separators}]){re.escape(revision_id)}(?![^{separators}])")
