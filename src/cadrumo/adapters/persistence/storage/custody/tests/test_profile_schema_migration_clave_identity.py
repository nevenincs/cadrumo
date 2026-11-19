"""The migration that retires the stored copy of the Cl@ve identity, through the real capsule.

A schema-15 record may hold ``auth.dni_nie``. Cl@ve signs in as the taxpayer the
profile describes, so its identity is ``identity.tax_id``. The migration clears
the copy whatever it holds, keeps every other fact, records the cleared path as
typed history and leaves nothing for the operator to answer again.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.profile_schema_migration import drain_migration_cleared_paths
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope
from cadrumo.domain.calculations.registry.tests.published_authority import published_profile_schema
from cadrumo.domain.user_profile.schema_migration import (
    MIGRATED_PROFILE_SCHEMA_VERSION,
    RETIRED_CLAVE_IDENTITY_PATH,
    ProfileSchemaMigration,
    migrate_profile_facts,
    pending_cleared_payer_fact_paths,
)
from cadrumo.domain.user_profile.values import UserProfileFact, UserProfileRecord

from .profile_record_boundary_support import PROFILE_ID
from .profile_schema_legacy_support import publish_legacy_capsule, record_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

YEAR = filing_year_envelope().horizon
_PRIOR_VERSION = 15
_KEPT = (
    UserProfileFact(path="identity.tax_id", value="X0001500M"),
    UserProfileFact(path="taxpayer_type.entity_type", value="natural_person"),
    UserProfileFact(path="auth.provider", value="clave_movil"),
    UserProfileFact(path="auth.numero_soporte", value="E00000000"),
)
#: A stale copy that differs from the tax identifier, the case that misled the operator.
_STALE_COPY = UserProfileFact(path=RETIRED_CLAVE_IDENTITY_PATH, value="12345678Z")
_AT = datetime(YEAR, 11, 1, 10, 0, 0, tzinfo=UTC)


@pytest.fixture
def contexts() -> Iterator[tuple[ProfileCreateContext, ProfileDecodeContext]]:
    with bundled_indexed_authority().operation() as operation:
        yield operation.profile_create_context(), operation.profile_decode_context()


def test_the_schema_no_longer_declares_a_second_clave_identity() -> None:
    schema = published_profile_schema()

    assert MIGRATED_PROFILE_SCHEMA_VERSION == _PRIOR_VERSION + 1
    assert RETIRED_CLAVE_IDENTITY_PATH not in schema.field_paths
    assert "identity.tax_id" in schema.field_paths


def test_a_stored_copy_is_cleared_and_every_other_fact_kept(
    tmp_path: Path, contexts: tuple[ProfileCreateContext, ProfileDecodeContext]
) -> None:
    publish_legacy_capsule(
        tmp_path,
        facts=(*_KEPT, _STALE_COPY),
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
    assert cleared == (RETIRED_CLAVE_IDENTITY_PATH,)
    assert migrations == (
        ProfileSchemaMigration(
            from_version=_PRIOR_VERSION,
            to_version=MIGRATED_PROFILE_SCHEMA_VERSION,
            cleared_paths=(RETIRED_CLAVE_IDENTITY_PATH,),
        ),
    )
    assert len(events) == 1
    assert events[0].payload["schema_migration_cleared_paths"] == RETIRED_CLAVE_IDENTITY_PATH
    assert pending_cleared_payer_fact_paths(migrated, migrations) == ()


def test_the_transform_clears_the_copy_whatever_its_value_and_asks_for_nothing() -> None:
    for value in ("X0001500M", "12345678Z", ""):
        kept, migration = migrate_profile_facts(
            (*_KEPT, UserProfileFact(path=RETIRED_CLAVE_IDENTITY_PATH, value=value)), from_version=_PRIOR_VERSION
        )
        record = UserProfileRecord.model_construct(facts=kept)

        assert kept == _KEPT
        assert migration.cleared_paths == (RETIRED_CLAVE_IDENTITY_PATH,)
        assert pending_cleared_payer_fact_paths(record, (migration,)) == ()


def test_a_record_without_a_copy_migrates_with_nothing_cleared() -> None:
    kept, migration = migrate_profile_facts(_KEPT, from_version=_PRIOR_VERSION)

    assert kept == _KEPT
    assert migration.cleared_paths == ()
