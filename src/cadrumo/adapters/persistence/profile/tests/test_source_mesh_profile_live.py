"""Profile-persistence integration coverage for live profile source resolution."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime
from functools import cache
from pathlib import Path

import pytest

from cadrumo.domain.user_profile.tests.profile_creation_authority import (
    profile_creation_context_for_test,
)

from .....application.aggregation.source_mesh import CalculationSourceContext
from .....application.aggregation.source_profile import ProfileSourceResolver
from .....application.user_profile.tests.profile_values import complete_profile_facts
from .....core.period import Period
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.tests.published_authority import published_profile_schema
from .....domain.user_profile.values import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    create_user_profile_record,
)
from ...storage.tests.profile_capsule_runtime import seed_test_profile_record
from ...storage.tests.secure_sql import isolated_runtime_profile
from .published_authority_support import published_authority_operation

pytestmark = [pytest.mark.integration, pytest.mark.hex_persistence_adapter]

_CLOCK = datetime(2026, 5, 21, 10, 0, 0, tzinfo=UTC)
_PROFILE_ID = "10010010-0100-4100-8100-100100100100"
_BUCKET_ID = _PROFILE_ID
_CCAA_BINDING = "renta-profile-tax-residence-ccaa"


@pytest.fixture
def secure_profile_backend(tmp_path: Path) -> Iterator[None]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID):
        yield


@cache
def _modelo_100_snapshot() -> RegistrySnapshot:
    return published_authority_operation().snapshot("100", filing_year=2025, period="0A")


def _profile_with_ccaa(ccaa: str) -> UserProfileRecord:
    # A COMPLETE fixture must pass the completion door, so every other owed fact is stated too.
    return create_user_profile_record(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=complete_profile_facts(
            published_profile_schema(),
            (
                UserProfileFact(path="identity.tax_id", value="12345678Ñ"),
                UserProfileFact(path="tax_residence.ccaa", value=ccaa),
            ),
        ),
        created_at=_CLOCK,
        updated_at=_CLOCK,
        context=profile_creation_context_for_test(),
    )


def test_profile_source_resolver_fingerprints_storage_loaded_profile(
    secure_profile_backend: None,
    operation: PinnedAuthorityOperation,
) -> None:
    snapshot = _modelo_100_snapshot()
    profile_record = _profile_with_ccaa("madrid")
    seed_test_profile_record(profile_record)

    resolution = ProfileSourceResolver(registry_snapshot=snapshot, operation=operation).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )

    assert resolution.enum_binding_values[_CCAA_BINDING] == "madrid"
    repeated = ProfileSourceResolver(registry_snapshot=snapshot, operation=operation).resolve(
        CalculationSourceContext(
            bucket_id=_BUCKET_ID,
            modelo="100",
            filing_year=2025,
            period=Period.from_year_and_code(2025, "0A"),
            revision=snapshot.revision,
        ),
    )
    assert {item.fingerprint for item in resolution.provenance if item.contributor_source_kind == "profile"} == {
        item.fingerprint for item in repeated.provenance
    }
    assert all(item.fingerprint for item in resolution.provenance)
