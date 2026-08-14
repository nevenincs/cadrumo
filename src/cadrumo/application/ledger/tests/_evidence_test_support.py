"""Shared real setup for purchase invoice evidence tests."""

from __future__ import annotations

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....core.config import Settings
from .._evidence import PurchaseInvoiceEvidenceService

_BUCKET_ID = "29292929-2929-4929-8929-292929292929"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


def _make_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> PurchaseInvoiceEvidenceService:
    return PurchaseInvoiceEvidenceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def _event_repo(objects: SecureObjectRepository) -> BucketEventHistoryRepository:
    return BucketEventHistoryRepository(objects=objects)
