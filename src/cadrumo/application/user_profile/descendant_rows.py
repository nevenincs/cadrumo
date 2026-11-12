"""Atomic replacement of a profile's declared descendant family.

A replacement states the whole family: the rows, their count and the clearing of every
row it no longer holds are one write against one exact custody revision. Every refusal
names the row by its position and never echoes what was typed, so the sentence served
for it discloses nothing the person did not already see. A caller may instead name
one row to add, or the stored index of one row to remove; the family is then
composed from the rows stored at the expected revision, so the people left alone are
rewritten from storage with every leaf they state, and the same validation and write
publish it.

Core types: :class:`~cadrumo.domain.user_profile.values.UserProfileRecord`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, NoReturn

from pydantic import BaseModel, Field, field_validator

from ...core.errors.hierarchy import ProfileAnswerTypeError, pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.identity.documents import IdentityError
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.governed_fact_scope import GovernedFactSource, validating_governed_facts
from ...domain.contribuyente.descendant import DescendantInfo
from ...domain.contribuyente.descendant_facts import descendant_facts_from_list, descendant_list_from_facts
from ...domain.contribuyente.household_person_name import admitted_household_person_name, household_person_name_limit
from ...domain.user_profile.errors import UserProfileValidationError
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from .capsule_record import ProfileRecordConflictError
from .fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from .household_person_tax_id import canonical_person_tax_id
from .household_row_limit import declared_household_row_limit
from .profile_record_repository import ProfileRecordRepository
from .projections import record_to_effective_facts

DESCENDANT_OBJECT_PATH: Final = "renta_family.descendiente"
DESCENDANT_COUNT_PATH: Final = "renta_family.descendientes_count"

_BIRTH_DATE_LEAF: Final = "birth_date"
_NIF_LEAF: Final = "nif"
_NAME_LEAF: Final = "apellidos_nombre"

_ROWS_OVER_LIMIT_LOCALE_KEY: Final = "application.user_profile.errors.descendant_rows_over_limit"
_LIMIT_UNKNOWN_LOCALE_KEY: Final = "application.user_profile.errors.descendant_limit_unknown"
_BIRTH_DATE_REQUIRED_LOCALE_KEY: Final = "application.user_profile.errors.descendant_birth_date_required"
_NIF_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.descendant_nif_invalid"
_NAME_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.descendant_name_invalid"
_VALUE_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.descendant_value_invalid"
_FACT_UNSUPPORTED_LOCALE_KEY: Final = "application.user_profile.errors.descendant_fact_unsupported"
_ROW_NOT_STORED_LOCALE_KEY: Final = "application.user_profile.errors.descendant_row_not_stored"


class ProfileDescendantFact(BaseModel):
    """One canonical descendant field token and private textual value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=128)
    value: str = Field(min_length=1, max_length=4096, repr=False)


class ProfileDescendantRow(BaseModel):
    """A complete row whose vocabulary is validated by the execution authority."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    facts: tuple[ProfileDescendantFact, ...] = Field(min_length=1, max_length=128, repr=False)

    @field_validator("facts")
    @classmethod
    @pydantic_validation_boundary
    def _distinct_fields(cls, facts: tuple[ProfileDescendantFact, ...]) -> tuple[ProfileDescendantFact, ...]:
        if len({fact.field_key for fact in facts}) != len(facts):
            raise ValueError("descendant row must not repeat a field")
        return facts


def encode_descendant_rows(
    descendants: tuple[DescendantInfo, ...], *, authority: GovernedFactSource
) -> tuple[ProfileDescendantRow, ...]:
    """Project canonical domain records to strict public operation row values."""
    return tuple(
        ProfileDescendantRow(
            facts=tuple(
                ProfileDescendantFact(field_key=path.removeprefix("renta_family.descendiente.0."), value=value)
                for path, value in descendant_facts_from_list((row,), authority=authority)
                if path.startswith("renta_family.descendiente.0.")
            )
        )
        for row in descendants
    )


def _refuse(message_key: str, **context: object) -> NoReturn:
    raise UserProfileValidationError(translated_message=message_key, context=context)


# The two readings below return ``None`` instead of refusing inside their handlers: an exception raised in a handler
# keeps the handled one as its context, and the handled errors quote the typed value.
def _canonical_nif(raw: str, *, operation: PinnedAuthorityOperation) -> str | None:
    try:
        return canonical_person_tax_id(raw, operation=operation)
    except IdentityError:
        return None


def _person_name(raw: str, *, position: int, operation: PinnedAuthorityOperation) -> str:
    admitted = admitted_household_person_name(raw, authority=operation)
    if admitted is None:
        _refuse(_NAME_INVALID_LOCALE_KEY, row=position, limit=household_person_name_limit(authority=operation))
    return admitted


def _decoded_descendants(
    supplied: dict[str, str], *, operation: PinnedAuthorityOperation
) -> tuple[DescendantInfo, ...] | None:
    try:
        return descendant_list_from_facts(supplied, authority=operation)
    except (ProfileAnswerTypeError, RegistryValidationError, ValueError):
        return None


def _validated_descendant_row(
    row: ProfileDescendantRow, *, position: int, operation: PinnedAuthorityOperation
) -> tuple[DescendantInfo, dict[str, str]]:
    """Validate one row alone and return its record with its canonical leaves.

    The record itself checks a NIF only for width, so the control letter is
    enforced here through the identifier check ascendants use, and the stored NIF
    is its canonical form. The name is stored with its whitespace collapsed and is
    refused here, by its own sentence, when blank or longer than the design admits.
    The domain decoder drops a leaf it does not know and a row without a birth
    date, so each is checked against what the decoder kept:
    nothing the person stated may disappear or change form on its way into the
    profile.
    """
    supplied = {f"{DESCENDANT_OBJECT_PATH}.0.{fact.field_key}": fact.value for fact in row.facts}
    if f"{DESCENDANT_OBJECT_PATH}.0.{_BIRTH_DATE_LEAF}" not in supplied:
        _refuse(_BIRTH_DATE_REQUIRED_LOCALE_KEY, row=position)
    nif_path = f"{DESCENDANT_OBJECT_PATH}.0.{_NIF_LEAF}"
    if nif_path in supplied:
        canonical_nif = _canonical_nif(supplied[nif_path], operation=operation)
        if canonical_nif is None:
            _refuse(_NIF_INVALID_LOCALE_KEY, row=position)
        supplied[nif_path] = canonical_nif
    name_path = f"{DESCENDANT_OBJECT_PATH}.0.{_NAME_LEAF}"
    if name_path in supplied:
        supplied[name_path] = _person_name(supplied[name_path], position=position, operation=operation)
    decoded = _decoded_descendants(supplied, operation=operation)
    if decoded is None:
        _refuse(_VALUE_INVALID_LOCALE_KEY, row=position)
    if len(decoded) != 1:
        _refuse(_BIRTH_DATE_REQUIRED_LOCALE_KEY, row=position)
    stored = dict(descendant_facts_from_list(decoded, authority=operation))
    if any(stored.get(path) != value for path, value in supplied.items()):
        _refuse(_FACT_UNSUPPORTED_LOCALE_KEY, row=position)
    stored.pop(DESCENDANT_COUNT_PATH)
    return decoded[0], stored


def _validated_descendant_facts(
    descendants: tuple[ProfileDescendantRow, ...], operation: PinnedAuthorityOperation
) -> tuple[tuple[DescendantInfo, ...], dict[str, str]]:
    """Return the family's records and its canonical ``path -> value`` facts, count included."""
    limit = declared_household_row_limit(operation, object_path=DESCENDANT_OBJECT_PATH)
    if limit is None:
        _refuse(_LIMIT_UNKNOWN_LOCALE_KEY)
    if len(descendants) > limit:
        _refuse(_ROWS_OVER_LIMIT_LOCALE_KEY, limit=limit, count=len(descendants))
    records: list[DescendantInfo] = []
    pairs: dict[str, str] = {}
    for index, row in enumerate(descendants):
        record, stored = _validated_descendant_row(row, position=index + 1, operation=operation)
        records.append(record)
        prefix = f"{DESCENDANT_OBJECT_PATH}.0."
        pairs.update(
            {f"{DESCENDANT_OBJECT_PATH}.{index}.{path.removeprefix(prefix)}": value for path, value in stored.items()}
        )
    pairs[DESCENDANT_COUNT_PATH] = str(len(records))
    return tuple(records), pairs


def _replaced_descendant_facts(current: UserProfileRecord, pairs: dict[str, str]) -> tuple[UserProfileFact, ...]:
    stale_paths = {
        fact.path
        for fact in current.facts
        if fact.path.startswith(f"{DESCENDANT_OBJECT_PATH}.") or fact.path == DESCENDANT_COUNT_PATH
    }
    return (
        *(UserProfileFact(path=path, value=None) for path in sorted(stale_paths - pairs.keys())),
        *(UserProfileFact(path=path, value=value) for path, value in pairs.items()),
    )


def _stored_leaves_without(current: UserProfileRecord, remove_row_index: str | None) -> dict[str, str]:
    """The effective stored leaves, less the row at ``remove_row_index``; a row that holds nothing is refused."""
    stored = {path: fact.value for path, fact in record_to_effective_facts(current).items() if fact.value is not None}
    if remove_row_index is None:
        return stored
    prefix = f"{DESCENDANT_OBJECT_PATH}.{remove_row_index}."
    if not any(path.startswith(prefix) and value.strip() for path, value in stored.items()):
        _refuse(_ROW_NOT_STORED_LOCALE_KEY)
    return {path: value for path, value in stored.items() if not path.startswith(prefix)}


def _composed_descendants(
    current: UserProfileRecord,
    *,
    descendants: tuple[ProfileDescendantRow, ...] | None,
    add_row: ProfileDescendantRow | None,
    remove_row_index: str | None,
    operation: PinnedAuthorityOperation,
) -> tuple[ProfileDescendantRow, ...]:
    """The family a change states: the family itself, or the stored rows less one removed and plus one added.

    The stored rows are read from the effective facts, so a leaf the operator cleared is not written back.
    """
    if descendants is not None:
        return descendants
    stored = _stored_leaves_without(current, remove_row_index)
    kept = encode_descendant_rows(descendant_list_from_facts(stored, authority=operation), authority=operation)
    return (*kept, *(() if add_row is None else (add_row,)))


@dataclass(frozen=True, slots=True)
class DescendantFamilyMutation:
    """Published revision and actual change, without duplicating private rows."""

    record: UserProfileRecord
    total: int
    changed: bool


def replace_profile_descendants(
    *,
    profile_id: str,
    descendants: tuple[ProfileDescendantRow, ...] | None = None,
    add_row: ProfileDescendantRow | None = None,
    remove_row_index: str | None = None,
    expected_revision: int,
    expected_content_digest: ContentDigest,
    operation: PinnedAuthorityOperation,
) -> DescendantFamilyMutation:
    """Validate and replace the whole family against one exact custody revision.

    The family is ``descendants`` when given; otherwise it is the rows stored at
    that revision, without the row stored at ``remove_row_index`` and with
    ``add_row`` appended. The count and orphaned optional/indexed fields belong
    to the same write. Revalidation uses the execution owner's authority even
    when the frontend has already constructed domain records under another
    publication.
    """
    decode = operation.profile_decode_context()
    current = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
    if current.record_revision != expected_revision or current.content_digest != expected_content_digest:
        raise ProfileRecordConflictError("descendant family replacement baseline is stale")
    with validating_governed_facts(operation):
        rows = _composed_descendants(
            current,
            descendants=descendants,
            add_row=add_row,
            remove_row_index=remove_row_index,
            operation=operation,
        )
        validated, pairs = _validated_descendant_facts(rows, operation)
        changes = _replaced_descendant_facts(current, pairs)
        published = apply_profile_fact_changes(
            profile_id=profile_id,
            changes=changes,
            door=ProfileFactWriteDoor.MANAGER_DESCENDANTS,
            expected_record=current,
            profile_decode_context=decode,
        )
    return DescendantFamilyMutation(
        record=published,
        total=len(validated),
        changed=published.record_revision != current.record_revision,
    )
