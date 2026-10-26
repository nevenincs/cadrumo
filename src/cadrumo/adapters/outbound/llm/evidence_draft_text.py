"""Semantic invoice-field extraction from a document's TEXT representation.

Reading a rendered document is two questions, not one. The vision reader once
answered them together, handing rasterised pages to a model and taking back
typed fields in a single call -- so when the result was wrong there was no way
to tell a transcription error from a reasoning error, and a perfect
transcription obtained by any other means had nowhere to go.

This module is the second stage that made splitting them possible: text in,
grounded :class:`~application.ledger.invoice_draft_records.InvoiceDraft` out. Both acquisition lanes
now feed it -- the deterministic text-layer extractor and
:class:`~llm.evidence_draft_vision.VisionDocumentTranscriber`, which transcribes and interprets
nothing. Splitting it out means the
transcription stage can be swapped, measured or replaced independently of the
understanding stage, and it makes any already-transcribed text -- a PDF text
layer, an OCR result, an EN16931 payload rendered back to prose -- usable.

**One dispatch path.** Every read names the text extraction role and goes to the
agent service, which runs it on the lane and model the person selected for that
role. Whether the read leaves this computer is that lane's catalogue flag. The
reader marks every request it builds as evidence-derived unless the caller
names the public corpus, and :class:`LLMClient`'s per-invocation
evidence-consent check refuses a marked request on a lane that reads off the
host without a consent token. A public-corpus read carries no consent, so the
agent service refuses it on such a lane.

**Language-neutral by design.** The vision prompt opens "a scanned Spanish
invoice"; invoices reaching this path are international, in arbitrary languages
and layouts, so the prompt names field *concepts* and lets the model find them
under whatever heading the document uses. What it does not relax is the safety
contract: copy printed values verbatim, never calculate or infer, and emit
``null`` for anything not printed. Grounded re-validation
(:func:`~llm.invoice_field_grounding.ground_extracted_fields`) then re-checks
every field against an independent authority, so a fabricated value is dropped
even if the prompt fails to prevent it.

See Also:
    :class:`~application.ledger.invoice_draft_records.InvoiceDraft`
        Typed draft this reader returns after grounded re-validation.
    :func:`~llm.invoice_field_grounding.ground_extracted_fields`
        Shared grounded re-validation this reader and the vision reader both use.
    :class:`~llm.evidence_draft_vision.VisionDocumentTranscriber`
        Sibling ACQUISITION stage for evidence carrying no text layer at all.
        It produces the transcription this reader consumes; it does not read
        fields.
"""

from __future__ import annotations

import asyncio
from collections.abc import Collection
from typing import TYPE_CHECKING

from ....application.ledger.document_transcription import DocumentTranscription
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ....application.ledger.invoice_draft_records import InvoiceDraft
from ....application.ledger.invoice_extraction_authority import (
    InvoiceExtractionAuthorityValues,
    resolve_invoice_extraction_authority_values,
)
from ....core.config import Settings, load_settings
from ....core.config_support import LLMProvider
from ....core.model_roles import ModelRole
from ....core.operator_action_enums import ActionEvidenceProvenance
from ....core.optional_extras import LLM_EXTRA, require_optional_extra
from ....core.provenance_stamp import build_provenance_stamp
from .client import LLMClient
from .consent import EvidenceConsentToken
from .invoice_extraction_prompt import (
    CompiledInvoiceExtractionPrompt,
    default_extraction_period,
    render_invoice_extraction_prompt,
)
from .invoice_field_grounding import ground_extracted_fields, parse_invoice_extraction_response
from .models import LLMRequest
from .preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

if TYPE_CHECKING:
    from ....domain.calculations.registry.authority import PinnedAuthorityOperation

__all__ = [
    "TextInvoiceFieldExtractor",
    "build_text_field_extraction_prompt",
    "default_extraction_authority_values",
    "extract_invoice_fields_from_text",
]


def default_extraction_authority_values(*, operation: PinnedAuthorityOperation) -> InvoiceExtractionAuthorityValues:
    """Resolve the authority values for the fallback period.

    The one place this package turns "no values were supplied" into values, and
    it does so by asking the application layer's compiler rather than by reading
    any authority itself.

    Returns:
        :class:`~application.ledger.invoice_extraction_authority.InvoiceExtractionAuthorityValues`: The values
        in force across the current civil year.
    """
    return resolve_invoice_extraction_authority_values(period=default_extraction_period(), operation=operation)


def build_text_field_extraction_prompt(
    evidence_text: str,
    *,
    operation: PinnedAuthorityOperation,
    values: InvoiceExtractionAuthorityValues | None = None,
    fields: Collection[str] | None = None,
) -> str:
    """Build the extraction prompt for ``evidence_text``.

    Separate from the transport so the exact instruction a model will receive is
    directly assertable without dispatching a request.

    The instruction half is the SHARED rendered artefact
    (:func:`~llm.invoice_extraction_prompt.render_invoice_extraction_prompt`),
    not a second hand-maintained field list: this reader and the vision reader
    ask for the same eight fields in the same declared forms, and maintaining
    that agreement by hand is exactly the drift that lost a correctly-read rate.

    Args:
        evidence_text: The document's text representation.
        operation: The caller-owned generation-pinned authority operation used
            when resolving fallback authority values.
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
    resolved = values if values is not None else default_extraction_authority_values(operation=operation)
    compiled = render_invoice_extraction_prompt(values=resolved, fields=fields)
    return f"{compiled.text}\nINVOICE TEXT:\n{evidence_text}"


class TextInvoiceFieldExtractor:
    """Read an invoice's text with a language model into a grounded :class:`InvoiceDraft`.

    Args:
        client: Injected :class:`~llm.LLMClient` (dependency
            injection for tests); default-constructed against the resolved
            settings otherwise.
        operation: Caller-owned generation-pinned authority operation retained
            for authority resolution and field grounding.
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
            :func:`~llm.consent.mint_evidence_consent_token`. Required for a
            read of real evidence on a lane that reads off the host; ``None``
            reads only on a lane that stays on this computer.
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
        client: LLMClient | None = None,
        operation: PinnedAuthorityOperation,
        settings: Settings | None = None,
        authority_values: InvoiceExtractionAuthorityValues | None = None,
        consent_token: EvidenceConsentToken | None = None,
        public_corpus: bool = False,
        fields: Collection[str] | None = None,
    ) -> None:
        """Build the text reader for one evidence shape."""
        # Ahead of every other statement, so the refusal is what an operator
        # without the extra sees rather than a settings or model-resolution
        # error raised on the way to it.
        require_optional_extra(LLM_EXTRA)
        resolved_settings = settings if settings is not None else load_settings()
        self._operation = operation
        self._consent_token = consent_token
        self._public_corpus = public_corpus
        self._fields = fields
        self._authority_values = (
            authority_values
            if authority_values is not None
            else default_extraction_authority_values(operation=operation)
        )
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=resolved_settings,
                caller="cadrumo.adapters.outbound.llm.evidence_draft_text",
                prompt_id="ledger-invoice-text-extract",
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp: transport, reader, model, and the rates compiled in.

        Distinct from the vision stamp so a persisted record always says which
        reader produced the fields. The model segment is ``configured``,
        because the agent resolves the model for the role at dispatch rather
        than this object holding it.

        The trailing rate-provenance token answers the question the model name
        cannot: the prompt now enumerates registry-resolved rates, so which
        rates were in force for this read is part of how the figure was reached.

        """
        return build_provenance_stamp(
            provider=LLMProvider.AGENT,
            reader="text-extract",
            model="configured",
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
            operation=self._operation,
        )

    def _build_request(self, evidence_text: str) -> LLMRequest:
        """Build the text extraction request the agent runs for ``evidence_text``."""
        return LLMRequest(
            prompt=build_text_field_extraction_prompt(
                evidence_text,
                operation=self._operation,
                values=self._authority_values,
                fields=self._fields,
            ),
            provider_override=LLMProvider.AGENT,
            evidence_derived=not self._public_corpus,
            consent_token=self._consent_token,
            model_role=ModelRole.TEXT_EXTRACTION,
            expects_json=True,
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
    operation: PinnedAuthorityOperation,
    settings: Settings | None = None,
    authority_values: InvoiceExtractionAuthorityValues | None = None,
) -> InvoiceDraft:
    """Convenience wrapper: build a :class:`TextInvoiceFieldExtractor` and extract.

    The read carries no consent token, so it runs only on a text extraction
    lane that stays on this computer; on a lane that reads off the host the
    client's evidence-consent check refuses it before anything is sent.

    Args:
        transcription: The acquisition-stage transcription to read.
        operation: The caller-owned generation-pinned authority operation used
            for authority resolution and field grounding.
        settings: Optional resolved settings override.
        authority_values: Application-resolved regulatory values for the prompt.
            The routing caller resolves these ONCE per document and passes them
            here, so a document read through several stages is read under one
            set of rates rather than one per prompt construction.

    Returns:
        :class:`InvoiceDraft`: The grounded, best-effort extracted fields.
    """
    extractor = TextInvoiceFieldExtractor(
        settings=settings,
        operation=operation,
        authority_values=authority_values,
    )
    return extractor.extract(transcription=transcription)
