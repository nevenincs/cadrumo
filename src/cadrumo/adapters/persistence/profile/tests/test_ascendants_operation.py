"""The ascendants operation replaces the whole set of ascendant rows in an encrypted profile.

These tests drive the operation's write function against a real encrypted
profile and read the result back through the stored record and the served
household rows, so the writer, the schema validation and the profile view are
checked to agree on one stored shape. Refusals are checked for the sentences the
operation serves in every language and for leaving the record untouched.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from cadrumo.adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from cadrumo.application.operations.error_detail import build_operation_error_detail
from cadrumo.application.user_profile.ascendant_rows import (
    AscendantFamilyMutation,
    ProfileAscendantFact,
    ProfileAscendantRow,
    replace_profile_ascendants,
)
from cadrumo.application.user_profile.capsule_record import ProfileRecordConflictError
from cadrumo.application.user_profile.fact_write import ProfileFactWriteDoor, apply_profile_fact_changes
from cadrumo.application.user_profile.family_rows import (
    ProfileFamilyGroupState,
    ProfileViewFamilyGroupItem,
    ProfileViewFamilyRowItem,
    family_row_items,
)
from cadrumo.application.user_profile.household_row_limit import declared_household_row_limit
from cadrumo.application.user_profile.login_session import authenticate_profile_for_invocation
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.registration import register_profile_with_credentials
from cadrumo.core.config import override_settings
from cadrumo.core.external_constants import OutputLanguage
from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.values import UserProfileFact, UserProfileRecord

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_OBJECT = "renta_family.ascendiente"
_COUNT = "renta_family.ascendientes_count"
# The 2025 Modelo 100 XSD declares Ascendiente with maxOccurs 4 and Hijo with maxOccurs 15.
_ASCENDANT_LIMIT = 4
_DESCENDANT_LIMIT = 15
_NIF = "12345678Z"
_NIE = "X0001500M"
_CIF = "B00015016"


def _row(**leaves: str) -> ProfileAscendantRow:
    return ProfileAscendantRow(
        facts=tuple(ProfileAscendantFact(field_key=key, value=value) for key, value in leaves.items())
    )


class _World:
    """One registered, authenticated profile and the authority the operation runs under."""

    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation

    def record(self) -> UserProfileRecord:
        return ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)

    def facts(self) -> dict[str, str]:
        return {
            fact.path: str(fact.value)
            for fact in self.record().facts
            if (fact.path.startswith(f"{_OBJECT}.") or fact.path == _COUNT) and fact.value is not None
        }

    def replace(self, *rows: ProfileAscendantRow, baseline: UserProfileRecord | None = None) -> AscendantFamilyMutation:
        current = baseline or self.record()
        return replace_profile_ascendants(
            profile_id=self.profile_id,
            ascendants=rows,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            operation=self.operation,
        )

    def served(self) -> tuple[ProfileViewFamilyGroupItem, tuple[ProfileViewFamilyRowItem, ...]]:
        record = self.record()
        values = {fact.path: str(fact.value) for fact in record.facts if fact.value is not None}
        items = family_row_items(values, schema=self.operation.profile_schema(), operation=self.operation)
        group = next(
            item for item in items if isinstance(item, ProfileViewFamilyGroupItem) and item.group_key == _OBJECT
        )
        rows = tuple(item for item in items if isinstance(item, ProfileViewFamilyRowItem) and item.group_key == _OBJECT)
        return group, rows


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"ascendants-operation-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Ascendants operation",
            passphrase=secret,
            profile_create_context=operation.profile_create_context(),
            profile_decode_context=operation.profile_decode_context(),
        )
        authenticate_profile_for_invocation(
            name=outcome.label,
            passphrase_callback=secret.__str__,
            profile_decode_context=operation.profile_decode_context(),
        )
        register_minimal_profile(profile_id=outcome.profile_id)
        yield _World(outcome.profile_id, operation)


def test_the_row_limit_is_the_one_the_design_declares(world: _World) -> None:
    assert declared_household_row_limit(world.operation, object_path=_OBJECT) == _ASCENDANT_LIMIT
    assert declared_household_row_limit(world.operation, object_path="renta_family.descendiente") == _DESCENDANT_LIMIT
    assert declared_household_row_limit(world.operation, object_path="renta_family.not_a_household") is None


def test_a_set_is_stored_as_rows_with_its_count_and_served_back(world: _World) -> None:
    before = world.record()

    mutation = world.replace(
        _row(nif="12345678z", birth_date="1948-03-04", convivientes="2"),
        _row(nif=_NIE, birth_date="1951-11-30", fallecimiento="2025-02-01"),
        _row(birth_date="1940-01-01"),
    )

    assert (mutation.total, mutation.changed) == (3, True)
    assert mutation.record.record_revision == before.record_revision + 1
    assert world.facts() == {
        _COUNT: "3",
        f"{_OBJECT}.0.nif": _NIF,
        f"{_OBJECT}.0.birth_date": "1948-03-04",
        f"{_OBJECT}.0.convivientes": "2",
        f"{_OBJECT}.1.nif": _NIE,
        f"{_OBJECT}.1.birth_date": "1951-11-30",
        f"{_OBJECT}.1.fallecimiento": "2025-02-01",
        f"{_OBJECT}.2.birth_date": "1940-01-01",
    }
    group, rows = world.served()
    assert (group.state, group.row_count, group.stated_count) == (ProfileFamilyGroupState.ROWS, 3, "3")
    assert [row.row_index for row in rows] == ["0", "1", "2"]
    assert {fact.leaf: fact.value for fact in rows[1].facts} == {
        "nif": _NIE,
        "birth_date": "1951-11-30",
        "fallecimiento": "2025-02-01",
    }


def test_the_same_set_again_publishes_nothing(world: _World) -> None:
    rows = (_row(nif=_NIF, birth_date="1948-03-04"),)
    world.replace(*rows)
    before = world.record()

    again = world.replace(*rows)

    assert (again.total, again.changed) == (1, False)
    assert again.record.record_revision == before.record_revision
    assert again.record.content_digest == before.content_digest


def test_a_smaller_set_clears_the_rows_it_no_longer_holds(world: _World) -> None:
    world.replace(
        _row(nif=_NIF, birth_date="1948-03-04", convivientes="1"),
        _row(nif=_NIE, birth_date="1951-11-30", fallecimiento="2025-02-01"),
    )

    world.replace(_row(birth_date="1951-11-30"))

    assert world.facts() == {_COUNT: "1", f"{_OBJECT}.0.birth_date": "1951-11-30"}
    group, rows = world.served()
    assert (group.state, group.row_count) == (ProfileFamilyGroupState.ROWS, 1)
    assert [fact.leaf for fact in rows[0].facts] == ["birth_date"]


def test_a_stated_zero_is_a_declared_empty_household_and_repeats_as_no_change(world: _World) -> None:
    world.replace(_row(nif=_NIF, birth_date="1948-03-04"))

    cleared = world.replace()

    assert (cleared.total, cleared.changed) == (0, True)
    assert world.facts() == {_COUNT: "0"}
    group, rows = world.served()
    assert (group.state, group.stated_count, group.row_count, rows) == (
        ProfileFamilyGroupState.NONE_DECLARED,
        "0",
        0,
        (),
    )
    assert world.replace().changed is False


def test_a_household_never_stated_stays_unknown(world: _World) -> None:
    group, rows = world.served()

    assert (group.state, group.stated_count, rows) == (ProfileFamilyGroupState.UNKNOWN, None, ())


def test_the_design_limit_is_accepted_and_one_more_is_refused(world: _World) -> None:
    full = tuple(_row(birth_date=f"19{40 + index}-01-01") for index in range(_ASCENDANT_LIMIT))
    assert world.replace(*full).total == _ASCENDANT_LIMIT
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(*full, _row(birth_date="1950-01-01"))

    assert refused.value.context == {"limit": _ASCENDANT_LIMIT, "count": _ASCENDANT_LIMIT + 1}
    assert world.record().content_digest == before.content_digest


@pytest.mark.parametrize(
    ("leaves", "row"),
    [
        ({"nif": _NIF}, 1),
        ({"nif": "12345678A", "birth_date": "1948-03-04"}, 1),
        ({"nif": "X1234567A", "birth_date": "1948-03-04"}, 1),
        ({"nif": _CIF, "birth_date": "1948-03-04"}, 1),
        ({"nif": "not an id", "birth_date": "1948-03-04"}, 1),
        ({"birth_date": "1948-02-30"}, 1),
        ({"birth_date": "19480304"}, 1),
        ({"birth_date": "1948-03-04", "fallecimiento": "yesterday"}, 1),
        ({"birth_date": "1948-03-04", "fallecimiento": "1947-12-31"}, 1),
        ({"birth_date": "1948-03-04", "convivientes": "11"}, 1),
        ({"birth_date": "1948-03-04", "convivientes": "-1"}, 1),
        ({"birth_date": "1948-03-04", "convivientes": "two"}, 1),
        ({"birth_date": "1948-03-04", "apellidos_nombre": "Ana"}, 1),
        ({"birth_date": "1948-03-04", "discapacidad_clave": "1"}, 1),
    ],
)
def test_a_row_the_declaration_cannot_hold_is_refused_before_anything_is_written(
    world: _World, leaves: dict[str, str], row: int
) -> None:
    before = world.record()

    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(_row(**leaves))

    assert refused.value.context is not None and refused.value.context["row"] == row
    assert world.record().content_digest == before.content_digest
    assert world.facts() == {}


@pytest.mark.parametrize(
    "leaves",
    [
        {"nif": "99999999A", "birth_date": "1948-03-04"},
        {"nif": _CIF, "birth_date": "1948-03-04"},
        {"birth_date": "1948-02-30"},
        {"birth_date": "1948-03-04", "fallecimiento": "yesterday"},
    ],
)
def test_a_refused_value_leaves_no_chained_exception_carrying_what_was_typed(
    world: _World, leaves: dict[str, str]
) -> None:
    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(_row(**leaves))

    assert refused.value.__cause__ is None
    assert refused.value.__context__ is None


def test_a_refusal_names_the_row_by_position(world: _World) -> None:
    with pytest.raises(UserProfileValidationError) as refused:
        world.replace(_row(birth_date="1948-03-04"), _row(birth_date="1950-01-01"), _row(nif=_NIF))

    assert refused.value.context is not None and refused.value.context["row"] == 3


@pytest.mark.parametrize("language", list(OutputLanguage))
def test_every_refusal_serves_a_sentence_in_the_workers_language_and_never_echoes_the_value(
    world: _World, language: OutputLanguage
) -> None:
    typed = "99999999A"
    attempts = (
        (_row(nif=typed, birth_date="1948-03-04"), ("2",)),
        (_row(nif=_NIF), ("2",)),
        (_row(birth_date="1948-03-04", fallecimiento="1900-01-01"), ("2",)),
        (_row(birth_date="1948-03-04", convivientes="11"), ("2", "10")),
    )
    sentences: set[str] = set()
    with override_settings(cadrumo_output_language=language.value):
        for offender, expected in attempts:
            with pytest.raises(UserProfileValidationError) as refused:
                world.replace(_row(birth_date="1940-01-01"), offender)
            detail = build_operation_error_detail(refused.value)
            assert detail is not None and detail.refusal_words is not None
            assert detail.refusal_words_language is language
            assert not detail.refusal_words.startswith("application.")
            assert typed not in detail.refusal_words and typed not in repr(detail)
            assert all(token in detail.refusal_words for token in expected)
            sentences.add(detail.refusal_words)
    assert len(sentences) == len(attempts)


def test_the_over_limit_sentence_names_the_limit_and_the_count_in_every_language(world: _World) -> None:
    rows = tuple(_row(birth_date="1940-01-01") for _ in range(_ASCENDANT_LIMIT + 1))
    sentences: dict[OutputLanguage, str] = {}
    for language in OutputLanguage:
        with override_settings(cadrumo_output_language=language.value):
            with pytest.raises(UserProfileValidationError) as refused:
                world.replace(*rows)
            detail = build_operation_error_detail(refused.value)
        assert detail is not None and detail.refusal_words is not None
        assert str(_ASCENDANT_LIMIT) in detail.refusal_words and str(_ASCENDANT_LIMIT + 1) in detail.refusal_words
        sentences[language] = detail.refusal_words
    assert len(set(sentences.values())) == len(sentences)


def test_a_stale_baseline_is_refused_and_writes_nothing(world: _World) -> None:
    stale = world.record()
    world.replace(_row(birth_date="1948-03-04"))
    after = world.record()

    with pytest.raises(ProfileRecordConflictError):
        world.replace(_row(birth_date="1950-01-01"), baseline=stale)

    assert world.record().content_digest == after.content_digest
    assert world.facts() == {_COUNT: "1", f"{_OBJECT}.0.birth_date": "1948-03-04"}


def test_a_set_replaces_only_the_ascendants_and_leaves_the_descendants(world: _World) -> None:
    apply_profile_fact_changes(
        profile_id=world.profile_id,
        changes=(
            UserProfileFact(path="renta_family.descendientes_count", value="1"),
            UserProfileFact(path="renta_family.descendiente.0.birth_date", value="2015-04-03"),
        ),
        door=ProfileFactWriteDoor.MANAGER_DESCENDANTS,
        expected_record=world.record(),
        profile_decode_context=world.operation.profile_decode_context(),
    )

    world.replace(_row(birth_date="1948-03-04"))
    world.replace()

    stored = {fact.path: str(fact.value) for fact in world.record().facts}
    assert stored["renta_family.descendientes_count"] == "1"
    assert stored["renta_family.descendiente.0.birth_date"] == "2015-04-03"


def test_a_row_cannot_repeat_a_leaf() -> None:
    with pytest.raises(ValidationError):
        _row_with_repeated_leaf()


def _row_with_repeated_leaf() -> ProfileAscendantRow:
    return ProfileAscendantRow(
        facts=(
            ProfileAscendantFact(field_key="birth_date", value="1948-03-04"),
            ProfileAscendantFact(field_key="birth_date", value="1950-01-01"),
        )
    )
