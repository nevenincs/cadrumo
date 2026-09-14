"""Shared real setup for purchase invoice evidence tests."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from cadrumo.adapters.persistence.profile.buckets import BucketEventHistoryRepository
from cadrumo.adapters.persistence.profile.purchase_invoice_evidence import (
    LedgerEvidenceAttachmentIngestor,
    LedgerEvidenceRepositoryAdapter,
)
from cadrumo.adapters.persistence.storage.attachment import AttachmentStore
from cadrumo.adapters.persistence.storage.sql.secure_objects import SecureObjectRepository
from cadrumo.adapters.persistence.tests.runtime_profile_fixture import bucket_scoped_runtime_profile_fixture
from cadrumo.adapters.persistence.storage.tests.profile_capsule_runtime import seed_test_profile_record
from cadrumo.application.ledger.counterparty_establishment import ConfirmedCounterpartyFacts
from cadrumo.application.ledger.counterparty_establishment_ports import CounterpartyEstablishmentRepositoryProtocol
from cadrumo.application.ledger.evidence import PurchaseInvoiceEvidenceService
from cadrumo.application.ledger.evidence_ports import LedgerEvidencePorts
from cadrumo.application.ledger.filer_establishment import FILER_POSTCODE_FACT_PATH
from cadrumo.core.config import Settings
from cadrumo.domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord

_BUCKET_ID = "29292929-2929-4929-8929-292929292929"

runtime_profile = bucket_scoped_runtime_profile_fixture(_BUCKET_ID, autouse=False, name="runtime_profile")


class _InMemoryCounterpartyEstablishmentRepository(CounterpartyEstablishmentRepositoryProtocol):
    """Inward fake for structured-path tests that exercise policy resolution."""

    def __init__(self) -> None:
        self._records: dict[str, ConfirmedCounterpartyFacts] = {}

    def load(self, identifier: str) -> ConfirmedCounterpartyFacts | None:
        return self._records.get(identifier)

    def save(self, payload: ConfirmedCounterpartyFacts) -> None:
        self._records[payload.counterparty_key] = payload

    def delete(self, identifier: str) -> bool:
        return self._records.pop(identifier, None) is not None


@pytest.fixture
def repository() -> CounterpartyEstablishmentRepositoryProtocol:
    """Provide an inward policy capability for structured-path assertions."""
    return _InMemoryCounterpartyEstablishmentRepository()


def _make_svc(isolated_settings: Settings, objects: SecureObjectRepository) -> PurchaseInvoiceEvidenceService:
    del isolated_settings
    return PurchaseInvoiceEvidenceService(
        ports=LedgerEvidencePorts(
            evidence_repository=LedgerEvidenceRepositoryAdapter(objects=objects),
            attachment_ingestor=LedgerEvidenceAttachmentIngestor(store=AttachmentStore(objects=objects)),
            bucket_event_repository=BucketEventHistoryRepository(objects=objects),
        ),
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


@pytest.fixture
def isolated_settings(runtime_profile) -> Settings:
    return runtime_profile.settings


@pytest.fixture
def secure_objects(runtime_profile) -> SecureObjectRepository:
    return runtime_profile.repository


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "receipt.pdf"
    path.write_bytes(b"%PDF-1.4 test")
    return path
