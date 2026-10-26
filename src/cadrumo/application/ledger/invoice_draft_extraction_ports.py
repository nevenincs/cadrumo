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
from ...core.errors.hierarchy import CadrumoError
from ...core.image_media_type import ImageMediaType
from ...domain.iva.supply_nature import SupplyNature
from ..operator_actions.models import PreconditionVerdict
from .document_transcription import DocumentTranscription
from .evidence_input import EvidenceInput
from .evidence_input_ports import EvidenceInputPorts
from .evidence_textlayer_ports import EvidenceTextLayerPorts
from .invoice_draft_records import InvoiceDraft
from .structured_invoice_ports import StructuredInvoiceReader


class EvidenceConsentProof(Protocol):
    """Minimum consent fact the use case needs to bind evidence bytes."""

    @property
    def evidence_content_address(self) -> str:
        """Return the content address covered by the consent proof."""
        ...


@dataclass(frozen=True)
class VisionImage:
    """In-memory image prepared by the application for a vision reader."""

    base64_data: str
    media_type: ImageMediaType


class StructuredInvoiceReadError(CadrumoError):
    """A structured document could not be read by the selected exact reader."""


class InvoiceDraftReaderUnavailableError(CadrumoError):
    """Selected reader or its runtime was unavailable; preserve its cause.

    ``precondition_verdict`` is the reader probe's own refusal when the probe
    knows why the reader cannot run -- the runtime does not answer, or the
    role's model is not installed -- so the extraction refuses, or records its
    label fallback, with the cause and the setup action the probe named rather
    than a generic reader failure. ``None`` when no probe answered for it.
    """

    def __init__(self, cause: Exception, *, precondition_verdict: PreconditionVerdict | None = None) -> None:
        """Create an unavailable-reader error while preserving its cause and the probe's verdict."""
        super().__init__(str(cause))
        self.cause = cause
        self.precondition_verdict = precondition_verdict


class SupplyNatureProposalResult(Protocol):
    """What a supply-nature proposer answers: the nature it proposed, or why no model was asked."""

    @property
    def nature(self) -> SupplyNature | None:
        """Return the proposed nature, or ``None`` when nothing was proposed."""
        ...

    @property
    def reader_unavailable(self) -> PreconditionVerdict | None:
        """Return the reader probe's verdict when the on-host reader could not be asked."""
        ...


class InvoiceDraftReaderHeadroomRefusedError(CadrumoError):
    """The agent refused to load the selected reader's model: it does not fit the memory free.

    The model was never loaded. Kept apart from
    :class:`InvoiceDraftReaderUnavailableError` because the two end differently
    when the read cannot stand without the model: an unavailable reader becomes
    the extraction's own reader refusal, while this refusal IS the load decision
    and is re-raised exactly as the agent's refusal arrived. ``cause`` keeps that
    refusal, and ``failed_condition_id`` names the precondition it failed.
    """

    def __init__(self, cause: Exception, *, failed_condition_id: str | None) -> None:
        """Create a headroom-refused error while preserving the refusal as its cause."""
        super().__init__(str(cause))
        self.cause = cause
        self.failed_condition_id = failed_condition_id


class InvoiceDraftReaderBusyRefusedError(CadrumoError):
    """Admission control refused the read because every on-host inference slot was occupied.

    The occupancy sibling of :class:`InvoiceDraftReaderHeadroomRefusedError`:
    another read already holds the machine's inference slots, so this one was
    refused before any request reached the runtime and no model was loaded for
    it. It ends the way the headroom refusal does -- an optional fill leaves the
    label reading standing, and a read that cannot stand without the model
    re-raises ``cause`` exactly as admission control raised it -- but it is a
    different condition with a different remedy, waiting for the other read
    rather than freeing memory, so it keeps its own type. ``failed_condition_id``
    names the precondition it failed.
    """

    def __init__(self, cause: Exception, *, failed_condition_id: str | None) -> None:
        """Create a busy-refused error while preserving the refusal as its cause."""
        super().__init__(str(cause))
        self.cause = cause
        self.failed_condition_id = failed_condition_id


@dataclass(frozen=True)
class InvoiceDraftExtractionPorts:
    """Concrete capabilities supplied by an outer composition root."""

    resolve_evidence_input: Callable[[str, str | None, str | None, Settings], EvidenceInput]
    evidence_input_ports: EvidenceInputPorts
    text_layer_ports: EvidenceTextLayerPorts
    parse_structured_invoice: StructuredInvoiceReader
    read_text: Callable[[DocumentTranscription, Settings, EvidenceConsentProof | None, object], InvoiceDraft]
    propose_supply_nature: Callable[
        [DocumentTranscription, Settings, EvidenceConsentProof | None], SupplyNatureProposalResult | None
    ]
    """Propose goods-or-services for a person to confirm; ``None`` when there is nothing to report.

    A reader that could not be asked answers with its verdict on
    ``reader_unavailable`` rather than raising: the proposal is optional, so
    its absence never refuses a read. The consent proof is the one the read
    already carries; a lane that reads off-host is refused without it.
    """
    rasterise_pdf: Callable[[bytes], tuple[str, ...]]
    transcribe_vision: Callable[
        [tuple[VisionImage, ...], str, Settings, EvidenceConsentProof | None], DocumentTranscription
    ]
    consent_binding_error: Callable[[dict[str, object]], Exception]


__all__ = [
    "EvidenceConsentProof",
    "InvoiceDraftExtractionPorts",
    "InvoiceDraftReaderBusyRefusedError",
    "InvoiceDraftReaderHeadroomRefusedError",
    "InvoiceDraftReaderUnavailableError",
    "StructuredInvoiceReadError",
    "SupplyNatureProposalResult",
    "VisionImage",
]
