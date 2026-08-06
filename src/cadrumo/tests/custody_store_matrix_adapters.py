"""Real adapter exports for the custody-store recovery matrix test."""

from __future__ import annotations

from ..adapters.outbound.aeat.sede import (
    FiledDeclaracionArtefact,
    FiledDeclaracionObservation,
    FiledDeclaracionObservationStore,
    IvaCompensationWalletObservation,
    IvaCompensationWalletRow,
)
from ..adapters.persistence.profile.assets import AmortizacionLedgerRepository, AssetsLedgerRepository
from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.profile.filing_amendments import ModeloAmendmentRepository
from ..adapters.persistence.profile.filing_drafts import ModeloDraftRepository
from ..adapters.persistence.profile.inventory import InventoryLedgerRepository
from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ..adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ..adapters.persistence.profile.submission import SubmissionRepository
from ..adapters.persistence.profile.usage_ratios import load_usage_ratios, save_usage_ratios
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_active_bucket

__all__ = [
    "AmortizacionLedgerRepository",
    "AssetsLedgerRepository",
    "BucketEventHistoryRepository",
    "FiledDeclaracionArtefact",
    "FiledDeclaracionObservation",
    "FiledDeclaracionObservationStore",
    "InventoryLedgerRepository",
    "InvoiceCatalogueRepository",
    "IvaCompensationWalletObservation",
    "IvaCompensationWalletRow",
    "ModeloAmendmentRepository",
    "ModeloDraftRepository",
    "SubmissionRepository",
    "VerificationReportCatalogueRepository",
    "load_usage_ratios",
    "save_usage_ratios",
    "secure_object_repository_for_active_bucket",
]
