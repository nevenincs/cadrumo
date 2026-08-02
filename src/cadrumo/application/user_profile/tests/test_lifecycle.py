"""Tests for the canonical ProfileLifecycleService."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import cast

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.i18n import tr
from ....core.resources import resources
from ....domain.buckets import BucketEventType
from ....domain.user_profile import (
    ProfileAlreadyExistsError,
    ProfileBucketMismatchError,
    ProfileNotFoundError,
    ProfileSchemaDefinition,
    ProfileSchemaValidationError,
    UserProfileFact,
    UserProfileStatus,
    UserProfileValidationError,
)
from ....tests.secure_sql import isolated_runtime_profile
from ....tests.user_profile import schema_valid_placeholder
from .. import (
    CompleteSetupCommand,
    EditProfileFieldCommand,
    ProfileLifecycleService,
    ProfileValidationService,
    ReactivateProfileCommand,
    RegisterProfileCommand,
    RemoveProfileCommand,
    RenameProfileCommand,
    UserProfileLifecycleRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_RUNTIME_BUCKET_ID = "e2505e3c-97de-49e7-84c8-6858cbece132"
_PROFILE_BUCKET_ID = "9ab28b80-7c35-4143-88f3-b2dcb7a48af7"
_PRIVATE_EVENTS_RUNTIME_BUCKET_ID = "2ac01741-cd0f-44ea-84c1-ff3db73942f2"


@pytest.fixture
def secure_objects(tmp_path: Path) -> Iterator[SecureObjectRepository]:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_RUNTIME_BUCKET_ID,
    ) as profile:
        yield profile.repository


@pytest.fixture(scope="module")
def schema() -> ProfileSchemaDefinition:
    return resources().user_profile_schema.singleton


def _service(secure_objects: SecureObjectRepository, schema: ProfileSchemaDefinition) -> ProfileLifecycleService:
    return ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(bucket_id=_PROFILE_BUCKET_ID, objects=secure_objects),
        validator=ProfileValidationService(schema=schema),
        events=BucketEventHistoryRepository(objects=secure_objects),
    )


def _all_required_facts(schema: ProfileSchemaDefinition) -> tuple[UserProfileFact, ...]:
    facts: list[UserProfileFact] = []
    for section in schema.sections:
        if section.repeatable:
            continue
        for field in section.fields:
            if field.required:
                facts.append(
                    UserProfileFact(
                        path=f"{section.key}.{field.key}",
                        value=schema_valid_placeholder(field),
                    ),
                )
    return tuple(facts)


def test_register_rejects_schema_violations(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    svc = _service(secure_objects, schema)
    with pytest.raises(ProfileSchemaValidationError) as exc_info:
        svc.register(RegisterProfileCommand(profile_id=_PROFILE_BUCKET_ID, display_name="Op", facts=()))
    error = exc_info.value
    assert str(error) == "profile facts failed schema validation"
    assert _PROFILE_BUCKET_ID not in str(error)
    assert error.translated_message == "application.user_profile.errors.lifecycle_schema_validation_failed"
    assert tr(error.translated_message) != error.translated_message
    assert error.context is not None
    assert error.context["profile_id"] == _PROFILE_BUCKET_ID
    assert "required_field_missing" in cast("list[str]", error.context["issue_codes"])


def test_register_persists_when_all_required_facts_present(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    svc = _service(secure_objects, schema)
    result = svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )
    assert result.profile.profile_id == _PROFILE_BUCKET_ID
    assert result.profile.status is UserProfileStatus.ACTIVE


def test_register_refuses_duplicate_profile_id(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )
    with pytest.raises(ProfileAlreadyExistsError) as exc_info:
        svc.register(
            RegisterProfileCommand(
                profile_id=_PROFILE_BUCKET_ID,
                display_name="Operator Two",
                facts=_all_required_facts(schema),
            ),
        )
    error = exc_info.value
    assert str(error) == "profile already exists in the active bucket"
    assert _PROFILE_BUCKET_ID not in str(error)
    assert error.translated_message == "application.user_profile.errors.lifecycle_profile_already_exists"
    assert tr(error.translated_message) != error.translated_message
    assert error.context == {"profile_id": _PROFILE_BUCKET_ID, "bucket_id": _PROFILE_BUCKET_ID}


def test_edit_field_upserts_a_fact(secure_objects: SecureObjectRepository, schema: ProfileSchemaDefinition) -> None:
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )
    result = svc.edit_field(
        EditProfileFieldCommand(
            profile_id=_PROFILE_BUCKET_ID,
            path="identity.tax_id",
            value="X1234567Z",
        ),
    )
    assert any(fact.path == "identity.tax_id" and fact.value == "X1234567Z" for fact in result.profile.facts)


def test_remove_tombstones_the_profile(secure_objects: SecureObjectRepository, schema: ProfileSchemaDefinition) -> None:
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )
    result = svc.remove(RemoveProfileCommand(profile_id=_PROFILE_BUCKET_ID))
    assert result.profile.status is UserProfileStatus.TOMBSTONED
    assert result.profile.removed_at is not None


def test_reactivate_restores_a_tombstoned_profile(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    """``reactivate`` is the symmetric inverse of ``remove``: status flips back, ``removed_at`` clears."""
    svc = _service(secure_objects, schema)
    registered = svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )
    svc.remove(RemoveProfileCommand(profile_id=_PROFILE_BUCKET_ID))

    result = svc.reactivate(ReactivateProfileCommand(profile_id=_PROFILE_BUCKET_ID))

    assert result.profile.status is UserProfileStatus.ACTIVE
    assert result.profile.removed_at is None
    assert result.profile.facts == registered.profile.facts
    assert result.profile.created_at == registered.profile.created_at

    # The persisted record reflects the reactivation.
    reloaded = svc.read(_PROFILE_BUCKET_ID)
    assert reloaded.status is UserProfileStatus.ACTIVE
    assert reloaded.removed_at is None


def test_reactivate_refuses_a_live_profile(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    """``reactivate`` on a live (never-tombstoned) profile is refused."""
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )

    with pytest.raises(ProfileNotFoundError):
        svc.reactivate(ReactivateProfileCommand(profile_id=_PROFILE_BUCKET_ID))


def test_reactivate_emits_profile_reactivated_event(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    """``reactivate`` emits ``PROFILE_REACTIVATED`` — the symmetric inverse of ``PROFILE_TOMBSTONED``."""
    events = BucketEventHistoryRepository(objects=secure_objects)
    svc = ProfileLifecycleService(
        repository=UserProfileLifecycleRepository(bucket_id=_PROFILE_BUCKET_ID, objects=secure_objects),
        validator=ProfileValidationService(schema=schema),
        events=events,
    )
    svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )
    svc.remove(RemoveProfileCommand(profile_id=_PROFILE_BUCKET_ID))
    svc.reactivate(ReactivateProfileCommand(profile_id=_PROFILE_BUCKET_ID))

    catalogue = events.load()
    event_types = [event.event_type for event in catalogue.events.values()]
    assert BucketEventType.PROFILE_TOMBSTONED in event_types
    assert BucketEventType.PROFILE_REACTIVATED in event_types


def test_rename_updates_label_only(secure_objects: SecureObjectRepository, schema: ProfileSchemaDefinition) -> None:
    """``rename`` changes ``display_name`` and nothing else.

    Profile identity is immutable: ``profile_id``, status, facts, and
    ``created_at`` must all survive a rename unchanged; only
    ``display_name`` moves to the new label.
    """

    svc = _service(secure_objects, schema)
    registered = svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )

    result = svc.rename(RenameProfileCommand(profile_id=_PROFILE_BUCKET_ID, target_display_name="Renamed Operator"))

    assert result.profile.profile_id == _PROFILE_BUCKET_ID
    assert result.profile.display_name == "Renamed Operator"
    assert result.profile.status is UserProfileStatus.ACTIVE
    assert result.profile.facts == registered.profile.facts
    assert result.profile.created_at == registered.profile.created_at

    # The persisted record reflects only the label change.
    reloaded = svc.read(_PROFILE_BUCKET_ID)
    assert reloaded.profile_id == _PROFILE_BUCKET_ID
    assert reloaded.display_name == "Renamed Operator"


def test_rename_refuses_a_tombstoned_profile(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    """``rename`` on a tombstoned profile is refused — only live profiles relabel."""

    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )
    svc.remove(RemoveProfileCommand(profile_id=_PROFILE_BUCKET_ID))

    with pytest.raises(ProfileNotFoundError) as exc_info:
        svc.rename(RenameProfileCommand(profile_id=_PROFILE_BUCKET_ID, target_display_name="New Label"))
    error = exc_info.value
    assert str(error) == "tombstoned profile cannot be renamed"
    assert _PROFILE_BUCKET_ID not in str(error)
    assert error.translated_message == "application.user_profile.errors.lifecycle_profile_tombstoned_rename"
    assert tr(error.translated_message) != error.translated_message
    assert error.context == {"profile_id": _PROFILE_BUCKET_ID, "action": "rename"}


def test_lifecycle_emits_bucket_events(secure_objects: SecureObjectRepository, schema: ProfileSchemaDefinition) -> None:
    svc = _service(secure_objects, schema)
    events_repo = BucketEventHistoryRepository(objects=secure_objects)

    svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Operator",
            facts=_all_required_facts(schema),
        ),
    )
    svc.edit_field(
        EditProfileFieldCommand(profile_id=_PROFILE_BUCKET_ID, path="identity.email", value="op@example.test")
    )
    svc.edit_field(EditProfileFieldCommand(profile_id=_PROFILE_BUCKET_ID, path="identity.email", value=None))
    svc.remove(RemoveProfileCommand(profile_id=_PROFILE_BUCKET_ID))

    catalogue = events_repo.load()
    by_type: dict[BucketEventType, int] = {}
    for event in catalogue.events.values():
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
    assert by_type[BucketEventType.PROFILE_BUCKET_CREATED] == 1
    assert by_type[BucketEventType.PROFILE_VALUES_UPDATED] >= 2  # register-with-facts + edit_field
    assert by_type[BucketEventType.PROFILE_VALUES_CLEARED] == 1
    assert by_type[BucketEventType.PROFILE_TOMBSTONED] == 1


def test_lifecycle_event_payload_values_are_encrypted_at_rest(tmp_path: Path, schema: ProfileSchemaDefinition) -> None:
    with isolated_runtime_profile(
        tmp_path=tmp_path,
        bucket_id=_PRIVATE_EVENTS_RUNTIME_BUCKET_ID,
    ) as profile:
        svc = _service(profile.repository, schema)
        source_profile_id = _PROFILE_BUCKET_ID
        original_label = "Sensitive Operator Label"
        renamed_label = "Renamed Sensitive Label"

        svc.register(
            RegisterProfileCommand(
                profile_id=source_profile_id,
                display_name=original_label,
                facts=_all_required_facts(schema),
            ),
        )
        svc.rename(RenameProfileCommand(profile_id=source_profile_id, target_display_name=renamed_label))

        catalogue = BucketEventHistoryRepository(objects=profile.repository).load()
        register_events = catalogue.for_bucket(
            _PROFILE_BUCKET_ID,
            event_types=(BucketEventType.PROFILE_BUCKET_CREATED,),
        )
        rename_events = catalogue.for_bucket(
            _PROFILE_BUCKET_ID,
            event_types=(BucketEventType.PROFILE_RENAMED,),
        )
        assert register_events[-1].payload["display_name"] == original_label
        assert rename_events[-1].payload["previous_display_name"] == original_label

        from ....tests.secure_sql import read_db_at_rest_bytes

        database_bytes = read_db_at_rest_bytes(profile.paths.db_dir / "cadrumo.db")
        # Only values this flow actually writes are asserted absent. A value
        # nothing persists is absent trivially, which would read as encryption
        # coverage while proving nothing.
        for plaintext in (
            source_profile_id,
            original_label,
            renamed_label,
        ):
            assert plaintext.encode("utf-8") not in database_bytes


def test_register_refuses_a_second_foreign_profile_in_one_bucket(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    """A bucket holds one live profile; the ownership guard refuses a second.

    This previously registered TWO profiles into one bucket and asserted they
    came back sorted from a listing. That shape is not reachable: a bucket
    holds exactly one live profile-value record by the storage contract this
    module documents, each profile is provisioned into its own bucket, and the
    ownership guard refuses the second registration outright -- which is what
    survives here. The listing half went with
    ``ProfileLifecycleService.list_profiles``, which had no production caller:
    the operator's profile listing scans bucket directories instead.
    """
    svc = _service(secure_objects, schema)
    svc.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Only",
            facts=_all_required_facts(schema),
        ),
    )

    with pytest.raises(ProfileBucketMismatchError):
        svc.register(
            RegisterProfileCommand(
                profile_id="14141414-1414-4141-8141-141414141414",
                display_name="Foreign",
                facts=_all_required_facts(schema),
            ),
        )


# ---------------------------------------------------------------------------
# Service-contract tests for the read + validate paths.
# ---------------------------------------------------------------------------


def test_read_returns_persisted_record(secure_objects: SecureObjectRepository, schema: ProfileSchemaDefinition) -> None:
    """Service-contract gate: read() loads the same record back as the
    register() call persisted (round-trip via the secure repository)."""

    svc = _service(secure_objects, schema)
    facts = _all_required_facts(schema)
    svc.register(RegisterProfileCommand(profile_id=_PROFILE_BUCKET_ID, display_name="Round-trip", facts=facts))
    loaded = svc.read(_PROFILE_BUCKET_ID)
    assert loaded.profile_id == _PROFILE_BUCKET_ID
    assert loaded.display_name == "Round-trip"
    assert loaded.status is UserProfileStatus.ACTIVE
    assert {f.path for f in loaded.facts} == {f.path for f in facts}


def test_read_raises_on_unknown_profile(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    """Service-contract gate: read() refuses an unknown profile id with
    :class:`ProfileNotFoundError`, not a silent empty record."""

    svc = _service(secure_objects, schema)
    with pytest.raises(ProfileNotFoundError):
        svc.read(_PROFILE_BUCKET_ID)


def test_validator_surfaces_missing_required_field_as_issue(schema: ProfileSchemaDefinition) -> None:
    """Service-contract gate: the ProfileValidationService that the
    lifecycle service composes surfaces a missing required field as
    a structured issue (not a silent pass).

    This pins the validator contract that ``aeat config profile
    validate`` and lifecycle.register both depend on."""

    validator = ProfileValidationService(schema=schema)
    # An empty fact tuple violates every required-field constraint.
    report = validator.validate_facts(profile_id="18181818-1818-4181-8181-181818181818", facts=())
    assert report.profile_id == "18181818-1818-4181-8181-181818181818"
    assert len(report.issues) >= 1
    severities = {issue.severity.value for issue in report.issues}
    assert "error" in severities


def test_register_setup_incomplete_persists_the_status(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    service = _service(secure_objects, schema)
    service.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Mid-setup",
            facts=_all_required_facts(schema),
            status=UserProfileStatus.SETUP_INCOMPLETE,
        ),
    )
    record = service.read(_PROFILE_BUCKET_ID)
    assert record.status is UserProfileStatus.SETUP_INCOMPLETE


def test_register_refuses_a_tombstoned_birth() -> None:
    with pytest.raises(ValueError, match="registered tombstoned"):
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Dead on arrival",
            status=UserProfileStatus.TOMBSTONED,
        )


def test_complete_setup_activates_and_emits_the_transition_event(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    service = _service(secure_objects, schema)
    service.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Mid-setup",
            facts=_all_required_facts(schema),
            status=UserProfileStatus.SETUP_INCOMPLETE,
        ),
    )
    result = service.complete_setup(CompleteSetupCommand(profile_id=_PROFILE_BUCKET_ID))
    assert result.profile.status is UserProfileStatus.ACTIVE
    catalogue = BucketEventHistoryRepository(objects=secure_objects).load()
    assert BucketEventType.PROFILE_SETUP_COMPLETED in {event.event_type for event in catalogue.events.values()}


def test_complete_setup_refuses_an_active_profile(
    secure_objects: SecureObjectRepository,
    schema: ProfileSchemaDefinition,
) -> None:
    service = _service(secure_objects, schema)
    service.register(
        RegisterProfileCommand(
            profile_id=_PROFILE_BUCKET_ID,
            display_name="Complete",
            facts=_all_required_facts(schema),
        ),
    )
    with pytest.raises(UserProfileValidationError):
        service.complete_setup(CompleteSetupCommand(profile_id=_PROFILE_BUCKET_ID))
