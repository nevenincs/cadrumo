"""Tests for the canonical ProfileLifecycleService."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ...adapters.persistence.storage import EphemeralMasterKeyProvider
from ...adapters.persistence.storage.sql import SecureObjectRepository, create_engine_from_settings
from ...adapters.persistence.storage.sql._orm import Base
from ...core.config import Settings
from ...core.resources import resources
from ...domain.buckets import BucketEventHistoryRepository, BucketEventType
from ...domain.user_profile import (
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    ProfileSchemaValidationError,
    UserProfileFact,
    UserProfileStatus,
)
from . import (
    DuplicateProfileCommand,
    EditProfileFieldCommand,
    ProfileLifecycleService,
    ProfileValidationService,
    RegisterProfileCommand,
    RemoveProfileCommand,
    RenameProfileCommand,
    UserProfileLifecycleRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    provider = EphemeralMasterKeyProvider()
    with provider:
        engine = create_engine_from_settings(
            Settings(aeat_database_url=f"sqlite:///{(tmp_path / 'aeat.db').as_posix()}")
        )
        Base.metadata.create_all(engine)
        try:
            yield SecureObjectRepository(engine=engine)
        finally:
            engine.dispose()


@pytest.fixture(scope="module")
def schema():
    return resources().user_profile_schema.singleton


def _service(secure_objects, schema) -> ProfileLifecycleService:
    return ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(bucket_id="bucket-a", objects=secure_objects),
        validator=ProfileValidationService(schema=schema),
        events=BucketEventHistoryRepository(objects=secure_objects),
    )


def _all_required_facts(schema) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(UserProfileFact(path=f"{section.key}.{field.key}", value="placeholder"))
    return tuple(facts)


def test_register_rejects_schema_violations(secure_objects, schema) -> None:
    svc = _service(secure_objects, schema)
    with pytest.raises(ProfileSchemaValidationError, match=r"required field .* is missing"):
        svc.register(RegisterProfileCommand(profile_id="operator", display_name="Op", facts=()))


def test_register_persists_when_all_required_facts_present(secure_objects, schema) -> None:
    svc = _service(secure_objects, schema)
    result = svc.register(
        RegisterProfileCommand(
            profile_id="operator",
            display_name="Operator",
            facts=_all_required_facts(schema),
        )
    )
    assert result.profile.profile_id == "operator"
    assert result.profile.status is UserProfileStatus.ACTIVE


def test_register_refuses_duplicate_profile_id(secure_objects, schema) -> None:
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id="operator",
            display_name="Operator",
            facts=_all_required_facts(schema),
        )
    )
    with pytest.raises(ProfileAlreadyExistsError):
        svc.register(
            RegisterProfileCommand(
                profile_id="operator",
                display_name="Operator Two",
                facts=_all_required_facts(schema),
            )
        )


def test_edit_field_upserts_a_fact(secure_objects, schema) -> None:
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id="operator",
            display_name="Operator",
            facts=_all_required_facts(schema),
        )
    )
    result = svc.edit_field(
        EditProfileFieldCommand(
            profile_id="operator",
            path="identity.tax_id",
            value="X1234567Z",
        )
    )
    assert any(fact.path == "identity.tax_id" and fact.value == "X1234567Z" for fact in result.profile.facts)


def test_remove_tombstones_the_profile(secure_objects, schema) -> None:
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id="operator",
            display_name="Operator",
            facts=_all_required_facts(schema),
        )
    )
    result = svc.remove(RemoveProfileCommand(profile_id="operator"))
    assert result.profile.status is UserProfileStatus.TOMBSTONED
    assert result.profile.removed_at is not None


def test_duplicate_copies_to_a_new_id(secure_objects, schema) -> None:
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id="operator",
            display_name="Operator",
            facts=_all_required_facts(schema),
        )
    )
    result = svc.duplicate(
        DuplicateProfileCommand(
            source_profile_id="operator",
            target_profile_id="operator-spouse",
            target_display_name="Spouse",
        )
    )
    assert result.profile.profile_id == "operator-spouse"
    assert result.profile.display_name == "Spouse"
    assert result.profile.status is UserProfileStatus.ACTIVE


def test_rename_updates_label_only(secure_objects, schema) -> None:
    """``rename`` changes ``display_name`` and nothing else.

    Profile identity is immutable: ``profile_id``, status, facts, and
    ``created_at`` must all survive a rename unchanged; only
    ``display_name`` moves to the new label.
    """

    svc = _service(secure_objects, schema)
    registered = svc.register(
        RegisterProfileCommand(
            profile_id="operator",
            display_name="Operator",
            facts=_all_required_facts(schema),
        )
    )

    result = svc.rename(
        RenameProfileCommand(profile_id="operator", target_display_name="Renamed Operator")
    )

    assert result.profile.profile_id == "operator"
    assert result.profile.display_name == "Renamed Operator"
    assert result.profile.status is UserProfileStatus.ACTIVE
    assert result.profile.facts == registered.profile.facts
    assert result.profile.created_at == registered.profile.created_at

    # The persisted record reflects only the label change.
    reloaded = svc.read("operator")
    assert reloaded.profile_id == "operator"
    assert reloaded.display_name == "Renamed Operator"


def test_rename_refuses_a_tombstoned_profile(secure_objects, schema) -> None:
    """``rename`` on a tombstoned profile is refused — only live profiles relabel."""

    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id="operator",
            display_name="Operator",
            facts=_all_required_facts(schema),
        )
    )
    svc.remove(RemoveProfileCommand(profile_id="operator"))

    with pytest.raises(ProfileNotFoundError, match="tombstoned"):
        svc.rename(RenameProfileCommand(profile_id="operator", target_display_name="New Label"))


def test_lifecycle_emits_bucket_events(secure_objects, schema) -> None:
    svc = _service(secure_objects, schema)
    events_repo = BucketEventHistoryRepository(objects=secure_objects)

    svc.register(
        RegisterProfileCommand(
            profile_id="operator",
            display_name="Operator",
            facts=_all_required_facts(schema),
        )
    )
    svc.edit_field(EditProfileFieldCommand(profile_id="operator", path="identity.email", value="op@example.test"))
    svc.edit_field(EditProfileFieldCommand(profile_id="operator", path="identity.email", value=None))
    svc.duplicate(
        DuplicateProfileCommand(
            source_profile_id="operator",
            target_profile_id="operator-spouse",
            target_display_name="Spouse",
        )
    )
    svc.remove(RemoveProfileCommand(profile_id="operator-spouse"))

    catalogue = events_repo.load()
    by_type: dict[BucketEventType, int] = {}
    for event in catalogue.events.values():
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
    assert by_type[BucketEventType.PROFILE_BUCKET_CREATED] == 1
    assert by_type[BucketEventType.PROFILE_VALUES_UPDATED] >= 2  # register-with-facts + edit_field
    assert by_type[BucketEventType.PROFILE_VALUES_CLEARED] == 1
    assert by_type[BucketEventType.PROFILE_DUPLICATED] == 1
    assert by_type[BucketEventType.PROFILE_TOMBSTONED] == 1


def test_list_profiles_returns_sorted_listings(secure_objects, schema) -> None:
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(profile_id="b-second", display_name="Second", facts=_all_required_facts(schema))
    )
    svc.register(RegisterProfileCommand(profile_id="a-first", display_name="First", facts=_all_required_facts(schema)))
    listing = svc.list_profiles()
    assert tuple(row.profile_id for row in listing.profiles) == ("a-first", "b-second")
