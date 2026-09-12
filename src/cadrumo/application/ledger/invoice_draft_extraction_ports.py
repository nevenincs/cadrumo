"""Application-owned dependencies for invoice-draft extraction.

The extraction use case decides *when* an evidence reader is needed.  This
module names the capabilities it needs; outer composition chooses the concrete
e-invoice, LLM, and secure-storage implementations.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ...core.config import Settings
from ...core.config_support import LLMProvider
from ...core.image_media_type import ImageMediaType
from ...domain.iva.supply_nature import SupplyNature
from .document_transcription import DocumentTranscription
from .evidence_input import EvidenceInput
from .invoice_draft_records import InvoiceDraft


class EvidenceConsentProof(Protocol):
    """Minimum consent fact the use case needs to bind evidence bytes."""

    @property
    def evidence_content_address(self) -> str: ...


@dataclass(frozen=True)
class VisionImage:
    """In-memory image prepared by the application for a vision reader."""

    base64_data: str
    media_type: ImageMediaType


class StructuredInvoiceReadError(Exception):
    """A structured document could not be read by the selected exact reader."""


class InvoiceDraftReaderUnavailableError(Exception):
    """Selected reader or its runtime was unavailable; preserve its cause."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(str(cause))
        self.cause = cause


@dataclass(frozen=True)
class InvoiceDraftExtractionPorts:
    """Concrete capabilities supplied by an outer composition root."""

    resolve_evidence_input: Callable[[str, str | None, str | None, Settings], EvidenceInput]
    parse_structured_invoice: Callable[[bytes], object]
    read_text: Callable[
        [DocumentTranscription, Settings, LLMProvider | None, EvidenceConsentProof | None, object], InvoiceDraft
    ]
    propose_supply_nature: Callable[[DocumentTranscription, Settings], SupplyNature | None]
    rasterise_pdf: Callable[[bytes], tuple[str, ...]]
    transcribe_vision: Callable[
        [tuple[VisionImage, ...], str, Settings, LLMProvider | None, EvidenceConsentProof | None], DocumentTranscription
    ]
    consent_binding_error: Callable[[dict[str, object]], Exception]


__all__ = [
    "EvidenceConsentProof",
    "InvoiceDraftExtractionPorts",
    "InvoiceDraftReaderUnavailableError",
    "StructuredInvoiceReadError",
    "VisionImage",
]
