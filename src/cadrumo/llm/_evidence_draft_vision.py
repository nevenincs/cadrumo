"""On-host vision fallback for invoice-field extraction from a scan-only PDF or image.

:func:`~application.ledger.extract_invoice_fields` reads a PDF's embedded text
layer. A scan-only or image-only invoice has no text layer at all, so that
primitive raises. This module supplies the on-host fallback: rasterise the PDF
(or use an image directly) into in-memory base64 PNG pages
(:func:`~adapters.outbound.llm.rasterise_pdf_pages_to_base64_png`) and read them
with the same LOCAL Ollama vision model the classification path already uses
(:class:`~llm._vision_classifier.LocalVisionLLMClassifier`), fully on-host
(``sensitive-financial-data-secure-storage-only``). Nothing is written to disk and
nothing leaves the machine; this needs no cloud consent gate.

The vision model's role here is strictly *transcription*, never *derivation*: the
prompt instructs it to copy each field's printed value verbatim (or emit ``null``
when a field is not visibly printed) and forbids it from computing, inferring, or
estimating any figure. Every field the model returns is re-validated through the
exact same grounded heuristics the text-layer path uses --
:func:`~core.identity.validate_spanish_tax_id`,
:func:`~core.parsing.parse_date`, and :class:`~decimal.Decimal` parsing via
:func:`~core.decimal.normalize_decimal_separators` -- so a malformed or
hallucinated value is rejected (left ``None``) rather than trusted. This mirrors the
document-printed-value semantics
:func:`~application.ledger.extract_invoice_fields` already has for text-layer PDFs:
both paths recover what is *printed on the
document*, never a registry-derived or model-computed tax figure
(``evidence-read-never-emits-regulated-numbers`` in spirit -- the persisted
:class:`~domain.invoices.Invoice` this draft eventually confirms into still goes
through the operator review step before anything is minted).

Gated by :attr:`~core.ServiceCapability.LLM_VISION`: an operator who has opted
out of on-host vision reading gets a typed refusal naming the capability toggle,
never a silent empty draft.

See Also:
    :class:`~application.ledger.InvoiceDraft`
        Typed draft this vision path returns after grounded re-validation.
    :func:`~llm._invoice_field_grounding.ground_extracted_fields`
        Transport-neutral response schema, parser and grounded re-validation
        this module shares with the text reader; only the prompt and the
        request payload differ between the two.
    :func:`~application.ledger.extract_invoice_fields`
        Text-layer extraction primitive this module complements for scan-only
        or image-only evidence.
    :func:`~application.ledger.extract_invoice_draft_from_evidence`
        Orchestration layer that falls back to this on-host reader.
    :class:`~llm._vision_classifier.LocalVisionLLMClassifier`
        Sibling local Ollama vision transport used for classification and
        split suggestions.
"""

from __future__ import annotations

import asyncio

from ..application.ledger import InvoiceDraft
from ..core import Period
from ..core.config import Settings, load_settings
from ._client import LLMClient
from ._errors import LLMConfigError
from ._invoice_extraction_prompt import (
    CompiledInvoiceExtractionPrompt,
    build_invoice_extraction_prompt,
    default_extraction_period,
)
from ._invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response
from ._models import LLMProvider, LLMRequest, MultimodalImageInput

__all__ = [
    "LocalVisionInvoiceFieldExtractor",
    "extract_invoice_fields_from_images",
]


class LocalVisionInvoiceFieldExtractor:
    """Read an invoice image on-host with a local Ollama vision model into an :class:`InvoiceDraft`.

    Mirrors :class:`~llm._vision_classifier.LocalVisionLLMClassifier`'s transport
    (a local Ollama vision model fed in-memory base64 images) but for field
    transcription instead of category classification. Every returned field is
    re-validated through the grounded heuristics
    :func:`~application.ledger.extract_invoice_fields` uses for the text-layer path,
    so a hallucinated or malformed value never reaches the operator as a
    fabricated fact.

    Args:
        model: Local Ollama vision model identifier; defaults to
            ``Settings.cadrumo_llm_ollama_vision_model``.
        client: Injected :class:`~adapters.outbound.llm.LLMClient` (dependency
            injection for tests); default-constructed against the resolved
            settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: LLMProvider = LLMProvider.LOCAL,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        period: Period | None = None,
    ) -> None:
        resolved_settings = settings if settings is not None else load_settings()
        self._provider = provider
        self._prompt: CompiledInvoiceExtractionPrompt = build_invoice_extraction_prompt(
            period=period if period is not None else default_extraction_period(),
        )
        if provider is LLMProvider.LOCAL:
            self._model = model if model is not None else resolved_settings.cadrumo_llm_ollama_vision_model
        elif model is None:
            # The only default that exists is the local Ollama vision model, and
            # forwarding that identifier to another vendor asks for a model it
            # does not serve. Refuse rather than send a name that cannot resolve.
            msg = f"a vision model must be named explicitly for provider {provider.value!r}; no default exists for it"
            raise LLMConfigError(msg, suggestion="pass model=<vendor vision model id>")
        else:
            self._model = model
        # A local vision model on consumer hardware can take minutes; give the
        # vision read its own (longer) timeout, mirroring LocalVisionLLMClassifier.
        vision_settings = resolved_settings.model_copy(
            update={"cadrumo_llm_default_timeout_s": resolved_settings.cadrumo_llm_vision_read_timeout_s},
        )
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=vision_settings,
                caller="cadrumo.application.ledger.evidence_draft_vision",
                prompt_id="ledger-invoice-vision-extract",
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp: transport, model, AND the rates the prompt was compiled from.

        The transport half is DERIVED from the provider actually used, never
        written as a constant. A stamp is the only durable record of how a
        figure was reached, so one that says ``local`` for a read served
        off-host is worse than no stamp at all: it answers the audit question
        confidently and wrongly.

        The same reasoning extends the stamp past the model. Now that the prompt
        enumerates registry-resolved rates, two reads by the same model under
        different filing periods are different reads, and a stamp naming only
        the model cannot answer "under which rates was this figure read?". The
        trailing
        :attr:`~llm._invoice_extraction_prompt.CompiledInvoiceExtractionPrompt.rate_provenance`
        token carries the resolved period and the compiled prompt's content
        fingerprint, so a registry change that moves a rate moves the stamp.
        """
        transport = "local" if self._provider is LLMProvider.LOCAL else self._provider.value.lower()
        return f"llm:{transport}-vision:{self._model}:rates-{self._prompt.rate_provenance}"

    def extract(self, *, evidence_images: tuple[MultimodalImageInput, ...]) -> InvoiceDraft:
        """Read ``evidence_images`` with the local vision model and return a grounded draft.

        Args:
            evidence_images: In-memory page/image renders of the evidence, each
                carrying its declared media type (built by the caller from
                :func:`~adapters.outbound.llm.rasterise_pdf_pages_to_base64_png`
                for a scan-only PDF, or from the raw bytes of an image
                attachment).

        Returns:
            :class:`InvoiceDraft`: Every field the model transcribed AND that
            passed grounded re-validation; everything else is ``None``.
        """
        request = LLMRequest(
            prompt=self._prompt.text,
            provider_override=self._provider,
            model_override=self._model,
            images=evidence_images,
        )
        response = asyncio.run(self._client.complete(request))
        parsed = parse_invoice_extraction_response(response.text)
        # `raw_text_length` on the vision path reports the length of the model's
        # own transcription text, mirroring the text-layer path's semantics of
        # "how much source material did the reader have to work with" -- here
        # that is the model's read-out rather than a pdfplumber page dump.
        return ground_extracted_fields(parsed, raw_text_length=len(response.text))


def extract_invoice_fields_from_images(
    evidence_images: tuple[MultimodalImageInput, ...],
    *,
    model: str | None = None,
    provider: LLMProvider = LLMProvider.LOCAL,
    settings: Settings | None = None,
    period: Period | None = None,
) -> InvoiceDraft:
    """Convenience wrapper: build a :class:`LocalVisionInvoiceFieldExtractor` and extract.

    Args:
        evidence_images: In-memory page/image renders of the evidence, each
            carrying its declared media type.
        model: Optional vision model override.
        provider: Transport serving the read. Defaults to
            :attr:`~adapters.outbound.llm.LLMProvider.LOCAL`, so the production
            route stays on-host; naming another provider is the caller's
            explicit, per-invocation decision to read off-host.
        settings: Optional resolved settings override.
        period: Optional filing period whose registry-resolved rates the prompt
            enumerates; defaults to the current annual period.

    Returns:
        :class:`InvoiceDraft`: The grounded, best-effort extracted fields.
    """
    extractor = LocalVisionInvoiceFieldExtractor(model=model, provider=provider, settings=settings, period=period)
    return extractor.extract(evidence_images=evidence_images)
