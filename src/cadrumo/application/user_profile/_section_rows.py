"""Adding one row to a repeatable profile section.

A repeatable section's rows live at ``section.INDEX.field``, and the write
door judges a whole fact batch at once: every required field of a row must
arrive together or none of it lands. That judgement is
:func:`~cadrumo.application.user_profile.reject_invalid_profile_facts`, which
every door shares and which judges "the whole resulting fact sequence rather
than the incoming change alone, so a patch is never left half-applied by a
later field's refusal"; row writes reach it through
:func:`~cadrumo.application.user_profile.apply_profile_fact_changes`.
That makes row creation a batch operation rather than a sequence of field
edits, so what a surface needs is the index a new row may occupy and the
facts that fill it -- both derived from the schema's own
:class:`~cadrumo.domain.user_profile.ProfileSectionDefinition` rather than
from a path convention restated per caller.

This is deliberately surface-free: it returns
:class:`~cadrumo.domain.user_profile.UserProfileFact` objects and never
opens the write door itself, so the manager action and any later command
addressing the same sections assemble rows identically instead of growing a
second answer about what a row is.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING

from ...domain.user_profile import UserProfileFact
from ._completeness import profile_section_rows

if TYPE_CHECKING:
    from ...domain.user_profile import ProfileSectionDefinition


def next_section_row_index(section_key: str, present: Iterable[str]) -> int:
    """Return the row index a new row of ``section_key`` may occupy.

    Row identity is :func:`~cadrumo.application.user_profile.profile_section_rows`,
    the same reading the completeness check and the manager's page already
    share, so a new row is numbered against the rows those two surfaces
    agree exist rather than against a fresh scan of the fact paths.

    Index ``0`` is reserved whenever the section holds an UNINDEXED row.
    The setup wizard writes one -- ``activities.description`` with no index
    -- so an operator who completed setup already has an activity that
    ``profile_section_rows`` reports under the ``""`` key. Numbering the
    next row ``0`` would leave that implicit row sitting beside an
    explicitly numbered one, and would collide with it outright if the
    implicit spelling were ever normalised to ``activities.0.*``: two rows
    would merge into one and an activity would vanish. Treating the
    implicit row as the occupant of slot ``0`` keeps the count honest now
    and leaves the normalisation reversible later.

    Args:
        section_key: The repeatable section a row is being added to.
        present: Paths carrying a value, by the shared presence rule -- so a
            row whose every field is blank is not a row here, and its index
            is free to reuse.

    Returns:
        An index no existing row occupies: one above the highest in use, and
        never below the floor the implicit row reserves. A gap left by a
        blanked-out row is NOT reclaimed -- reusing it would silently give a
        new row the identity a reader may still hold from before.
    """
    rows = profile_section_rows(section_key, present)
    indexed = tuple(int(row) for row in rows if row)
    floor = 1 if "" in rows else 0
    return max(floor, max(indexed) + 1 if indexed else 0)


def section_row_facts(
    section: ProfileSectionDefinition,
    *,
    row_index: int,
    values: Mapping[str, str],
) -> tuple[UserProfileFact, ...]:
    """Project one row's collected values into facts at ``section.INDEX.field``.

    ``values`` is keyed by FIELD key, not by path: a caller collecting a row
    is answering "what goes in this row", and the row it belongs to is
    ``row_index``. Keys naming no declared field are ignored, so a surface
    carrying its own bookkeeping entries alongside the answers does not
    persist them.

    A blank value yields NO fact rather than a fact carrying ``None``. On a
    new row there is nothing to clear, and a null fact would make an
    unanswered optional field indistinguishable from one deliberately
    emptied. A blank REQUIRED field is therefore not refused here -- it
    simply does not arrive, and the write door refuses the incomplete row
    naming exactly what is missing, which keeps one authority over what a
    complete row is.

    Fields are emitted in declaration order, so the batch reads in the same
    order the section is displayed.

    Args:
        section: The repeatable section being added to.
        row_index: The row these values fill, from
            :func:`next_section_row_index`.
        values: Collected values keyed by field key.

    Returns:
        The facts filling the row, empty when every value was blank.
    """
    facts: list[UserProfileFact] = []
    for field in section.fields:
        value = values.get(field.key, "").strip()
        if not value:
            continue
        facts.append(UserProfileFact(path=f"{section.key}.{row_index}.{field.key}", value=value))
    return tuple(facts)


__all__ = [
    "next_section_row_index",
    "section_row_facts",
]
