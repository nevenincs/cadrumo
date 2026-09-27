"""Measured hardware readings for LLM dispatch tests.

The dispatch point refuses a catalogued local model unless a measured reading
shows headroom for it, and it fails closed on a machine whose free memory it
cannot read. A test whose subject is the transport, the prompt or the reply
must therefore state the measurement it runs under; left to the host, the same
case admits on a workstation with a readable accelerator and refuses on a
runner without one.
"""

from __future__ import annotations

from collections.abc import Sequence

from .....application.ledger.document_transcription import DocumentTranscription
from .....application.ledger.invoice_draft_records import InvoiceDraft
from .....application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
from .....application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    ModelRole,
    SystemMemoryReading,
    select_model_for_role,
)
from .....core.config import Settings
from .....core.config_support import LLMProvider
from .....core.hardware import AcceleratorKind
from .....core.model_catalogue import model_candidate
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.iva.supply_nature import SupplyNature
from ..client import LLMClient
from ..evidence_draft_text import TextInvoiceFieldExtractor
from ..evidence_draft_vision import VISION_TRANSCRIPTION_PROMPT_ID, LocalVisionDocumentTranscriber
from ..models import MultimodalImageInput
from ..supply_nature_proposal import SUPPLY_NATURE_PROMPT_ID, SupplyNatureProposer


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


def admitting_hardware_profile(model: str, *, settings: Settings) -> HardwareProfile:
    """A measured reading with exactly the headroom ``model`` needs under ``settings``.

    The figure is the catalogue's declared requirement plus the configured
    safety margin, so the real admission comparison runs and admits at its
    boundary rather than being bypassed.
    """
    candidate = model_candidate(model)
    requirement = (
        0 if candidate is None or candidate.memory_requirement_bytes is None else candidate.memory_requirement_bytes
    )
    required = requirement + settings.cadrumo_llm_contention_safety_margin_bytes
    return measured_hardware_profile(
        free_vram_bytes=required,
        free_ram_bytes=required,
        total_vram_bytes=required,
        total_ram_bytes=required,
    )


def admitting_client(
    model: str,
    *,
    settings: Settings,
    caller: str,
    prompt_id: str,
) -> LLMClient:
    """A client carrying ``caller``/``prompt_id`` under a measurement that admits ``model``.

    Each reader stamps its own caller and prompt identity on the request it
    builds, and usage and run telemetry are keyed on them. A test that injects a
    client must therefore repeat the identity the reader would have set, or it
    moves the very records some of these cases assert on.
    """
    return LLMClient(
        settings=settings,
        caller=caller,
        prompt_id=prompt_id,
        hardware_profile=admitting_hardware_profile(model, settings=settings),
        runtime_residents=(),
    )


def admitting_text_extraction_client(*, settings: Settings) -> LLMClient:
    """An admitting client with the invoice-text reader's identity."""
    return admitting_client(
        settings.cadrumo_llm_ollama_text_model,
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.evidence_draft_text",
        prompt_id="ledger-invoice-text-extract",
    )


def admitting_vision_transcription_client(*, settings: Settings) -> LLMClient:
    """An admitting client with the vision-transcription reader's identity."""
    return admitting_client(
        settings.cadrumo_llm_ollama_vision_model,
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.evidence_vision_transcription",
        prompt_id=VISION_TRANSCRIPTION_PROMPT_ID,
    )


def admitting_vision_classify_client(*, settings: Settings, model: str | None = None) -> LLMClient:
    """An admitting client with the vision-classifier reader's identity."""
    return admitting_client(
        settings.cadrumo_llm_ollama_vision_model if model is None else model,
        settings=settings,
        caller="cadrumo.application.ledger.vision",
        prompt_id="ledger-vision-classify",
    )


def admitting_text_classify_client(*, settings: Settings, model: str | None = None) -> LLMClient:
    """An admitting client with the text-classifier reader's identity."""
    return admitting_client(
        settings.cadrumo_llm_ollama_text_model if model is None else model,
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.text",
        prompt_id="ledger-text-classify",
    )


def admitting_supply_nature_client(*, settings: Settings) -> LLMClient:
    """An admitting client with the supply-nature proposer's identity.

    The proposer dispatches the model its ROLE selects rather than a configured
    default, so the measurement is sized to that selection.
    """
    selection = select_model_for_role(ModelRole.SUPPLY_NATURE_PROPOSAL, settings=settings)
    assert selection.runtime_id is not None, "the supply-nature role selects no model to dispatch to"
    return admitting_client(
        selection.runtime_id,
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
    """Transcribe evidence images on the LOCAL route the router pins, under an admitting measurement."""
    return LocalVisionDocumentTranscriber(
        provider=LLMProvider.LOCAL,
        client=admitting_vision_transcription_client(settings=settings),
        settings=settings,
    ).transcribe(evidence_images=evidence_images, source_content_sha256=source_content_sha256)


def propose_supply_nature_under_admitted_load(lines: Sequence[str], *, settings: Settings) -> SupplyNature | None:
    """Propose an invoice's supply nature on the LOCAL route, under an admitting measurement."""
    proposer = SupplyNatureProposer(settings=settings, client=admitting_supply_nature_client(settings=settings))
    return proposer.propose(list(lines)).nature


def extract_invoice_text_under_admitted_load(
    transcription: DocumentTranscription,
    *,
    settings: Settings,
    authority_values: InvoiceExtractionAuthorityValues,
    operation: PinnedAuthorityOperation,
) -> InvoiceDraft:
    """Read an invoice's text on the LOCAL route the evidence router pins, under an admitting measurement.

    The client carries the reader's own caller and prompt identity, so usage
    and run telemetry are recorded exactly as the router's read records them.
    """
    return TextInvoiceFieldExtractor(
        provider=LLMProvider.LOCAL,
        client=admitting_text_extraction_client(settings=settings),
        settings=settings,
        operation=operation,
        authority_values=authority_values,
    ).extract(transcription=transcription)
