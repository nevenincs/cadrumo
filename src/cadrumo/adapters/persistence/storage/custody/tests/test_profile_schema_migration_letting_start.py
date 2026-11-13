"""The schema-14 transition that adds the letting start of a property clears nothing and refuses an early carrier."""

from __future__ import annotations

import pytest

from cadrumo.domain.user_profile.errors import UserProfileValidationError
from cadrumo.domain.user_profile.schema_migration import (
    MIGRATED_PROFILE_SCHEMA_VERSION,
    SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS,
    ProfileSchemaMigration,
    cleared_payer_fact_paths_between,
    migrate_profile_facts,
)
from cadrumo.domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PRIOR_VERSION = 13
_KEPT = (
    UserProfileFact(path="identity.tax_id", value="X0001500M"),
    UserProfileFact(path="renta_inmueble.0.situacion", value="5"),
    UserProfileFact(path="renta_inmueble.0.fecha_adquisicion", value="2020-03-04"),
)


def test_schema_14_is_the_written_schema_and_schema_13_still_opens() -> None:
    assert MIGRATED_PROFILE_SCHEMA_VERSION == _PRIOR_VERSION + 1
    assert _PRIOR_VERSION in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS


def test_the_transition_out_of_schema_13_clears_nothing() -> None:
    assert cleared_payer_fact_paths_between(_PRIOR_VERSION, MIGRATED_PROFILE_SCHEMA_VERSION) == frozenset()

    kept, migration = migrate_profile_facts(_KEPT, from_version=_PRIOR_VERSION)

    assert kept == _KEPT
    assert migration == ProfileSchemaMigration(
        from_version=_PRIOR_VERSION, to_version=MIGRATED_PROFILE_SCHEMA_VERSION, cleared_paths=()
    )


@pytest.mark.parametrize("leaf", ["arrendado_desde", "sin_arrendar"])
def test_a_schema_13_record_carrying_a_schema_14_leaf_is_refused(leaf: str) -> None:
    carrier = UserProfileFact(path=f"renta_inmueble.0.{leaf}", value="2022-06-01")

    with pytest.raises(UserProfileValidationError):
        migrate_profile_facts((*_KEPT, carrier), from_version=_PRIOR_VERSION)


def test_an_older_record_crosses_to_schema_14_without_gaining_a_letting_start() -> None:
    kept, migration = migrate_profile_facts(_KEPT, from_version=9)

    assert kept == _KEPT
    assert migration.to_version == MIGRATED_PROFILE_SCHEMA_VERSION
    assert not any(fact.path.endswith(("arrendado_desde", "sin_arrendar")) for fact in kept)
