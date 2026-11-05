"""A complete, general-regime natural-person profile seeded for work-unit suites.

The taxpayer is the catalogue's general-regime autonomo, so identity comes from
the persona catalogue rather than from values restated in a test.
"""

from __future__ import annotations

from datetime import datetime

from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.domain.user_profile.tests.general_regime_facts import GENERAL_REGIME_NATURAL_PERSON_FACTS
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test
from cadrumo.tests.personas import identity_catalogue

_TAXPAYER_ROLE = "fontanero.titular"


def _ready_profile_facts() -> tuple[UserProfileFact, ...]:
    taxpayer = identity_catalogue().role(_TAXPAYER_ROLE)
    return (
        UserProfileFact(path="identity.tax_id", value=taxpayer.value),
        UserProfileFact(path="identity.name", value=taxpayer.field("name")),
        UserProfileFact(path="identity.surnames", value=taxpayer.field("surnames")),
        UserProfileFact(path="activities.description", value="economic activity"),
        *GENERAL_REGIME_NATURAL_PERSON_FACTS,
        UserProfileFact(path="provenance.source", value="manual_cli"),
        # Modelo 111 refuses a defaulted colegio-concertado declaration, and the
        # natural-person filer truthfully states False.
        UserProfileFact(path="withholding.colegio_concertado", value=False),
    )


def seed_ready_profile(*, bucket_id: str, at: datetime) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_ready_profile_facts(),
            created_at=at,
            updated_at=at,
            context=_profile_creation_context_for_test(),
        ),
    )
