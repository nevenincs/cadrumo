"""The migration that adds the LIS art. 40.3 election, through the real capsule.

Schema 10 adds one optional fact and changes no stored value. A schema-9 record
opens with every fact kept and nothing cleared, and the migration is recorded
as history; a schema-9 record that already carries the new field cannot exist
and is refused.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.profile_schema_migration import drain_migration_cleared_paths
from cadrumo.domain.buckets.event import BucketEventType
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.schema_migration import (
    MIGRATED_PROFILE_SCHEMA_VERSION,
    PATHS_INTRODUCED_IN_V10,
    SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS,
    ProfileSchemaMigration,
    migrate_profile_facts,
)
from cadrumo.domain.user_profile.values import UserProfileFact

from .profile_record_boundary_support import PROFILE_ID
from .profile_schema_legacy_support import publish_legacy_capsule, record_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PRIOR_VERSION = 9
_ELECTION_PATH = "taxpayer_type.pago_fraccionado_art_40_3_elected"
_KEPT = (
    UserProfileFact(path="identity.tax_id", value="B00015016"),
    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
    UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=False),
)


@pytest.fixture
def contexts() -> Iterator[tuple[ProfileCreateContext, ProfileDecodeContext]]:
    with bundled_indexed_authority().operation() as operation:
        yield operation.profile_create_context(), operation.profile_decode_context()


def test_the_election_is_the_one_field_schema_10_adds() -> None:
    assert frozenset({_ELECTION_PATH}) == PATHS_INTRODUCED_IN_V10
    assert _PRIOR_VERSION in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS
    assert MIGRATED_PROFILE_SCHEMA_VERSION > _PRIOR_VERSION


def test_a_schema_9_record_opens_with_every_fact_kept_and_nothing_cleared(
    tmp_path: Path, contexts: tuple[ProfileCreateContext, ProfileDecodeContext]
) -> None:
    publish_legacy_capsule(
        tmp_path, facts=_KEPT, create_context=contexts[0], decode_context=contexts[1], version=_PRIOR_VERSION
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
    assert migrated.schema_version == MIGRATED_PROFILE_SCHEMA_VERSION
    assert cleared == ()
    assert migrations == (
        ProfileSchemaMigration(from_version=_PRIOR_VERSION, to_version=MIGRATED_PROFILE_SCHEMA_VERSION),
    )
    assert len(events) == 1
    assert events[0].payload["schema_migration_from"] == str(_PRIOR_VERSION)
    assert events[0].payload["schema_migration_cleared_paths"] == ""


def test_a_schema_9_record_cannot_carry_the_election() -> None:
    with pytest.raises(UserProfileValidationError):
        migrate_profile_facts(
            (*_KEPT, UserProfileFact(path=_ELECTION_PATH, value=True)),
            from_version=_PRIOR_VERSION,
        )


@pytest.mark.parametrize("stated", [True, False])
def test_the_transform_keeps_every_schema_9_fact(stated: bool) -> None:
    """The transition clears nothing, so even a stored false survives it."""
    facts = (*_KEPT, UserProfileFact(path="taxpayer_type.new_entity_first_two_profit_periods", value=stated))
    kept, migration = migrate_profile_facts(facts, from_version=_PRIOR_VERSION)
    assert kept == facts
    assert migration.cleared_paths == ()
