"""Shared real setup for evidence input byte-resolution tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ....adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ....adapters.persistence.storage.sql import SecureObjectRepository
from ....adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from ....core.config import Settings
from ..evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService

_PDF_BYTES = b"%PDF-1.4 evidence-input-roundtrip body"
_BUCKET_ID = "30303030-3030-4030-8030-303030303030"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


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
