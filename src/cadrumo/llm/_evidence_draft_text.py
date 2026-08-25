"""Semantic invoice-field extraction from a document's TEXT representation.

Reading a rendered document is two questions, not one. The vision reader once
answered them together, handing rasterised pages to a model and taking back
typed fields in a single call -- so when the result was wrong there was no way
to tell a transcription error from a reasoning error, and a perfect
transcription obtained by any other means had nowhere to go.

This module is the second stage that made splitting them possible: text in,
grounded :class:`~application.ledger.evidence_draft.InvoiceDraft` out. Both acquisition lanes
now feed it -- the deterministic text-layer extractor and
:class:`~llm.LocalVisionDocumentTranscriber`, which transcribes and interprets
nothing. Splitting it out means the
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
:class:`LLMClient`'s per-invocation evidence-consent check, applied at
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
    :class:`~application.ledger.evidence_draft.InvoiceDraft`
        Typed draft this reader returns after grounded re-validation.
    :func:`~llm._invoice_field_grounding.ground_extracted_fields`
        Shared grounded re-validation this reader and the vision reader both use.
    :func:`~llm.transcribe_document_images`
        Sibling ACQUISITION stage for evidence carrying no text layer at all.
        It produces the transcription this reader consumes; it does not read
        fields.
"""

from __future__ import annotations

import asyncio
from collections.abc import Collection

from ..application.ledger.document_transcription import DocumentTranscription
from ..application.ledger.evidence_draft import InvoiceDraft
from ..application.ledger.invoice_extraction_authority import InvoiceExtractionAuthorityValues, resolve_invoice_extraction_authority_values
from ..application.ledger.evidence import PurchaseInvoiceEvidenceInputError
from ..core import LLM_EXTRA, ActionEvidenceProvenance, build_provenance_stamp, require_optional_extra
from ..core.config import Settings, load_settings
from ._client import LLMClient
from ._consent import EvidenceConsentToken
from ._errors import LLMConfigError
from ._invoice_extraction_prompt import (
    CompiledInvoiceExtractionPrompt,
    default_extraction_period,
    render_invoice_extraction_prompt,
)
from ._invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response
from ._models import LLMProvider, LLMRequest
from ._preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

__all__ = [
    "TextInvoiceFieldExtractor",
    "build_text_field_extraction_prompt",
    "default_extraction_authority_values",
    "extract_invoice_fields_from_text",
]


def default_extraction_authority_values() -> InvoiceExtractionAuthorityValues:
    """Resolve the authority values for the fallback period.

    The one place this package turns "no values were supplied" into values, and
    it does so by asking the application layer's compiler rather than by reading
    any authority itself.

    Returns:
        :class:`~application.ledger.invoice_extraction_authority.InvoiceExtractionAuthorityValues`: The values
        in force across the current civil year.
    """
    return resolve_invoice_extraction_authority_values(period=default_extraction_period())


def build_text_field_extraction_prompt(
    evidence_text: str,
    *,
    values: InvoiceExtractionAuthorityValues | None = None,
    fields: Collection[str] | None = None,
) -> str:
    """Build the extraction prompt for ``evidence_text``.

    Separate from the transport so the exact instruction a model will receive is
    directly assertable without dispatching a request.

    The instruction half is the SHARED rendered artefact
    (:func:`~llm._invoice_extraction_prompt.render_invoice_extraction_prompt`),
    not a second hand-maintained field list: this reader and the vision reader
    ask for the same eight fields in the same declared forms, and maintaining
    that agreement by hand is exactly the drift that lost a correctly-read rate.

    Args:
        evidence_text: The document's text representation.
        values: Regulatory values to enumerate, resolved by the application
            layer. ``None`` resolves the current civil year's, which is the
            honest fallback for a document not yet bound to a filing period.
        fields: The field names to ask for, or ``None`` for every declared
            field. Passed to the shared compiler unchanged; the selection is
            validated there against the declaration, so a name this reader does
            not recognise refuses in the one place that knows the vocabulary
            rather than being silently dropped on the way.

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
            precondition_verdict=llm_no_recovery_verdict(
                LLMPreconditionCondition.EVIDENCE_TEXT_PRESENT,
                facts={"evidence_content_available": False},
                provenance=ActionEvidenceProvenance.APPLICATION_STATE,
            ),
        )
    resolved = values if values is not None else default_extraction_authority_values()
    compiled = render_invoice_extraction_prompt(values=resolved, fields=fields)
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
        client: Injected :class:`~llm.LLMClient` (dependency
            injection for tests); default-constructed against the resolved
            settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
        authority_values: The regulatory values the compiled prompt enumerates,
            resolved by
            :func:`~application.ledger.invoice_extraction_authority.resolve_invoice_extraction_authority_values`.
            Taken as resolved DATA rather than as a period this reader would
            look up for itself: the rates are the application layer's to
            determine, and a reader that resolves its own has quietly become a
            second consumer of the calculation authorities. ``None`` falls back
            to the current civil year's values.
        consent_token: Per-invocation off-host consent proof, minted through
            :func:`~llm._consent.mint_evidence_consent_token`. Required only for
            an off-host read of real evidence; ``None`` is correct for every
            on-host read.
        public_corpus: Whether the text handed to this reader comes from the
            public, synthetic measurement corpus rather than from a taxpayer's
            document. Defaults to ``False`` -- the fail-closed direction, so a
            caller that says nothing gets the gate. Naming the corpus is the
            deliberate act, not naming the evidence.
        fields: The field names each read asks for, or ``None`` for every
            declared field. Held for the reader's lifetime rather than passed
            per read, because it describes the SHAPE of the call this reader
            makes, and a shape that varied between two reads of one corpus would
            make those reads incomparable. A measurement comparing call shapes
            builds one reader per shape.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: LLMProvider = LLMProvider.LOCAL,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        authority_values: InvoiceExtractionAuthorityValues | None = None,
        consent_token: EvidenceConsentToken | None = None,
        public_corpus: bool = False,
        fields: Collection[str] | None = None,
    ) -> None:
        # Ahead of every other statement, so the refusal is what an operator
        # without the extra sees rather than a settings or model-resolution
        # error raised on the way to it.
        require_optional_extra(LLM_EXTRA)
        resolved_settings = settings if settings is not None else load_settings()
        self._provider = provider
        self._consent_token = consent_token
        self._public_corpus = public_corpus
        self._fields = fields
        if provider is LLMProvider.LOCAL:
            self._model = model if model is not None else resolved_settings.cadrumo_llm_ollama_text_model
        elif model is None:
            # Mirrors the vision reader's guard, and closes the same hole from
            # the other side. The only default that exists is the local text
            # model, so forwarding that identifier to a vendor asks for a model
            # it does not serve -- and doing so SILENTLY is what let a
            # taxpayer's document reach a cloud provider by configuration alone.
            raise LLMConfigError(
                context={"provider": provider.value, "off_host_model_named": False},
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.OFF_HOST_MODEL_NAMED,
                    facts={"provider": provider.value, "off_host_model_named": False},
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                ),
            )
        else:
            self._model = model
        self._authority_values = (
            authority_values if authority_values is not None else default_extraction_authority_values()
        )
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
        return build_provenance_stamp(
            provider=self._provider,
            reader="text-extract",
            model=self._model or "configured",
            qualifier=f"rates-{self._compiled_prompt().rate_provenance}",
        )

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

        The default is now :attr:`~llm.LLMProvider.LOCAL` and
        it is stated here rather than inherited, because the confidentiality
        guarantee is that sensitive financial data stays on the host. Running
        this reader against a hosted model remains possible, but only by naming
        both the provider and the model, which makes the off-host read a
        deliberate act at the call site instead of a property of the
        environment.
        """
        return LLMRequest(
            prompt=build_text_field_extraction_prompt(
                evidence_text,
                values=self._authority_values,
                fields=self._fields,
            ),
            provider_override=self._provider,
            model_override=self._model,
            evidence_derived=not self._public_corpus,
            consent_token=self._consent_token,
        )

    def _compiled_prompt(self) -> CompiledInvoiceExtractionPrompt:
        """Return the compiled instruction half this reader sends.

        Built without any document text, so the stamp can name the rates a read
        was performed under without a document in hand.

        Carries this reader's own field selection. The stamp's whole purpose is
        to identify the instruction a read was performed under, and a stamp that
        described the full prompt while the read asked for three fields would
        name an instruction that was never sent -- which is worse than no stamp,
        because it is a confident wrong answer to the one question the stamp
        exists to answer.
        """
        return render_invoice_extraction_prompt(values=self._authority_values, fields=self._fields)


def extract_invoice_fields_from_text(
    transcription: DocumentTranscription,
    *,
    model: str | None = None,
    settings: Settings | None = None,
    authority_values: InvoiceExtractionAuthorityValues | None = None,
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
    :class:`LLMClient`'s per-invocation evidence-consent check refuses a
    marked request at any off-host provider without a per-invocation consent
    token. That is the property to preserve if this signature ever changes: the
    refusal lives below this function, not in it.

    Args:
        transcription: The acquisition-stage transcription to read.
        model: Optional model override.
        settings: Optional resolved settings override.
        authority_values: Application-resolved regulatory values for the prompt.
            The routing caller resolves these ONCE per document and passes them
            here, so a document read through several stages is read under one
            set of rates rather than one per prompt construction.

    Returns:
        :class:`InvoiceDraft`: The grounded, best-effort extracted fields.
    """
    extractor = TextInvoiceFieldExtractor(
        model=model,
        settings=settings,
        provider=LLMProvider.LOCAL,
        authority_values=authority_values,
    )
    return extractor.extract(transcription=transcription)
