"""Shared real setup for purchase invoice evidence tests."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....core.config import Settings
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ....tests.profile_capsule import seed_test_profile_record
from ..evidence import PurchaseInvoiceEvidenceService
from ..filer_establishment import FILER_POSTCODE_FACT_PATH

_BUCKET_ID = "29292929-2929-4929-8929-292929292929"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


def _make_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> PurchaseInvoiceEvidenceService:
    return PurchaseInvoiceEvidenceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def _event_repo(objects: SecureObjectRepository) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=objects)


def seed_filer_profile(*, tax_id: str | None = "12345678Z") -> None:
    """Seed the filer profile the evidence draft path reads its territory from.

    Resolving a purchase invoice needs the taxpayer's own IVA territory, which
    comes from the fiscal-address postcode and never from the invoice, so an
    evidence test without a profile refuses before reaching what it asserts.
    A caller that must leave the identity guards inert passes ``tax_id=None``;
    the current profile record then establishes the filer's territory without
    claiming a taxpayer identity.
    """
    clock = datetime(2026, 1, 1, tzinfo=UTC)
    facts = [UserProfileFact(path=FILER_POSTCODE_FACT_PATH, value="28001")]
    if tax_id is not None:
        facts.insert(0, UserProfileFact(path="identity.tax_id", value=tax_id))
    seed_test_profile_record(
        UserProfileRecord(
            setup_state=ProfileSetupState.COMPLETE,
            profile_id=_BUCKET_ID,
            facts=tuple(facts),
            created_at=clock,
            updated_at=clock,
        ),
    )


@pytest.fixture(autouse=True)
def seeded_filer_profile(secure_objects: SecureObjectRepository) -> None:
    seed_filer_profile()
