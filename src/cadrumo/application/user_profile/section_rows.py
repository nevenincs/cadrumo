"""Adding one row to a repeatable profile section.

A repeatable section's rows live at ``section.INDEX.field``, and the write
door judges a whole fact batch at once: every required field of a row must
arrive together or none of it lands. That judgement is
:func:`~cadrumo.application.user_profile.validation.reject_invalid_profile_facts`, which
every door shares and which judges "the whole resulting fact sequence rather
than the incoming change alone, so a patch is never left half-applied by a
later field's refusal"; row writes reach it through
:func:`~cadrumo.application.user_profile.fact_write.apply_profile_fact_changes`.
That makes row creation a batch operation rather than a sequence of field
edits, so what a surface needs is the index a new row may occupy and the
facts that fill it -- both derived from the schema's own
:class:`~cadrumo.domain.user_profile.schema.ProfileSectionDefinition` rather than
from a path convention restated per caller.

The application-owned row mutation below composes those two pure helpers with
the canonical fact write door. Frontends collect values but never allocate a
row or publish it themselves.

Core types:
:class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ...domain.user_profile.errors import ProfileSchemaValidationError
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from .completeness import profile_section_rows
from .fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from .profile_record_repository import ProfileRecordRepository
from .projections import record_to_path_values

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority_artifact import ProfileDecodeContext
    from ...domain.user_profile.schema import ProfileSchemaDefinition, ProfileSectionDefinition


@dataclass(frozen=True, slots=True)
class ProfileRepeatableRowMutationOutcome:
    """The exact encrypted record and row identity produced by one row addition."""

    record: UserProfileRecord
    section_key: str
    row_index: int


@dataclass(frozen=True, slots=True)
class ProfileRepeatableRowChangeOutcome:
    """Encrypted record and stable schema row key produced by update or removal."""

    record: UserProfileRecord
    section_key: str
    row_key: str
    changed: bool


def _repeatable_section(schema: ProfileSchemaDefinition, section_key: str) -> ProfileSectionDefinition:
    section = schema.section(section_key)
    if not section.repeatable:
        raise ProfileSchemaValidationError("profile row mutation requires a schema-declared repeatable section")
    return section


def _row_path(section_key: str, row_key: str, field_key: str) -> str:
    return f"{section_key}.{field_key}" if not row_key else f"{section_key}.{row_key}.{field_key}"


def _require_existing_row(section_key: str, row_key: str, current: UserProfileRecord) -> None:
    if row_key not in profile_section_rows(section_key, record_to_path_values(current)):
        raise ProfileSchemaValidationError(
            translated_message="application.user_profile.errors.row_not_found",
            context={"section": section_key, "row": row_key or "base"},
        )


def _validate_field_keys(
    section: ProfileSectionDefinition,
    *,
    values: Mapping[str, str],
    clear_fields: Iterable[str] = (),
) -> tuple[str, ...]:
    declared = {field.key for field in section.fields}
    clears = tuple(clear_fields)
    unknown = tuple(sorted(({*values} | set(clears)) - declared))
    if unknown:
        raise ProfileSchemaValidationError(
            translated_message="application.user_profile.errors.row_unknown_field",
            context={
                "section": section.key,
                "unknown": ", ".join(unknown),
                "fields": ", ".join(sorted(declared)),
            },
        )
    overlap = tuple(sorted(set(values) & set(clears)))
    if overlap:
        raise ProfileSchemaValidationError(
            "a repeatable-row field cannot be assigned and cleared in the same mutation",
            context={"section": section.key, "fields": ", ".join(overlap)},
        )
    blank = tuple(sorted(key for key, value in values.items() if not value.strip()))
    if blank:
        raise ProfileSchemaValidationError(
            "blank repeatable-row values are ambiguous; omit unchanged fields or clear them explicitly",
            context={"section": section.key, "fields": ", ".join(blank)},
        )
    return clears


def next_section_row_index(section_key: str, present: Iterable[str]) -> int:
    """Return the row index a new row of ``section_key`` may occupy.

    Row identity is :func:`~cadrumo.application.user_profile.completeness.profile_section_rows`,
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
        present: Paths whose identities have been allocated, including clear
            tombstones. A removed row's index stays occupied so a later add
            cannot acquire an identity retained by an older reader.

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


def add_profile_repeatable_section_row(
    *,
    profile_id: str,
    section_key: str,
    values: Mapping[str, str],
    schema: ProfileSchemaDefinition,
    profile_decode_context: ProfileDecodeContext,
) -> ProfileRepeatableRowMutationOutcome:
    """Allocate and publish one complete repeatable profile row atomically.

    The schema selects the section, the current encrypted record determines the
    next stable index, and the shared profile-fact writer owns the one atomic
    publication and bucket event. A frontend must supply only the field-keyed
    values it collected. ``schema`` must come from the enclosing pinned
    authority operation; this operation does not consult bundled authoring
    data.
    """
    section = _repeatable_section(schema, section_key)
    # Two different mistakes, refused apart. section_row_facts deliberately
    # ignores keys it does not declare, so a mistyped field used to arrive here
    # as "no populated field" -- which told an operator who had populated one
    # that they had not, and never mentioned the key that was wrong.
    _validate_field_keys(section, values=values)
    declared = {field.key for field in section.fields}
    current = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    ).load(profile_id)
    row_index = next_section_row_index(section.key, (fact.path for fact in current.facts))
    facts = section_row_facts(section, row_index=row_index, values=values)
    if not facts:
        raise ProfileSchemaValidationError(
            translated_message="application.user_profile.errors.row_all_values_blank",
            context={"section": section.key, "fields": ", ".join(sorted(declared))},
        )
    record = apply_profile_fact_changes(
        profile_id=profile_id,
        changes=facts,
        door=ProfileFactWriteDoor.MANAGER_ROW,
        expected_record=current,
        profile_decode_context=profile_decode_context,
    )
    return ProfileRepeatableRowMutationOutcome(record=record, section_key=section.key, row_index=row_index)


def update_profile_repeatable_section_row(
    *,
    profile_id: str,
    section_key: str,
    row_key: str,
    values: Mapping[str, str],
    clear_fields: Iterable[str],
    schema: ProfileSchemaDefinition,
    profile_decode_context: ProfileDecodeContext,
) -> ProfileRepeatableRowChangeOutcome:
    """Modify one stable row, retaining omissions and clearing only explicit fields."""
    section = _repeatable_section(schema, section_key)
    clears = _validate_field_keys(section, values=values, clear_fields=clear_fields)
    if not values and not clears:
        raise ProfileSchemaValidationError("repeatable-row update requires a value or explicit clear")
    repository = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    )
    current = repository.load(profile_id)
    _require_existing_row(section.key, row_key, current)
    changes = tuple(
        UserProfileFact(path=_row_path(section.key, row_key, field.key), value=values[field.key].strip())
        for field in section.fields
        if field.key in values
    ) + tuple(
        UserProfileFact(path=_row_path(section.key, row_key, field.key), value=None)
        for field in section.fields
        if field.key in clears
    )
    record = apply_profile_fact_changes(
        profile_id=profile_id,
        changes=changes,
        door=ProfileFactWriteDoor.MANAGER_ROW,
        expected_record=current,
        profile_decode_context=profile_decode_context,
    )
    return ProfileRepeatableRowChangeOutcome(
        record=record,
        section_key=section.key,
        row_key=row_key,
        changed=record.record_revision != current.record_revision,
    )


def remove_profile_repeatable_section_row(
    *,
    profile_id: str,
    section_key: str,
    row_key: str,
    schema: ProfileSchemaDefinition,
    profile_decode_context: ProfileDecodeContext,
) -> ProfileRepeatableRowChangeOutcome:
    """Remove one stable row by publishing explicit clear tombstones for its values."""
    section = _repeatable_section(schema, section_key)
    repository = ProfileRecordRepository.for_current_session(
        profile_id,
        profile_decode_context=profile_decode_context,
    )
    current = repository.load(profile_id)
    _require_existing_row(section.key, row_key, current)
    present = record_to_path_values(current)
    changes = tuple(
        UserProfileFact(path=path, value=None)
        for field in section.fields
        if (path := _row_path(section.key, row_key, field.key)) in present
    )
    record = apply_profile_fact_changes(
        profile_id=profile_id,
        changes=changes,
        door=ProfileFactWriteDoor.MANAGER_ROW,
        expected_record=current,
        profile_decode_context=profile_decode_context,
    )
    return ProfileRepeatableRowChangeOutcome(record=record, section_key=section.key, row_key=row_key, changed=True)


__all__ = [
    "ProfileRepeatableRowChangeOutcome",
    "ProfileRepeatableRowMutationOutcome",
    "add_profile_repeatable_section_row",
    "next_section_row_index",
    "remove_profile_repeatable_section_row",
    "section_row_facts",
    "update_profile_repeatable_section_row",
]
