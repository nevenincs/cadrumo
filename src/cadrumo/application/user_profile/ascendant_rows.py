"""Atomic replacement of a profile's declared ascendants.

Ascendants are stored as ``renta_family.ascendiente.{n}.{leaf}`` facts with
``renta_family.ascendientes_count``, the household shape the Modelo 100 bindings
read. A replacement states the whole set: the rows, their count and the clearing
of every row it no longer holds are one write against one exact custody revision,
so a stated zero is a real answer and a person left out is removed. A caller may
instead name one row to add, or the stored index of one row to remove; the set is
then composed from the rows stored at the expected revision, so the people left
alone are rewritten from storage with every leaf they state, and the same
validation and write publish it.

The leaves are the ones an ascendant row can state and the declaration reads: the
NIF or NIE, the surnames and name, the date of birth, the date of death and the number
of descendants the ascendant lives with. The row limit is the one the declaration's own design states.
Every refusal names the row by its position and never echoes what was typed;
:class:`UserProfileRecord`, the stored taxpayer profile record.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from typing import TYPE_CHECKING, Final, NoReturn

from pydantic import BaseModel, Field, field_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.identity.digest import ContentDigest
from ...core.identity.documents import IdentityError
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.parsing.dates import require_iso8601_date
from ...domain.calculations.registry.form_codes import resolve_form_codes
from ...domain.calculations.registry.governed_fact_scope import validating_governed_facts
from ...domain.contribuyente.household_person_name import admitted_household_person_name, household_person_name_limit
from ...domain.user_profile.errors import UserProfileValidationError
from ...domain.user_profile.values import UserProfileFact, UserProfileRecord
from .edit_baseline import require_profile_edit_baseline
from .fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from .household_person_tax_id import canonical_person_tax_id
from .household_row_limit import declared_household_row_limit
from .profile_record_repository import ProfileRecordRepository
from .projections import record_to_effective_facts

if TYPE_CHECKING:
    from ...domain.calculations.registry.authority import PinnedAuthorityOperation

ASCENDANT_OBJECT_PATH: Final = "renta_family.ascendiente"
ASCENDANT_COUNT_PATH: Final = "renta_family.ascendientes_count"

_NIF_LEAF: Final = "nif"
_NAME_LEAF: Final = "apellidos_nombre"
_BIRTH_DATE_LEAF: Final = "birth_date"
_DEATH_DATE_LEAF: Final = "fallecimiento"
_COHABITING_LEAF: Final = "convivientes"
_COHABITING_BOUND_KEY: Final = "m100.ascendant_cohabiting_descendants_max"
_FORM_ROW_CODES_FACT: Final = "form-row-codes"

_ROWS_OVER_LIMIT_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_rows_over_limit"
_LIMIT_UNKNOWN_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_limit_unknown"
_FACT_UNSUPPORTED_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_fact_unsupported"
_BIRTH_DATE_REQUIRED_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_birth_date_required"
_BIRTH_DATE_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_birth_date_invalid"
_DEATH_DATE_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_death_date_invalid"
_DEATH_BEFORE_BIRTH_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_death_before_birth"
_NIF_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_nif_invalid"
_NAME_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_name_invalid"
_COHABITING_INVALID_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_convivientes_invalid"
_ROW_NOT_STORED_LOCALE_KEY: Final = "application.user_profile.errors.ascendant_row_not_stored"

_LEAF_ORDER: Final = (_NIF_LEAF, _NAME_LEAF, _BIRTH_DATE_LEAF, _DEATH_DATE_LEAF, _COHABITING_LEAF)


class ProfileAscendantFact(BaseModel):
    """One ascendant leaf token and its private textual value."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    field_key: str = Field(pattern=r"^[a-z][a-z0-9_]*$", max_length=128)
    value: str = Field(min_length=1, max_length=4096, repr=False)


class ProfileAscendantRow(BaseModel):
    """A complete ascendant row whose leaves the execution authority validates."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    facts: tuple[ProfileAscendantFact, ...] = Field(min_length=1, max_length=64, repr=False)

    @field_validator("facts")
    @classmethod
    @pydantic_validation_boundary
    def _distinct_fields(cls, facts: tuple[ProfileAscendantFact, ...]) -> tuple[ProfileAscendantFact, ...]:
        if len({fact.field_key for fact in facts}) != len(facts):
            raise ValueError("ascendant row must not repeat a field")
        return facts


_STORED_LEAF_PATTERN: Final = re.compile(rf"^{re.escape(ASCENDANT_OBJECT_PATH)}\.(\d+)\.([a-z0-9_]+)$")


def ascendant_rows_from_facts(facts: Mapping[str, str]) -> tuple[ProfileAscendantRow, ...]:
    """Read the stored ascendant rows back, in stored order, as the rows a replacement takes.

    Only the leaves a row can state are read, so a stale foreign leaf never rides into a
    replacement; a row that states no leaf is not a row. The values are the canonical stored
    ones, and the replacement validates them again.
    """
    stored: dict[int, dict[str, str]] = {}
    for path, value in facts.items():
        match = _STORED_LEAF_PATTERN.match(path)
        if match is not None and match.group(2) in _LEAF_ORDER and value.strip():
            stored.setdefault(int(match.group(1)), {})[match.group(2)] = value
    return tuple(
        ProfileAscendantRow(
            facts=tuple(
                ProfileAscendantFact(field_key=leaf, value=leaves[leaf]) for leaf in _LEAF_ORDER if leaf in leaves
            )
        )
        for _, leaves in sorted(stored.items())
    )


def _refuse(message_key: str, **context: object) -> NoReturn:
    raise UserProfileValidationError(translated_message=message_key, context=context)


# The readings below return ``None`` instead of refusing inside their handlers: an exception raised in a handler
# keeps the handled one as its context, and the handled errors quote the typed value.
def _canonical_nif(raw: str, *, operation: PinnedAuthorityOperation) -> str | None:
    try:
        return canonical_person_tax_id(raw, operation=operation)
    except IdentityError:
        return None


def _iso_date(raw: str) -> date | None:
    try:
        return require_iso8601_date(raw)
    except ValueError:
        return None


def _tax_id(raw: str, *, position: int, operation: PinnedAuthorityOperation) -> str:
    """Admit a NIF or NIE whose checksum holds; an ascendant is a person, never an entity."""
    canonical = _canonical_nif(raw, operation=operation)
    if canonical is None:
        _refuse(_NIF_INVALID_LOCALE_KEY, row=position)
    return canonical


def _date(raw: str, *, position: int, message_key: str) -> date:
    parsed = _iso_date(raw)
    if parsed is None:
        _refuse(message_key, row=position)
    return parsed


def _person_name(raw: str, *, position: int, operation: PinnedAuthorityOperation) -> str:
    admitted = admitted_household_person_name(raw, authority=operation)
    if admitted is None:
        _refuse(_NAME_INVALID_LOCALE_KEY, row=position, limit=household_person_name_limit(authority=operation))
    return admitted


def _cohabiting(raw: str, *, position: int, operation: PinnedAuthorityOperation) -> str:
    limit = resolve_form_codes(_FORM_ROW_CODES_FACT, authority=operation).integer(_COHABITING_BOUND_KEY)
    text = raw.strip()
    if not (text.isascii() and text.isdigit()) or int(text) > limit:
        _refuse(_COHABITING_INVALID_LOCALE_KEY, row=position, limit=limit)
    return str(int(text))


def _row_facts(row: ProfileAscendantRow, *, position: int, operation: PinnedAuthorityOperation) -> dict[str, str]:
    """Validate one row's leaves and return them in their canonical stored form."""
    supplied = {fact.field_key: fact.value for fact in row.facts}
    if not supplied.keys() <= set(_LEAF_ORDER):
        _refuse(_FACT_UNSUPPORTED_LOCALE_KEY, row=position)
    if _BIRTH_DATE_LEAF not in supplied:
        _refuse(_BIRTH_DATE_REQUIRED_LOCALE_KEY, row=position)
    stored: dict[str, str] = {}
    birth = _date(supplied[_BIRTH_DATE_LEAF], position=position, message_key=_BIRTH_DATE_INVALID_LOCALE_KEY)
    if _NIF_LEAF in supplied:
        stored[_NIF_LEAF] = _tax_id(supplied[_NIF_LEAF], position=position, operation=operation)
    if _NAME_LEAF in supplied:
        stored[_NAME_LEAF] = _person_name(supplied[_NAME_LEAF], position=position, operation=operation)
    stored[_BIRTH_DATE_LEAF] = birth.isoformat()
    if _DEATH_DATE_LEAF in supplied:
        death = _date(supplied[_DEATH_DATE_LEAF], position=position, message_key=_DEATH_DATE_INVALID_LOCALE_KEY)
        if death < birth:
            _refuse(_DEATH_BEFORE_BIRTH_LOCALE_KEY, row=position)
        stored[_DEATH_DATE_LEAF] = death.isoformat()
    if _COHABITING_LEAF in supplied:
        stored[_COHABITING_LEAF] = _cohabiting(supplied[_COHABITING_LEAF], position=position, operation=operation)
    return stored


def _validated_ascendant_facts(
    ascendants: tuple[ProfileAscendantRow, ...], operation: PinnedAuthorityOperation
) -> dict[str, str]:
    """Return the canonical ``path -> value`` facts of the whole set, count included."""
    limit = declared_household_row_limit(operation, object_path=ASCENDANT_OBJECT_PATH)
    if limit is None:
        _refuse(_LIMIT_UNKNOWN_LOCALE_KEY)
    if len(ascendants) > limit:
        _refuse(_ROWS_OVER_LIMIT_LOCALE_KEY, limit=limit, count=len(ascendants))
    pairs: dict[str, str] = {}
    for index, row in enumerate(ascendants):
        stored = _row_facts(row, position=index + 1, operation=operation)
        pairs.update(
            {f"{ASCENDANT_OBJECT_PATH}.{index}.{leaf}": stored[leaf] for leaf in _LEAF_ORDER if leaf in stored}
        )
    pairs[ASCENDANT_COUNT_PATH] = str(len(ascendants))
    return pairs


def _replaced_ascendant_facts(current: UserProfileRecord, pairs: dict[str, str]) -> tuple[UserProfileFact, ...]:
    stale_paths = {
        fact.path
        for fact in current.facts
        if fact.path.startswith(f"{ASCENDANT_OBJECT_PATH}.") or fact.path == ASCENDANT_COUNT_PATH
    }
    return (
        *(UserProfileFact(path=path, value=None) for path in sorted(stale_paths - pairs.keys())),
        *(UserProfileFact(path=path, value=value) for path, value in pairs.items()),
    )


def _composed_ascendants(
    current: UserProfileRecord,
    *,
    ascendants: tuple[ProfileAscendantRow, ...] | None,
    add_row: ProfileAscendantRow | None,
    remove_row_index: str | None,
) -> tuple[ProfileAscendantRow, ...]:
    """The whole set a change states: the set itself, or the stored rows less one removed and plus one added.

    The stored rows are read from the effective facts, so a leaf the operator cleared is not written back.
    """
    if ascendants is not None:
        return ascendants
    stored = {path: fact.value for path, fact in record_to_effective_facts(current).items() if fact.value is not None}
    if remove_row_index is not None:
        prefix = f"{ASCENDANT_OBJECT_PATH}.{remove_row_index}."
        if not any(path.startswith(prefix) and value.strip() for path, value in stored.items()):
            _refuse(_ROW_NOT_STORED_LOCALE_KEY)
        stored = {path: value for path, value in stored.items() if not path.startswith(prefix)}
    return (*ascendant_rows_from_facts(stored), *(() if add_row is None else (add_row,)))


@dataclass(frozen=True, slots=True)
class AscendantFamilyMutation:
    """Published revision and actual change, without duplicating private rows."""

    record: UserProfileRecord
    total: int
    changed: bool


def replace_profile_ascendants(
    *,
    profile_id: str,
    ascendants: tuple[ProfileAscendantRow, ...] | None = None,
    add_row: ProfileAscendantRow | None = None,
    remove_row_index: str | None = None,
    expected_revision: int,
    expected_content_digest: ContentDigest,
    operation: PinnedAuthorityOperation,
) -> AscendantFamilyMutation:
    """Validate and replace the whole set of ascendants against one exact custody revision.

    The set is ``ascendants`` when given; otherwise it is the rows stored at that
    revision, without the row stored at ``remove_row_index`` and with ``add_row``
    appended. The count and every orphaned row fact belong to the same write.
    Validation runs before publication, so a refused set leaves the record untouched.

    Raises:
        ProfileRecordConflictError: The profile moved past the expected revision or digest.
        UserProfileValidationError: A row or the set is outside what the declaration holds,
            or no row is stored at ``remove_row_index``.
    """
    decode = operation.profile_decode_context()
    current = ProfileRecordRepository.for_current_session(profile_id, profile_decode_context=decode).load(profile_id)
    require_profile_edit_baseline(
        current,
        expected_revision=expected_revision,
        expected_content_digest=expected_content_digest,
        field_paths=(ASCENDANT_COUNT_PATH,),
    )
    rows = _composed_ascendants(current, ascendants=ascendants, add_row=add_row, remove_row_index=remove_row_index)
    with validating_governed_facts(operation):
        pairs = _validated_ascendant_facts(rows, operation)
        published = apply_profile_fact_changes(
            profile_id=profile_id,
            changes=_replaced_ascendant_facts(current, pairs),
            door=ProfileFactWriteDoor.MANAGER_ASCENDANTS,
            expected_record=current,
            profile_decode_context=decode,
        )
    return AscendantFamilyMutation(
        record=published,
        total=len(rows),
        changed=published.record_revision != current.record_revision,
    )


__all__ = [
    "ASCENDANT_COUNT_PATH",
    "ASCENDANT_OBJECT_PATH",
    "AscendantFamilyMutation",
    "ProfileAscendantFact",
    "ProfileAscendantRow",
    "ascendant_rows_from_facts",
    "replace_profile_ascendants",
]
