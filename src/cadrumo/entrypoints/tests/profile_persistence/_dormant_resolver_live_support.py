from __future__ import annotations

from datetime import UTC, date, datetime

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.domain.calculations.registry.schema import ModeloRevision
from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test as _profile_creation_context_for_test,
)
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact
from cadrumo.domain.user_profile.values import create_user_profile_record as _create_profile_record_for_test

from ....adapters.persistence.profile.tests.published_authority_support import published_authority_operation
from .general_iva_profile_facts_support import general_iva_profile_facts

_T0 = datetime(2026, 1, 10, 10, 0, tzinfo=UTC)
_T1 = datetime(2026, 1, 10, 11, 0, tzinfo=UTC)

_READY_PROFILE_FACTS: tuple[UserProfileFact, ...] = general_iva_profile_facts(
    tax_id="12345678Z",
    activity_start_date=date(2000, 1, 1),
    name="Ready",
    activity="design services",
)


def _seed_ready_profile(objects: SecureObjectRepository, *, bucket_id: str) -> None:
    seed_test_profile_record(
        _create_profile_record_for_test(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=bucket_id,
            facts=_READY_PROFILE_FACTS,
            created_at=_T0,
            updated_at=_T0,
            context=_profile_creation_context_for_test(),
        ),
    )


def _revision(modelo: str, revision_id: str) -> ModeloRevision:
    return published_authority_operation().revision_with_export_layouts(modelo, revision_id)
