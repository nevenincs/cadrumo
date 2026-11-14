"""The schema-15 transition that adds the Modelo 840 facts clears nothing and refuses an early carrier."""

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

_PRIOR_VERSION = 14
_KEPT = (
    UserProfileFact(path="identity.tax_id", value="X0001500M"),
    UserProfileFact(path="activities.description", value="Actividad sintetica"),
    UserProfileFact(path="contact.postcode", value="28001"),
)


def test_schema_15_is_the_written_schema_and_schema_14_still_opens() -> None:
    assert MIGRATED_PROFILE_SCHEMA_VERSION == _PRIOR_VERSION + 1
    assert _PRIOR_VERSION in SUPPORTED_LEGACY_PROFILE_SCHEMA_VERSIONS


def test_the_transition_out_of_schema_14_clears_nothing() -> None:
    assert cleared_payer_fact_paths_between(_PRIOR_VERSION, MIGRATED_PROFILE_SCHEMA_VERSION) == frozenset()

    kept, migration = migrate_profile_facts(_KEPT, from_version=_PRIOR_VERSION)

    assert kept == _KEPT
    assert migration == ProfileSchemaMigration(
        from_version=_PRIOR_VERSION, to_version=MIGRATED_PROFILE_SCHEMA_VERSION, cleared_paths=()
    )


@pytest.mark.parametrize(
    "path",
    [
        "censo.aeat_delegacion_code",
        "contact.fiscal_address_municipality_code",
        "activities.0.local_afecto_indirectamente",
        "iae_local.0.afectacion",
        "iae_local_superficie.0.clase",
        "iae_elemento_tributario.0.linea",
    ],
)
def test_a_schema_14_record_carrying_a_schema_15_path_is_refused(path: str) -> None:
    carrier = UserProfileFact(path=path, value="1")

    with pytest.raises(UserProfileValidationError):
        migrate_profile_facts((*_KEPT, carrier), from_version=_PRIOR_VERSION)


def test_an_older_record_crosses_to_schema_15_without_gaining_a_modelo_840_fact() -> None:
    kept, migration = migrate_profile_facts(_KEPT, from_version=9)

    assert kept == _KEPT
    assert migration.to_version == MIGRATED_PROFILE_SCHEMA_VERSION
