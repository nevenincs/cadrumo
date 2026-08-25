"""Persistence-owned support for local-vision evidence tests."""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..application.ledger import PurchaseInvoiceEvidenceService
from .secure_sql import TestRuntimeProfile, isolated_runtime_profile

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        yield runtime


def _scan_only_pdf() -> bytes:
    """Return a one-page raster, text-layer-free PDF."""
    buffer = BytesIO()
    Image.new("RGB", (260, 160), "white").save(buffer, format="PDF")
    return buffer.getvalue()


def _add_evidence(profile: TestRuntimeProfile, tmp_path: Path, *, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    service = PurchaseInvoiceEvidenceService(
        settings=profile.settings,
        bucket_event_repository=BucketEventHistoryRepository(objects=profile.repository),
    )
    return service.add(bucket_id=_BUCKET_ID, source_path=path).record.evidence_id
