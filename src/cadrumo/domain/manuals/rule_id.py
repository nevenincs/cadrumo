"""Deterministic rule-id generation for :mod:`cadrumo.domain.manuals`.

Rule identifiers are locked at the schema layer so subsequent
extraction runs cannot collide with each other. The generator is pure
and fully deterministic given its inputs.
"""

from __future__ import annotations

import re

from ._ids import ManualId, ManualPart
from .errors import ManualValidationError

_ID_CHAR_RE = re.compile(r"[^a-z0-9-]+")


def _slug(value: str) -> str:
    """Lower-case and strip to kebab-case characters only."""
    return _ID_CHAR_RE.sub("-", value.lower()).strip("-")


def generate_rule_id(
    *,
    manual_id: ManualId,
    year: int,
    part: ManualPart,
    chapter_id: str,
    section_id: str,
    ordinal: int,
) -> str:
    """Return the deterministic identifier for a rule.

    The shape is
    ``{manual_id}-{year}-[{part}-]{chapter_id}-{section_id}-rule{ordinal:04d}``,
    where the ``part`` segment is collapsed for ``ManualPart.SINGLE`` so
    IVA rule IDs stay compact.

    Args:
        manual_id: Handbook identifier.
        year: Tax year the manual applies to.
        part: Volume split within the year.
        chapter_id: Stable kebab-case chapter identifier.
        section_id: Stable kebab-case section identifier.
        ordinal: 1-indexed position of the rule within its section.

    Returns:
        A deterministic lower-case kebab-case rule identifier.

    Raises:
        ManualValidationError: If ``ordinal`` is not a positive integer or
            any of the identifier components is empty after slugging.
    """
    if ordinal < 1:
        raise ManualValidationError(f"ordinal must be >= 1, got {ordinal}")

    chapter_slug = _slug(chapter_id)
    section_slug = _slug(section_id)
    if not chapter_slug:
        raise ManualValidationError("chapter_id is empty after slugging")
    if not section_slug:
        raise ManualValidationError("section_id is empty after slugging")

    segments: list[str] = [manual_id.value, str(year)]
    if part is not ManualPart.SINGLE:
        segments.append(part.value)
    segments.extend([chapter_slug, section_slug, f"rule{ordinal:04d}"])
    return "-".join(segments)
