"""Persistence-owned support for local-vision evidence tests."""

from __future__ import annotations

from collections.abc import Iterator
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from .....application.ledger.evidence import PurchaseInvoiceEvidenceService
from ....persistence.storage.tests.secure_sql import TestRuntimeProfile, isolated_runtime_profile
from .....entrypoints.adapter_composition import build_ledger_evidence_ports

_BUCKET_ID = "33333333-3333-4333-8333-333333333333"


@pytest.fixture
def profile(tmp_path: Path) -> Iterator[TestRuntimeProfile]:
    with isolated_runtime_profile(tmp_path=tmp_path, bucket_id=_BUCKET_ID) as runtime:
        yield runtime


def scan_only_pdf() -> bytes:
    """Return a one-page raster, text-layer-free PDF."""
    buffer = BytesIO()
    Image.new("RGB", (260, 160), "white").save(buffer, format="PDF")
    return buffer.getvalue()


def add_evidence(profile: TestRuntimeProfile, tmp_path: Path, *, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    service = PurchaseInvoiceEvidenceService(
        ports=build_ledger_evidence_ports(bucket_id=_BUCKET_ID),
    )
    return service.add(bucket_id=_BUCKET_ID, source_path=path).record.evidence_id
