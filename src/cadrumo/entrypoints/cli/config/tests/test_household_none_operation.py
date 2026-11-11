"""The household verbs' request path against a real encrypted profile.

Each case composes what ``config profile ascendiente`` and ``config profile descendiente``
do around the registered replacement: the flag grammar builds the rows, the rows already
stored are read back, and ``--none`` is admitted or refused from the group the profile
view serves. The writes go through the same replacement operations the window uses, so a
stated-empty household, a never-answered one and a household with people are checked as
three different stored states.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo_client.commands.errors import CliRefusedBoundaryError

from .....adapters.persistence.profile.tests.profile_registration import register_minimal_profile
from .....adapters.persistence.storage.tests.secure_sql import isolated_profile_storage_root
from .....application.user_profile.ascendant_rows import (
    ASCENDANT_OBJECT_PATH,
    ProfileAscendantFact,
    ProfileAscendantRow,
    ascendant_rows_from_facts,
    replace_profile_ascendants,
)
from .....application.user_profile.capsule_record import ProfileRecordConflictError
from .....application.user_profile.descendant_rows import DESCENDANT_OBJECT_PATH, replace_profile_descendants
from .....application.user_profile.family_rows import (
    ProfileFamilyGroupState,
    ProfileViewFamilyGroupItem,
    family_row_items,
)
from .....application.user_profile.login_session import authenticate_profile_for_invocation
from .....application.user_profile.profile_record_repository import ProfileRecordRepository
from .....application.user_profile.registration import register_profile_with_credentials
from .....core.config import override_settings
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from .....domain.user_profile.errors import UserProfileValidationError
from .....domain.user_profile.values import UserProfileRecord
from ..ascendiente_flag import parse_ascendiente_flag
from ..operation_household import require_group_open_to_none

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _World:
    """One registered, authenticated profile and the authority the operations run under."""

    def __init__(self, profile_id: str, operation: PinnedAuthorityOperation) -> None:
        self.profile_id = profile_id
        self.operation = operation

    def record(self) -> UserProfileRecord:
        return ProfileRecordRepository.for_current_session(
            self.profile_id, profile_decode_context=self.operation.profile_decode_context()
        ).load(self.profile_id)

    def group(self, object_path: str) -> ProfileViewFamilyGroupItem:
        values = {fact.path: str(fact.value) for fact in self.record().facts if fact.value is not None}
        items = family_row_items(values, schema=self.operation.profile_schema(), operation=self.operation)
        return next(
            item for item in items if isinstance(item, ProfileViewFamilyGroupItem) and item.group_key == object_path
        )

    def stored_ascendants(self) -> tuple[ProfileAscendantRow, ...]:
        return ascendant_rows_from_facts(
            {fact.path: str(fact.value) for fact in self.record().facts if fact.value is not None}
        )

    def replace_ascendants(
        self, rows: tuple[ProfileAscendantRow, ...], *, baseline: UserProfileRecord | None = None
    ) -> int:
        current = baseline or self.record()
        return replace_profile_ascendants(
            profile_id=self.profile_id,
            ascendants=rows,
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            operation=self.operation,
        ).total

    def replace_descendants(self) -> int:
        current = self.record()
        return replace_profile_descendants(
            profile_id=self.profile_id,
            descendants=(),
            expected_revision=current.record_revision,
            expected_content_digest=current.content_digest,
            operation=self.operation,
        ).total


@pytest.fixture
def world(tmp_path: Path) -> Iterator[_World]:
    secret = f"household-none-{tmp_path.name}"
    with (
        override_settings(cadrumo_output_language="", cadrumo_secret_passphrase=secret),
        isolated_profile_storage_root(tmp_path=tmp_path),
        bundled_indexed_authority().operation() as operation,
    ):
        outcome = register_profile_with_credentials(
            label="Household none",
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


def test_a_never_asked_household_is_unknown_and_none_makes_it_a_stated_empty_one(world: _World) -> None:
    unknown = world.group(ASCENDANT_OBJECT_PATH)
    assert (unknown.state, unknown.stated_count, unknown.row_count) == (ProfileFamilyGroupState.UNKNOWN, None, 0)
    require_group_open_to_none(unknown)

    assert world.replace_ascendants(()) == 0

    stated = world.group(ASCENDANT_OBJECT_PATH)
    assert (stated.state, stated.stated_count, stated.row_count) == (ProfileFamilyGroupState.NONE_DECLARED, "0", 0)
    assert world.stored_ascendants() == ()
    require_group_open_to_none(stated)
    # The descendants group is a different answer: stating one family says nothing about the other.
    assert world.group(DESCENDANT_OBJECT_PATH).state is ProfileFamilyGroupState.UNKNOWN


def test_the_descendant_none_is_the_same_stated_zero_and_leaves_the_ascendants_unasked(world: _World) -> None:
    assert world.replace_descendants() == 0

    descendants = world.group(DESCENDANT_OBJECT_PATH)
    assert (descendants.state, descendants.stated_count) == (ProfileFamilyGroupState.NONE_DECLARED, "0")
    assert world.group(ASCENDANT_OBJECT_PATH).state is ProfileFamilyGroupState.UNKNOWN


def test_flag_rows_are_stored_appended_and_closed_to_none(world: _World) -> None:
    first = parse_ascendiente_flag("NACIMIENTO=1948-03-04,NIF=12345678z,CONVIVIENTES=2")
    assert world.replace_ascendants((first,)) == 1

    second = parse_ascendiente_flag("NACIMIENTO=1951-11-30,FALLECIMIENTO=2025-02-01")
    existing = world.stored_ascendants()
    assert world.replace_ascendants((*existing, second)) == 2

    leaves = [{fact.field_key: fact.value for fact in row.facts} for row in world.stored_ascendants()]
    assert leaves == [
        {"nif": "12345678Z", "birth_date": "1948-03-04", "convivientes": "2"},
        {"birth_date": "1951-11-30", "fallecimiento": "2025-02-01"},
    ]
    people = world.group(ASCENDANT_OBJECT_PATH)
    assert (people.state, people.row_count) == (ProfileFamilyGroupState.ROWS, 2)
    with pytest.raises(CliRefusedBoundaryError) as refused:
        require_group_open_to_none(people)
    assert refused.value.translated_message == "cli.config.profile.household.none_with_stored_rows"


def test_removing_the_last_person_states_an_empty_household_rather_than_an_unknown_one(world: _World) -> None:
    world.replace_ascendants((parse_ascendiente_flag("NACIMIENTO=1948-03-04"),))

    assert world.replace_ascendants(world.stored_ascendants()[1:]) == 0

    assert world.group(ASCENDANT_OBJECT_PATH).state is ProfileFamilyGroupState.NONE_DECLARED


def test_a_row_the_operation_refuses_changes_nothing_and_does_not_echo_the_value(world: _World) -> None:
    before = world.record()
    typed = "99999999A"

    with pytest.raises(UserProfileValidationError) as refused:
        world.replace_ascendants((parse_ascendiente_flag(f"NACIMIENTO=1948-03-04,NIF={typed}"),))

    assert refused.value.context is not None and refused.value.context["row"] == 1
    assert typed not in repr(refused.value.context)
    assert world.record().content_digest == before.content_digest
    assert world.group(ASCENDANT_OBJECT_PATH).state is ProfileFamilyGroupState.UNKNOWN


def test_a_field_an_ascendant_row_cannot_state_is_refused(world: _World) -> None:
    before = world.record()
    row = ProfileAscendantRow(
        facts=(
            ProfileAscendantFact(field_key="birth_date", value="1948-03-04"),
            ProfileAscendantFact(field_key="apellidos_nombre", value="Ana"),
        )
    )

    with pytest.raises(UserProfileValidationError):
        world.replace_ascendants((row,))

    assert world.record().content_digest == before.content_digest


def test_a_baseline_the_profile_moved_past_is_refused_and_a_none_cannot_overwrite_the_newer_state(
    world: _World,
) -> None:
    stale = world.record()
    world.replace_ascendants((parse_ascendiente_flag("NACIMIENTO=1948-03-04"),))
    after = world.record()

    with pytest.raises(ProfileRecordConflictError):
        world.replace_ascendants((), baseline=stale)

    assert world.record().content_digest == after.content_digest
    assert world.group(ASCENDANT_OBJECT_PATH).state is ProfileFamilyGroupState.ROWS
