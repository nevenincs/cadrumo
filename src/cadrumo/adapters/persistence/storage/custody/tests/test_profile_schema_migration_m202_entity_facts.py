"""The migration that adds the Modelo 202 page 01 entity facts, through the real capsule.

Schema 13 adds optional facts and changes no stored value. A schema-12 record
opens with every fact kept and nothing cleared; a schema-12 record that already
carries one of the new fields cannot exist and is refused.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from cadrumo.application.user_profile.capsule_record import ProfileRecordStore
from cadrumo.application.user_profile.profile_record_repository import ProfileRecordRepository
from cadrumo.application.user_profile.profile_schema_migration import drain_migration_cleared_paths
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext, ProfileDecodeContext
from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.schema_migration import (
    MIGRATED_PROFILE_SCHEMA_VERSION,
    PATHS_INTRODUCED_IN_V13,
    SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS,
    ProfileSchemaMigration,
    migrate_profile_facts,
)
from cadrumo.domain.user_profile.values import UserProfileFact

from .profile_record_boundary_support import PROFILE_ID
from .profile_schema_legacy_support import publish_legacy_capsule, record_session

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PRIOR_VERSION = 12
_KEPT = (
    UserProfileFact(path="identity.tax_id", value="B00015016"),
    UserProfileFact(path="taxpayer_type.entity_type", value="legal_entity"),
    UserProfileFact(path="taxpayer_type.pago_fraccionado_art_40_3_elected", value=False),
)


@pytest.fixture
def contexts() -> Iterator[tuple[ProfileCreateContext, ProfileDecodeContext]]:
    with bundled_indexed_authority().operation() as operation:
        yield operation.profile_create_context(), operation.profile_decode_context()


def test_schema_13_adds_page_01_entity_facts_the_schema_declares() -> None:
    with bundled_indexed_authority().operation() as operation:
        declared = frozenset(operation.profile_schema().field_paths)
    assert declared >= PATHS_INTRODUCED_IN_V13
    assert "taxpayer_type.principal_cnae" in PATHS_INTRODUCED_IN_V13
    assert _PRIOR_VERSION in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS
    assert MIGRATED_PROFILE_SCHEMA_VERSION > _PRIOR_VERSION + 1
    assert _PRIOR_VERSION + 1 in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS


def test_a_schema_12_record_opens_with_every_fact_kept_and_nothing_cleared(
    tmp_path: Path, contexts: tuple[ProfileCreateContext, ProfileDecodeContext]
) -> None:
    publish_legacy_capsule(
        tmp_path, facts=_KEPT, create_context=contexts[0], decode_context=contexts[1], version=_PRIOR_VERSION
    )
    drain_migration_cleared_paths()
    session = record_session(contexts[1])
    try:
        migrated = ProfileRecordRepository(session=session, root=tmp_path).load(PROFILE_ID)
        migrations = ProfileRecordStore(session=session, root=tmp_path).schema_migrations()
    finally:
        session.close()
        cleared = drain_migration_cleared_paths()

    assert migrated.facts == _KEPT
    assert migrated.schema_version == MIGRATED_PROFILE_SCHEMA_VERSION
    assert cleared == ()
    assert migrations == (
        ProfileSchemaMigration(from_version=_PRIOR_VERSION, to_version=MIGRATED_PROFILE_SCHEMA_VERSION),
    )


@pytest.mark.parametrize("path", sorted(PATHS_INTRODUCED_IN_V13))
def test_a_schema_12_record_cannot_carry_a_schema_13_fact(path: str) -> None:
    with pytest.raises(UserProfileValidationError):
        migrate_profile_facts((*_KEPT, UserProfileFact(path=path, value="6201")), from_version=_PRIOR_VERSION)
