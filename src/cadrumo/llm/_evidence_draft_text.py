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

**Defaults to LOCAL, like the vision reader.** This paragraph previously said
the opposite -- that the reader took whatever provider the caller had
configured, because "the sensitive-data posture is owned by the calling flow's
consent gate, not by this primitive". That reasoning was sound and the premise
was false: no such consent gate had been built, while the shipped provider
default is a cloud vendor. The two together meant reading a taxpayer's invoice
sent the document's text off-host by configuration alone, with nothing at the
call site expressing that choice.

The default is therefore stated here rather than inherited. An off-host read
stays possible -- the measurement corpus is public, synthetic and explicitly
sanctioned for it -- but requires naming BOTH the provider and the model, which
makes it a deliberate act at the call site instead of a property of the
environment. A named provider with no model refuses, mirroring the vision
reader's guard.

This is a floor, not the consent gate. The gate itself is
:meth:`~adapters.outbound.llm.LLMClient._require_evidence_consent`, applied at
the client's dispatch choke point where no caller can reach around it by
constructing a request directly: this reader marks every request it builds as
evidence-derived unless the caller names the public corpus, and an off-host
dispatch of a marked request without a per-invocation consent token refuses.

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

from ..application.ledger import DocumentTranscription, InvoiceDraft, PurchaseInvoiceEvidenceInputError
from ..core import Period
from ..core.config import Settings, load_settings
from ._client import LLMClient
from ._consent import EvidenceConsentToken
from ._errors import LLMConfigError
from ._invoice_extraction_prompt import (
    CompiledInvoiceExtractionPrompt,
    build_invoice_extraction_prompt,
    default_extraction_period,
)
from ._invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response
from ._models import LLMProvider, LLMRequest

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
        model: Optional model identifier; ``None`` uses the configured LOCAL
            text model. Required when ``provider`` is not LOCAL, because the
            only default that exists names a local model no vendor serves.
        provider: Which provider carries the read. Defaults to LOCAL so a
            taxpayer's document does not leave the host by default; naming a
            cloud provider is a deliberate call-site act.
        client: Injected :class:`~adapters.outbound.llm.LLMClient` (dependency
            injection for tests); default-constructed against the resolved
            settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
        period: Filing period whose registry-resolved rates the compiled prompt
            enumerates; defaults to the current annual period.
        consent_token: Per-invocation off-host consent proof, minted through
            :func:`~llm._consent.mint_evidence_consent_token`. Required only for
            an off-host read of real evidence; ``None`` is correct for every
            on-host read.
        public_corpus: Whether the text handed to this reader comes from the
            public, synthetic measurement corpus rather than from a taxpayer's
            document. Defaults to ``False`` -- the fail-closed direction, so a
            caller that says nothing gets the gate. Naming the corpus is the
            deliberate act, not naming the evidence.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: LLMProvider = LLMProvider.LOCAL,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        period: Period | None = None,
        consent_token: EvidenceConsentToken | None = None,
        public_corpus: bool = False,
    ) -> None:
        resolved_settings = settings if settings is not None else load_settings()
        self._provider = provider
        self._consent_token = consent_token
        self._public_corpus = public_corpus
        if provider is LLMProvider.LOCAL:
            self._model = model if model is not None else resolved_settings.cadrumo_llm_ollama_text_model
        elif model is None:
            # Mirrors the vision reader's guard, and closes the same hole from
            # the other side. The only default that exists is the local text
            # model, so forwarding that identifier to a vendor asks for a model
            # it does not serve -- and doing so SILENTLY is what let a
            # taxpayer's document reach a cloud provider by configuration alone.
            msg = f"a text model must be named explicitly for provider {provider.value!r}; no default exists for it"
            raise LLMConfigError(msg, suggestion="pass model=<vendor text model id>")
        else:
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
        """Provenance stamp: transport, reader, model, and the rates compiled in.

        Distinct from the vision stamp so a persisted record always says which
        reader produced the fields. The model segment is ``configured`` when the
        caller pinned nothing, because the effective model is then the active
        provider's default rather than a fact this object holds.

        The trailing rate-provenance token answers the question the model name
        cannot: the prompt now enumerates registry-resolved rates, so which
        rates were in force for this read is part of how the figure was reached.

        **The transport segment is DERIVED from the provider actually used**,
        matching the vision reader. It was previously absent, so this stamp
        could not say whether a read had left the host -- and a model name does
        not answer that, because a vendor model identifier reveals the vendor
        only to a reader who already knows the catalogue. A consent withdrawal
        enumerates cloud-derived artefacts BY this segment, so a stamp that
        omits it makes a withdrawal silently incomplete: the artefact that most
        needs re-deriving is the one the survey cannot see.
        """
        transport = "local" if self._provider is LLMProvider.LOCAL else self._provider.value.lower()
        model = self._model or "configured"
        return f"llm:{transport}-text-extract:{model}:rates-{self._compiled_prompt().rate_provenance}"

    def extract(self, *, transcription: DocumentTranscription) -> InvoiceDraft:
        """Read the acquisition-stage ``transcription`` and return the grounded draft.

        Takes the typed stage-1 artefact rather than a bare string, which is
        what makes this the second stage of a pipeline instead of a helper that
        happens to accept text. A string carries no answer to "who read these
        characters off the document", and that answer is not decoration: it is
        the ORIGIN stamped on every value this reader proposes, and the record
        of whether an independent reader produced the text its anchors are
        later checked against.

        Args:
            transcription: The acquisition-stage transcription, printed forms
                intact.

        Returns:
            :class:`InvoiceDraft`: Every field the model reported AND that passed
            grounded re-validation; everything else is ``None``.
        """
        response = asyncio.run(self._client.complete(self._build_request(transcription.text)))
        parsed = parse_invoice_extraction_response(response.text)
        # `raw_text_length` reports how much source material the reader had to
        # work with -- the transcription handed in, not the model's reply.
        #
        # The origin is the TRANSCRIBER'S, read off the artefact rather than
        # asserted here. This stage reads MEANING; it never touches the
        # document, so it has nothing to say about how the characters were
        # acquired and must not overwrite the stage that does. Hardcoding
        # TEXT_LAYER was defensible while a text layer was the only thing that
        # could reach this reader; once a vision transcription can, it would
        # launder a rasterised read into an exact-looking one -- the precise
        # distinction `FieldOrigin` exists to keep.
        return ground_extracted_fields(
            parsed,
            raw_text_length=len(transcription.text),
            origin=transcription.transcriber.origin,
        )

    def _build_request(self, evidence_text: str) -> LLMRequest:
        """Build the completion request for ``evidence_text``.

        Carries an EXPLICIT ``provider_override``. It previously carried none,
        so the provider was whatever the settings resolved to -- and the shipped
        default is a cloud vendor, which meant reading a taxpayer's invoice sent
        the document's text off-host by configuration alone, with nothing at the
        call site saying so.

        The default is now :attr:`~adapters.outbound.llm.LLMProvider.LOCAL` and
        it is stated here rather than inherited, because the confidentiality
        guarantee is that sensitive financial data stays on the host. Running
        this reader against a hosted model remains possible, but only by naming
        both the provider and the model, which makes the off-host read a
        deliberate act at the call site instead of a property of the
        environment.
        """
        return LLMRequest(
            prompt=build_text_field_extraction_prompt(evidence_text, period=self._period),
            provider_override=self._provider,
            model_override=self._model,
            evidence_derived=not self._public_corpus,
            consent_token=self._consent_token,
        )

    def _compiled_prompt(self) -> CompiledInvoiceExtractionPrompt:
        """Return the compiled instruction half this reader sends.

        Built without any document text, so the stamp can name the rates a read
        was performed under without a document in hand.
        """
        return build_invoice_extraction_prompt(period=self._period)


def extract_invoice_fields_from_text(
    transcription: DocumentTranscription,
    *,
    model: str | None = None,
    settings: Settings | None = None,
) -> InvoiceDraft:
    """Convenience wrapper: build a :class:`TextInvoiceFieldExtractor` and extract.

    This is the entry point the evidence router calls, and it takes no provider
    argument. The provider is therefore pinned LOCAL, and the pin is written out
    below rather than inherited from the extractor's default: a pin held by NOT
    passing an argument is the weakest possible statement of a confidentiality
    property, because widening this signature with a pass-through ``provider``
    would open the off-host route for every router call without a single diff
    line that looks like a confidentiality change.

    The pin is documentation, not the boundary. Widening this signature cannot
    actually send a taxpayer's document off-host, because the extractor marks
    every request it builds as evidence-derived and
    :meth:`~adapters.outbound.llm.LLMClient._require_evidence_consent` refuses a
    marked request at any off-host provider without a per-invocation consent
    token. That is the property to preserve if this signature ever changes: the
    refusal lives below this function, not in it.

    Args:
        transcription: The acquisition-stage transcription to read.
        model: Optional model override.
        settings: Optional resolved settings override.

    Returns:
        :class:`InvoiceDraft`: The grounded, best-effort extracted fields.
    """
    extractor = TextInvoiceFieldExtractor(model=model, settings=settings, provider=LLMProvider.LOCAL)
    return extractor.extract(transcription=transcription)
