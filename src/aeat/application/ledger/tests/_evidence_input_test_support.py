"""Shared real setup for evidence input byte-resolution tests."""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from pathlib import Path

import pytest

from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....core.config import Settings
from ....domain.buckets import BucketEventHistoryRepository
from ....tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .._evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService

_PDF_BYTES = b"%PDF-1.4 evidence-input-roundtrip body"
_BUCKET_ID = "30303030-3030-4030-8030-303030303030"


@pytest.fixture
def runtime_profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as profile:
        yield profile


@pytest.fixture
def isolated_settings(runtime_profile: TestRuntimeProfile) -> Settings:
    return runtime_profile.settings


@pytest.fixture
def secure_objects(runtime_profile: TestRuntimeProfile) -> SecureObjectRepository:
    return runtime_profile.repository


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    p = tmp_path / "invoice.pdf"
    p.write_bytes(_PDF_BYTES)
    return p


def _added_record(
    isolated_settings: Settings,
    secure_objects: SecureObjectRepository,
    pdf_file: Path,
) -> PurchaseInvoiceEvidence:
    svc = _make_svc(isolated_settings, secure_objects)
    return svc.add(bucket_id=_BUCKET_ID, source_path=pdf_file).record


def _make_svc(isolated_settings: Settings, secure_objects: SecureObjectRepository) -> PurchaseInvoiceEvidenceService:
    return PurchaseInvoiceEvidenceService(
        settings=isolated_settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=secure_objects),
    )


def _pdf_sha256() -> str:
    return hashlib.sha256(_PDF_BYTES).hexdigest()
