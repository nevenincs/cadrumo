"""The migration that retires the stored disability key of an ascendant row, through the real capsule.

A record stored before schema 11 may hold an official disability key on an ascendant
row. The key is now derived from the grade, the assistance and the judicial
incapacity, and a key 1 or 2 cannot be converted into a grade, so the migration clears
the key on every row, keeps every other fact, records the cleared paths as typed
history and leaves a finding for each row until it states the three facts.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.profile_schema_migration import drain_migration_cleared_paths
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.user_profile.schema_migration import (
    MIGRATED_PROFILE_SCHEMA_VERSION,
    SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS,
    ProfileSchemaMigration,
    migrate_profile_facts,
)
from cadrumo.domain.user_profile.values import UserProfileFact

from .profile_record_boundary_support import PROFILE_ID
from .profile_schema_legacy_support import publish_legacy_capsule, record_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

YEAR = filing_year_envelope().horizon
_LAST_KEYED_VERSION = MIGRATED_PROFILE_SCHEMA_VERSION - 1
_GROUP = "renta_family.ascendiente"
_KEPT = (
    UserProfileFact(path="identity.tax_id", value="X0001500M"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="renta_family.ascendientes_count", value="2"),
    UserProfileFact(path=f"{_GROUP}.0.birth_date", value="1946-03-04"),
    UserProfileFact(path=f"{_GROUP}.0.discapacidad", value="33"),
    UserProfileFact(path=f"{_GROUP}.1.birth_date", value="1950-07-09"),
)
_KEYS = (
    UserProfileFact(path=f"{_GROUP}.0.discapacidad_clave", value="2"),
    UserProfileFact(path=f"{_GROUP}.1.discapacidad_clave", value="4"),
)
_CLEARED = tuple(sorted(fact.path for fact in _KEYS))
_AT = datetime(YEAR, 11, 1, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def contexts() -> Iterator[tuple[ProfileCreateContext, ProfileDecodeContext]]:
    with bundled_indexed_authority().operation() as operation:
        yield operation.profile_create_context(), operation.profile_decode_context()


def test_the_schema_this_build_writes_is_eleven_and_schema_9_and_10_records_still_open() -> None:
    assert MIGRATED_PROFILE_SCHEMA_VERSION == 11
    assert {9, 10} <= set(SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS)
    with bundled_indexed_authority().operation() as operation:
        assert operation.profile_schema().version == MIGRATED_PROFILE_SCHEMA_VERSION


@pytest.mark.parametrize("version", [9, _LAST_KEYED_VERSION])
def test_the_transform_clears_every_stored_key_and_nothing_else(version: int) -> None:
    kept, migration = migrate_profile_facts((*_KEPT, *_KEYS), from_version=version)

    assert kept == _KEPT
    assert migration.cleared_paths == _CLEARED
    assert migration.to_version == MIGRATED_PROFILE_SCHEMA_VERSION


def test_a_key_on_another_group_or_a_leaf_that_only_resembles_it_is_kept() -> None:
    others = (
        UserProfileFact(path="renta_family.descendiente.0.discapacidad_clave", value="1"),
        UserProfileFact(path=f"{_GROUP}.0.discapacidad_clave_extra", value="1"),
    )

    kept, migration = migrate_profile_facts(others, from_version=_LAST_KEYED_VERSION)

    assert kept == others
    assert migration.cleared_paths == ()


def test_a_migration_record_cannot_name_a_key_path_of_another_group() -> None:
    with pytest.raises(ValidationError, match="never clears"):
        ProfileSchemaMigration(
            from_version=_LAST_KEYED_VERSION,
            cleared_paths=("renta_family.descendiente.0.discapacidad_clave",),
        )


def test_the_keys_are_cleared_with_history_and_each_row_is_asked_until_it_states_its_facts(
    tmp_path: Path, contexts: tuple[ProfileCreateContext, ProfileDecodeContext]
) -> None:
    publish_legacy_capsule(
        tmp_path,
        facts=(*_KEPT, *_KEYS),
        create_context=contexts[0],
        decode_context=contexts[1],
        version=_LAST_KEYED_VERSION,
    )
    drain_migration_cleared_paths()
    session = record_session(contexts[1])
    try:
        repository = ProfileRecordRepository(session=session, root=tmp_path)
        record = repository.load(PROFILE_ID)
        store = ProfileRecordStore(session=session, root=tmp_path)
        events = [event for event in store.history() if event.event_type is BucketEventType.PROFILE_SCHEMA_MIGRATED]
        pending = repository.ascendant_disability_rows_pending(PROFILE_ID)
        payer_paths = repository.pending_cleared_payer_fact_paths(PROFILE_ID)
        repository.apply_fact_changes(
            PROFILE_ID,
            facts=(
                *record.facts,
                UserProfileFact(path=f"{_GROUP}.0.discapacidad_asistencia", value="true"),
                UserProfileFact(path=f"{_GROUP}.0.incapacidad_judicial", value="false"),
            ),
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
            event_type=BucketEventType.PROFILE_VALUES_UPDATED,
            event_payload={},
            now=_AT,
        )
        answered = repository.ascendant_disability_rows_pending(PROFILE_ID)
    finally:
        session.close()
        cleared = drain_migration_cleared_paths()

    assert record.facts == _KEPT
    assert cleared == _CLEARED
    assert len(events) == 1
    assert events[0].payload["schema_migration_cleared_paths"] == "|".join(_CLEARED)
    assert pending == ("0", "1")
    # A retired key is not a payer fact: its finding is the row's, never a profile edit flag.
    assert payer_paths == ()
    assert answered == ("1",)
