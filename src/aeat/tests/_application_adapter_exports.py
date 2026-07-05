"""Real adapter exports for application-layer roundtrip tests."""

from __future__ import annotations

from ..adapters.outbound.llm import LLMRunRecord, LLMRunTelemetryRecorder
from ..adapters.persistence.profile.bienes_inversion import BienesInversionIvaRegisterRepository
from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.profile.invoices import InvoiceCatalogueRepository
from ..adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ..adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ..adapters.persistence.profile.modelos_work_units import WorkUnitCatalogueRepository
from ..adapters.persistence.profile.transactions import TransactionCatalogueRepository
from ..adapters.persistence.storage import M145_COMMUNICATION_RECORD_NAMESPACE
from ..adapters.persistence.storage.attachment import AttachmentStore
from ..adapters.persistence.storage.bucket import (
    BucketLifecycleStatus,
    bucket_paths,
    manifest_path,
    provision_bucket_directory,
    read_manifest,
)
from ..adapters.persistence.storage.sql import SecureObjectRepository

__all__ = [
    "M145_COMMUNICATION_RECORD_NAMESPACE",
    "AttachmentStore",
    "BienesInversionIvaRegisterRepository",
    "BucketEventHistoryRepository",
    "BucketLifecycleStatus",
    "CalculationRevisionCatalogueRepository",
    "InvoiceCatalogueRepository",
    "LLMRunRecord",
    "LLMRunTelemetryRecorder",
    "ModeloRecordCatalogueRepository",
    "SecureObjectRepository",
    "TransactionCatalogueRepository",
    "WorkUnitCatalogueRepository",
    "bucket_paths",
    "manifest_path",
    "provision_bucket_directory",
    "read_manifest",
]
