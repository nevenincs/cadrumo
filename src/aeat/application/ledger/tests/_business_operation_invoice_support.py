"""Shared support for business operation invoice application tests."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.buckets import BucketEventHistoryRepository
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._business_operation_invoice import CollectibleInvoiceService, PayableInvoiceService

_BUCKET_ID = "34343434-3434-4434-8434-343434343434"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def isolated_settings(runtime_profile: TestRuntimeProfile) -> Settings:
    """Fresh per-test settings rooted in a real active runtime profile."""
    return runtime_profile.settings


@pytest.fixture
def secure_objects(runtime_profile: TestRuntimeProfile) -> SecureObjectRepository:
    return runtime_profile.repository


def _make_payable_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> PayableInvoiceService:
    return PayableInvoiceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )


def _make_collectible_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> CollectibleInvoiceService:
    return CollectibleInvoiceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=objects),
    )
