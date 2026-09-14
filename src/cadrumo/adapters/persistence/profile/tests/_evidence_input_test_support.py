"""Shared real setup for evidence input byte-resolution tests."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.storage.tests.secure_sql import TestRuntimeProfile
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.application.ledger.evidence import PurchaseInvoiceEvidence, PurchaseInvoiceEvidenceService
from cadrumo.application.ledger.evidence_input_ports import EvidenceInputPorts
from cadrumo.core.config import Settings
from cadrumo.core.document_shape import DocumentShape
from cadrumo.entrypoints.adapter_composition import build_ledger_evidence_ports

_PDF_BYTES = b"%PDF-1.4 evidence-input-roundtrip body"
_BUCKET_ID = "30303030-3030-4030-8030-303030303030"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


@pytest.fixture
def evidence_input_ports() -> EvidenceInputPorts:
    """Provide an inward fake for the content-shape capability."""

    def probe(data: bytes) -> DocumentShape:
        if data.startswith(b"%PDF-"):
            return DocumentShape.PDF_TEXT_LAYER
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return DocumentShape.IMAGE
        return DocumentShape.UNKNOWN

    return EvidenceInputPorts(document_shape_probe=probe)


@pytest.fixture
def isolated_settings(runtime_profile: TestRuntimeProfile) -> Settings:
    """Expose the real profile settings to persistence integration tests."""

    return runtime_profile.settings


@pytest.fixture
def secure_objects(runtime_profile: TestRuntimeProfile) -> SecureObjectRepository:
    """Expose the profile-bound secure repository to persistence tests."""

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
    del isolated_settings, secure_objects
    return PurchaseInvoiceEvidenceService(
        ports=build_ledger_evidence_ports(bucket_id=_BUCKET_ID),
    )


def _pdf_sha256() -> str:
    return hashlib.sha256(_PDF_BYTES).hexdigest()
