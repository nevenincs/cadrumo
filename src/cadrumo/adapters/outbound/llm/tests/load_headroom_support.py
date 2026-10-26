"""Measured hardware readings for LLM dispatch tests.

The dispatch point refuses an on-host lane's model unless a measured reading
shows headroom for the size its catalogue entry states, and it fails closed on
a machine whose free memory it cannot read. A test whose subject is the transport, the prompt or the reply
must therefore state the measurement it runs under; left to the host, the same
case admits on a workstation with a readable accelerator and refuses on a
runner without one.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

import httpx

from .....application.ledger.document_transcription import DocumentTranscription
from .....application.ledger.invoice_draft_extraction_ports import (
    EvidenceConsentProof,
    InvoiceDraftExtractionPorts,
    InvoiceDraftReaderUnavailableError,
    VisionImage,
)
from .....application.ledger.invoice_draft_records import InvoiceDraft
from .....application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
from .....application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
)
from .....core.config import Settings
from .....core.hardware import AcceleratorKind
from .....core.optional_extras import MissingOptionalExtraError
from .....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..client import LLMClient
from ..errors import LLMProviderError
from ..evidence_draft_text import TextInvoiceFieldExtractor
from ..evidence_draft_vision import VISION_TRANSCRIPTION_PROMPT_ID, VisionDocumentTranscriber
from ..models import MultimodalImageInput
from ..supply_nature_proposal import SUPPLY_NATURE_PROMPT_ID, SupplyNatureProposal, SupplyNatureProposer


def measured_hardware_profile(
    *,
    free_vram_bytes: int | None,
    free_ram_bytes: int,
    total_vram_bytes: int,
    total_ram_bytes: int,
) -> HardwareProfile:
    """Build a measured reading of one accelerator device and system memory."""
    return HardwareProfile(
        memory=SystemMemoryReading(total_bytes=total_ram_bytes, free_bytes=free_ram_bytes),
        accelerator=AcceleratorReading(
            kind=AcceleratorKind.NVIDIA_CUDA,
            devices=(
                AcceleratorDevice(
                    index=0,
                    name="probe device",
                    total_vram_bytes=total_vram_bytes,
                    free_vram_bytes=free_vram_bytes,
                ),
            ),
        ),
    )


#: The size a test lane's catalogue entry states for its model, which an admitting reading holds exactly.
ADMITTED_REQUIREMENT_BYTES = 2 * 1024**3


def admitting_hardware_profile(*, settings: Settings) -> HardwareProfile:
    """A measured reading with exactly the headroom a lane of :data:`ADMITTED_REQUIREMENT_BYTES` needs.

    The figure is that size plus the configured safety margin, so the real
    admission comparison runs and admits at its boundary rather than being
    bypassed for an on-host lane that states its size.
    """
    required = ADMITTED_REQUIREMENT_BYTES + settings.cadrumo_llm_contention_safety_margin_bytes
    return measured_hardware_profile(
        free_vram_bytes=required,
        free_ram_bytes=required,
        total_vram_bytes=required,
        total_ram_bytes=required,
    )


def admitting_client(*, settings: Settings, caller: str, prompt_id: str) -> LLMClient:
    """A client carrying ``caller``/``prompt_id`` under a measurement that admits the lane's load.

    Each reader stamps its own caller and prompt identity on the request it
    builds, and usage and run record are keyed on them. A test that injects a
    client must therefore repeat the identity the reader would have set, or it
    moves the very records some of these cases assert on.
    """
    return LLMClient(
        settings=settings,
        caller=caller,
        prompt_id=prompt_id,
        hardware_profile=admitting_hardware_profile(settings=settings),
        runtime_residents=(),
    )


def admitting_text_extraction_client(*, settings: Settings) -> LLMClient:
    """An admitting client with the invoice-text reader's identity."""
    return admitting_client(
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.evidence_draft_text",
        prompt_id="ledger-invoice-text-extract",
    )


def admitting_vision_transcription_client(*, settings: Settings) -> LLMClient:
    """An admitting client with the vision-transcription reader's identity."""
    return admitting_client(
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.evidence_vision_transcription",
        prompt_id=VISION_TRANSCRIPTION_PROMPT_ID,
    )


def admitting_supply_nature_client(*, settings: Settings) -> LLMClient:
    """An admitting client with the supply-nature proposer's identity."""
    return admitting_client(
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.supply_nature_proposal",
        prompt_id=SUPPLY_NATURE_PROMPT_ID,
    )


def transcribe_document_images_under_admitted_load(
    evidence_images: tuple[MultimodalImageInput, ...],
    *,
    source_content_sha256: str,
    settings: Settings,
) -> DocumentTranscription:
    """Transcribe evidence images through the agent, as the router does, under an admitting measurement."""
    return VisionDocumentTranscriber(
        client=admitting_vision_transcription_client(settings=settings),
        settings=settings,
    ).transcribe(evidence_images=evidence_images, source_content_sha256=source_content_sha256)


def propose_supply_nature_under_admitted_load(lines: Sequence[str], *, settings: Settings) -> SupplyNatureProposal:
    """Propose an invoice's supply nature on the LOCAL route, under an admitting measurement."""
    proposer = SupplyNatureProposer(settings=settings, client=admitting_supply_nature_client(settings=settings))
    return proposer.propose(list(lines))


def extraction_ports_under_admitted_load(ports: InvoiceDraftExtractionPorts) -> InvoiceDraftExtractionPorts:
    """Return ``ports`` with each ON-HOST reader dispatch under an admitting measurement.

    Mirrors the composition root's own local branches, including where the
    authority operation is opened: per call, from the bundled indexed authority,
    so the read runs under the same authority production gives it and only the
    client's measured reading differs. A read carrying an off-host consent
    token is delegated back to ``ports`` untouched, because a lane that reads
    off host is never assessed for on-host headroom.

    The reader-unavailable wrapping is reproduced too: these ports are the ones
    the extraction use case reads through, and it distinguishes an unavailable
    reader from a refusal.
    """

    def read_text(
        transcription: DocumentTranscription,
        settings: Settings,
        consent_token: EvidenceConsentProof | None,
        authority_values: object,
    ) -> InvoiceDraft:
        if consent_token is not None:
            return ports.read_text(transcription, settings, consent_token, authority_values)
        try:
            if not isinstance(authority_values, InvoiceExtractionAuthorityValues):
                raise TypeError("text reader requires resolved invoice extraction authority values")
            with bundled_indexed_authority().operation() as operation:
                return extract_invoice_text_under_admitted_load(
                    transcription,
                    settings=settings,
                    authority_values=authority_values,
                    operation=operation,
                )
        except (MissingOptionalExtraError, LLMProviderError, httpx.HTTPError) as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    def propose_supply_nature(
        transcription: DocumentTranscription, settings: Settings, consent_token: EvidenceConsentProof | None
    ) -> SupplyNatureProposal | None:
        del consent_token
        try:
            return propose_supply_nature_under_admitted_load(transcription.text.splitlines(), settings=settings)
        except Exception:
            return None

    def transcribe_vision(
        images: tuple[VisionImage, ...],
        source_content_sha256: str,
        settings: Settings,
        consent_token: EvidenceConsentProof | None,
    ) -> DocumentTranscription:
        if consent_token is not None:
            return ports.transcribe_vision(images, source_content_sha256, settings, consent_token)
        try:
            inputs = tuple(MultimodalImageInput.from_base64(image.base64_data, image.media_type) for image in images)
            return transcribe_document_images_under_admitted_load(
                inputs, source_content_sha256=source_content_sha256, settings=settings
            )
        except (MissingOptionalExtraError, LLMProviderError, httpx.HTTPError) as exc:
            raise InvoiceDraftReaderUnavailableError(exc) from exc

    return replace(
        ports,
        read_text=read_text,
        propose_supply_nature=propose_supply_nature,
        transcribe_vision=transcribe_vision,
    )


def extract_invoice_text_under_admitted_load(
    transcription: DocumentTranscription,
    *,
    settings: Settings,
    authority_values: InvoiceExtractionAuthorityValues,
    operation: PinnedAuthorityOperation,
) -> InvoiceDraft:
    """Read an invoice's text through the agent, as the evidence router does, under an admitting measurement.

    The client carries the reader's own caller and prompt identity, so usage
    and run record are recorded exactly as the router's read records them.
    """
    return TextInvoiceFieldExtractor(
        client=admitting_text_extraction_client(settings=settings),
        settings=settings,
        operation=operation,
        authority_values=authority_values,
    ).extract(transcription=transcription)
