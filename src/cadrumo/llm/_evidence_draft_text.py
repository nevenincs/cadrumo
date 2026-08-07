"""Semantic invoice-field extraction from a document's TEXT representation.

Reading a rendered document is two questions, not one, and the vision reader
answers them together. :func:`.extract_invoice_fields_from_images` hands rasterised pages to a vision
model, which collapses *reading the page* and *understanding the page* into one
call -- when the result is wrong there is no way to tell a transcription error
from a reasoning error, and a perfect transcription obtained by any other means
has nowhere to go.

This module is the missing second stage: text in, grounded
:class:`~application.ledger.InvoiceDraft` out. Splitting it out means the
transcription stage can be swapped, measured or replaced independently of the
understanding stage, and it makes any already-transcribed text -- a PDF text
layer, an OCR result, an EN16931 payload rendered back to prose -- usable.

**No provider pin.** Unlike the vision reader, which hard-pins
:attr:`~adapters.outbound.llm.LLMProvider.LOCAL` because a rasterised invoice
page is raw evidence that must never leave the host, this reader runs on
whatever provider the caller has configured. That is deliberate: the extractor
itself makes no persistence and no transport decision, and the sensitive-data
posture governing whether a given text may be sent anywhere is owned by the
calling flow's consent gate, not by this primitive. Callers handling
undisclosed evidence keep passing a LOCAL-configured client.

**Language-neutral by design.** The vision prompt opens "a scanned Spanish
invoice"; invoices reaching this path are international, in arbitrary languages
and layouts, so the prompt names field *concepts* and lets the model find them
under whatever heading the document uses. What it does not relax is the safety
contract: copy printed values verbatim, never calculate or infer, and emit
``null`` for anything not printed. Grounded re-validation
(:func:`~llm._invoice_field_grounding.ground_extracted_fields`) then re-checks
every field against an independent authority, so a fabricated value is dropped
even if the prompt fails to prevent it.

See Also:
    :class:`~application.ledger.InvoiceDraft`
        Typed draft this reader returns after grounded re-validation.
    :func:`~llm._invoice_field_grounding.ground_extracted_fields`
        Shared grounded re-validation this reader and the vision reader both use.
    :func:`.extract_invoice_fields_from_images`
        Sibling reader for evidence carrying no text at all.
"""

from __future__ import annotations

import asyncio

from ..application.ledger import InvoiceDraft, PurchaseInvoiceEvidenceInputError
from ..core import FieldOrigin, Period
from ..core.config import Settings, load_settings
from ._client import LLMClient
from ._invoice_extraction_prompt import (
    CompiledInvoiceExtractionPrompt,
    build_invoice_extraction_prompt,
    default_extraction_period,
)
from ._invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response
from ._models import LLMRequest

__all__ = [
    "TextInvoiceFieldExtractor",
    "build_text_field_extraction_prompt",
    "extract_invoice_fields_from_text",
]


def build_text_field_extraction_prompt(evidence_text: str, *, period: Period | None = None) -> str:
    """Build the extraction prompt for ``evidence_text``.

    Separate from the transport so the exact instruction a model will receive is
    directly assertable without dispatching a request.

    The instruction half is the SHARED compiled artefact
    (:func:`~llm._invoice_extraction_prompt.build_invoice_extraction_prompt`),
    not a second hand-maintained field list: this reader and the vision reader
    ask for the same eight fields in the same declared forms, and maintaining
    that agreement by hand is exactly the drift that lost a correctly-read rate.

    Args:
        evidence_text: The document's text representation.
        period: Optional filing period whose registry-resolved rates the prompt
            enumerates; defaults to the current annual period.

    Returns:
        The full prompt: instructions, then the document text under a delimiter
        that tells the model where its own instructions end.

    Raises:
        PurchaseInvoiceEvidenceInputError: When ``evidence_text`` is blank, which
            would otherwise ask a model to read nothing and invite it to invent
            an entire invoice.
    """
    if not evidence_text.strip():
        raise PurchaseInvoiceEvidenceInputError(
            "invoice text extraction was given no text to read",
            suggestion="aeat app ledger evidence extract --evidence-id <id>",
        )
    compiled = build_invoice_extraction_prompt(period=period if period is not None else default_extraction_period())
    return f"{compiled.text}\nINVOICE TEXT:\n{evidence_text}"


class TextInvoiceFieldExtractor:
    """Read an invoice's text with a language model into a grounded :class:`InvoiceDraft`.

    Args:
        model: Optional model identifier override; ``None`` uses the configured
            model for whichever provider is active.
        client: Injected :class:`~adapters.outbound.llm.LLMClient` (dependency
            injection for tests); default-constructed against the resolved
            settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
        period: Filing period whose registry-resolved rates the compiled prompt
            enumerates; defaults to the current annual period.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        period: Period | None = None,
    ) -> None:
        resolved_settings = settings if settings is not None else load_settings()
        self._model = model
        self._period = period if period is not None else default_extraction_period()
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=resolved_settings,
                caller="cadrumo.llm.evidence_draft_text",
                prompt_id="ledger-invoice-text-extract",
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp for this extractor's transport.

        Distinct from the vision stamp so a persisted record always says which
        reader produced the fields. The model segment is ``configured`` when the
        caller pinned nothing, because the effective model is then the active
        provider's default rather than a fact this object holds.

        The trailing rate-provenance token answers the question the model name
        cannot: the prompt now enumerates registry-resolved rates, so which
        rates were in force for this read is part of how the figure was reached.
        """
        return f"llm:text-extract:{self._model or 'configured'}:rates-{self._compiled_prompt().rate_provenance}"

    def extract(self, *, evidence_text: str) -> InvoiceDraft:
        """Read ``evidence_text`` and return the grounded draft.

        Args:
            evidence_text: The document's text representation.

        Returns:
            :class:`InvoiceDraft`: Every field the model reported AND that passed
            grounded re-validation; everything else is ``None``.
        """
        response = asyncio.run(self._client.complete(self._build_request(evidence_text)))
        parsed = parse_invoice_extraction_response(response.text)
        # `raw_text_length` reports how much source material the reader had to
        # work with, matching the text-layer heuristic path's semantics -- here
        # that is the document text handed in, not the model's reply.
        #
        # TEXT_LAYER, not VISION: a model read the MEANING here, but it read it
        # off text some earlier stage had already extracted, so the characters
        # behind every value came from the document rather than from a
        # rasterised page. Claiming VISION would overstate how the bytes were
        # acquired; the probabilistic step is recorded by the grounding outcome.
        return ground_extracted_fields(
            parsed,
            raw_text_length=len(evidence_text),
            origin=FieldOrigin.TEXT_LAYER,
        )

    def _build_request(self, evidence_text: str) -> LLMRequest:
        """Build the completion request for ``evidence_text``.

        Carries no ``provider_override``: the active provider is whatever the
        caller configured, which is what lets this reader run against a hosted
        model on a host with no inference capacity of its own.
        """
        return LLMRequest(
            prompt=build_text_field_extraction_prompt(evidence_text, period=self._period),
            model_override=self._model,
        )

    def _compiled_prompt(self) -> CompiledInvoiceExtractionPrompt:
        """Return the compiled instruction half this reader sends.

        Built without any document text, so the stamp can name the rates a read
        was performed under without a document in hand.
        """
        return build_invoice_extraction_prompt(period=self._period)


def extract_invoice_fields_from_text(
    evidence_text: str,
    *,
    model: str | None = None,
    settings: Settings | None = None,
) -> InvoiceDraft:
    """Convenience wrapper: build a :class:`TextInvoiceFieldExtractor` and extract.

    Args:
        evidence_text: The document's text representation.
        model: Optional model override.
        settings: Optional resolved settings override.

    Returns:
        :class:`InvoiceDraft`: The grounded, best-effort extracted fields.
    """
    extractor = TextInvoiceFieldExtractor(model=model, settings=settings)
    return extractor.extract(evidence_text=evidence_text)
