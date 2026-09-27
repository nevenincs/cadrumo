"""Measured hardware readings for LLM dispatch tests.

The dispatch point refuses a catalogued local model unless a measured reading
shows headroom for it, and it fails closed on a machine whose free memory it
cannot read. A test whose subject is the transport, the prompt or the reply
must therefore state the measurement it runs under; left to the host, the same
case admits on a workstation with a readable accelerator and refuses on a
runner without one.
"""

from __future__ import annotations

from .....application.ledger.document_transcription import DocumentTranscription
from .....application.ledger.invoice_draft_records import InvoiceDraft
from .....application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues
from .....application.provisioning import (
    AcceleratorDevice,
    AcceleratorReading,
    HardwareProfile,
    SystemMemoryReading,
)
from .....core.config import Settings
from .....core.config_support import LLMProvider
from .....core.hardware import AcceleratorKind
from .....core.model_catalogue import model_candidate
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from ..client import LLMClient
from ..evidence_draft_text import TextInvoiceFieldExtractor


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
    client = LLMClient(
        settings=settings,
        caller="cadrumo.adapters.outbound.llm.evidence_draft_text",
        prompt_id="ledger-invoice-text-extract",
        hardware_profile=admitting_hardware_profile(settings.cadrumo_llm_ollama_text_model, settings=settings),
        runtime_residents=(),
    )
    return TextInvoiceFieldExtractor(
        provider=LLMProvider.LOCAL,
        client=client,
        settings=settings,
        operation=operation,
        authority_values=authority_values,
    ).extract(transcription=transcription)
