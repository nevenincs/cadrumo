"""The migration that retires the year-keyed art. 23.2 reduction tier, through the real capsule.

A schema-8 record may hold a tier for one or more ejercicios. The tier cannot be
converted into the lease facts that now decide it, so the migration clears every
stored window of it, keeps every other fact, records the cleared path as typed
history and leaves the finding standing until a lease is recorded.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, date, datetime
from pathlib import Path

import pytest

from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.profile_schema_migration import (
    drain_migration_cleared_paths,
    migrate_profile_record_on_open,
)
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.schema_migration import (
    MIGRATED_PROFILE_SCHEMA_VERSION,
    RETIRED_RENTAL_TIER_PATH,
    ProfileSchemaMigration,
    migrate_profile_facts,
)
from cadrumo.domain.user_profile.values import UserProfileFact

from .profile_record_boundary_support import PROFILE_ID
from .profile_schema_legacy_support import publish_legacy_capsule, record_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

YEAR = filing_year_envelope().horizon
_PRIOR_VERSION = 8
_LEASE_PATH = "renta_arrendamiento.0.fecha_contrato"
_KEPT = (
    UserProfileFact(path="identity.tax_id", value="X0001500M"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
)
_TIER_WINDOWS = (
    UserProfileFact(
        path=RETIRED_RENTAL_TIER_PATH, value="tier-70", valid_from=date(YEAR - 1, 1, 1), valid_to=date(YEAR - 1, 12, 31)
    ),
    UserProfileFact(path=RETIRED_RENTAL_TIER_PATH, value="tier-50", valid_from=date(YEAR, 1, 1)),
)
_AT = datetime(YEAR, 11, 1, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def contexts() -> Iterator[tuple[ProfileCreateContext, ProfileDecodeContext]]:
    with bundled_indexed_authority().operation() as operation:
        yield operation.profile_create_context(), operation.profile_decode_context()


def test_every_stored_window_of_the_tier_is_cleared_and_nothing_else(
    tmp_path: Path, contexts: tuple[ProfileCreateContext, ProfileDecodeContext]
) -> None:
    publish_legacy_capsule(
        tmp_path,
        facts=(*_KEPT, *_TIER_WINDOWS),
        create_context=contexts[0],
        decode_context=contexts[1],
        version=_PRIOR_VERSION,
    )
    drain_migration_cleared_paths()
    session = record_session(contexts[1])
    try:
        migrated = ProfileRecordRepository(session=session, root=tmp_path).load(PROFILE_ID)
        store = ProfileRecordStore(session=session, root=tmp_path)
        migrations = store.schema_migrations()
        events = [event for event in store.history() if event.event_type is BucketEventType.PROFILE_SCHEMA_MIGRATED]
    finally:
        session.close()
        cleared = drain_migration_cleared_paths()

    assert migrated.facts == _KEPT
    assert cleared == (RETIRED_RENTAL_TIER_PATH,)
    assert migrations == (
        ProfileSchemaMigration(
            from_version=_PRIOR_VERSION,
            to_version=MIGRATED_PROFILE_SCHEMA_VERSION,
            cleared_paths=(RETIRED_RENTAL_TIER_PATH,),
        ),
    )
    assert len(events) == 1
    assert events[0].payload["schema_migration_cleared_paths"] == RETIRED_RENTAL_TIER_PATH
    assert events[0].payload["schema_migration_from"] == str(_PRIOR_VERSION)


def test_the_finding_stands_until_a_lease_is_recorded(
    tmp_path: Path, contexts: tuple[ProfileCreateContext, ProfileDecodeContext]
) -> None:
    publish_legacy_capsule(
        tmp_path,
        facts=(*_KEPT, *_TIER_WINDOWS),
        create_context=contexts[0],
        decode_context=contexts[1],
        version=_PRIOR_VERSION,
    )
    session = record_session(contexts[1])
    try:
        repository = ProfileRecordRepository(session=session, root=tmp_path)
        record = repository.load(PROFILE_ID)
        pending = repository.rental_tier_finding_pending(PROFILE_ID)
        repository.apply_fact_changes(
            PROFILE_ID,
            facts=(
                *record.facts,
                UserProfileFact(path="renta_arrendamiento.0.inmueble", value=0),
                UserProfileFact(path=_LEASE_PATH, value=date(YEAR, 2, 1)),
            ),
            expected_revision=record.record_revision,
            expected_content_digest=record.content_digest,
            event_type=BucketEventType.PROFILE_VALUES_UPDATED,
            event_payload={},
            now=_AT,
        )
        answered = repository.rental_tier_finding_pending(PROFILE_ID)
    finally:
        session.close()
        drain_migration_cleared_paths()

    assert pending is True
    assert answered is False


def test_a_profile_that_never_stored_a_tier_has_no_finding(
    tmp_path: Path, contexts: tuple[ProfileCreateContext, ProfileDecodeContext]
) -> None:
    publish_legacy_capsule(
        tmp_path, facts=_KEPT, create_context=contexts[0], decode_context=contexts[1], version=_PRIOR_VERSION
    )
    session = record_session(contexts[1])
    try:
        repository = ProfileRecordRepository(session=session, root=tmp_path)
        repository.load(PROFILE_ID)
        pending = repository.rental_tier_finding_pending(PROFILE_ID)
        migration = migrate_profile_record_on_open(session, root=tmp_path)
    finally:
        session.close()
        drain_migration_cleared_paths()

    assert pending is False
    assert migration is None


def test_a_schema_8_record_cannot_carry_a_field_only_schema_9_declares() -> None:
    with pytest.raises(UserProfileValidationError):
        migrate_profile_facts(
            (UserProfileFact(path="renta_inmueble.0.situacion", value="1"),), from_version=_PRIOR_VERSION
        )


def test_the_transform_clears_the_retired_path_whatever_its_value() -> None:
    kept, migration = migrate_profile_facts((*_KEPT, *_TIER_WINDOWS), from_version=_PRIOR_VERSION)

    assert kept == _KEPT
    assert migration.cleared_paths == (RETIRED_RENTAL_TIER_PATH,)
