"""On-host VISION TRANSCRIPTION of a scan-only PDF or image: stage one, and only stage one.

This module reads pixels into text. It does not read pixels into fields, and the
difference is the whole reason it was refitted.

**What it used to do, and why that could not stand.** One call handed rasterised
pages to a vision model and took back typed invoice fields with their anchors.
Two questions were answered together -- *what does this page say* and *what does
that mean* -- so a wrong result could not be attributed to either: a
transcription error and a reasoning error arrived in the same shape. Worse, the
anchors came back from the same call that produced the values, so there was
nothing independent to check them against. The provenance record had to say so
(:attr:`~application.ledger.evidence_draft.FieldProvenance.anchor_self_reported`), and a
self-reported anchor can never read as verified, because a fabricating model is
self-consistent too. The vision lane was therefore structurally incapable of
earning the grounding the text lane earned for free.

**What it does now.** It emits a
:class:`~application.ledger.document_transcription.DocumentTranscription` -- reading-order text with
printed forms preserved verbatim -- and stops. The semantic stage
(:func:`~llm.extract_invoice_fields_from_text`) then reads that text in a
SEPARATE call, and the anchor check runs against the transcription this module
produced. Two readers, two calls, one external check: exactly the shape the text
lane already had, now reachable for a document that has no text layer at all.

**Faithfulness is the only job, and an explicit unknown is a legitimate result.**
A vision model reading a creased receipt genuinely cannot always resolve a glyph.
The prompt therefore asks it to transcribe what it can see and to mark what it
cannot, rather than to produce a clean-looking page by filling the gap. An
illegible character reported as illegible costs one field; an invented one that
happens to parse costs a filing, silently, because a plausible figure passes
every downstream check that is not the anchor check -- and it would pass that
one too, since the fabrication would be in the transcription the check runs
against.

**On-host by default, and the default is stated rather than inherited.** The
shipped provider default is a cloud vendor, so a reader that took whatever the
environment resolved would send a taxpayer's document off-host by configuration
alone. Naming another provider requires naming its model too, which makes an
off-host read a deliberate act at the call site. That is a floor, not the gate:
the gate is the client's per-invocation evidence-consent check, and every
request built here is marked evidence-derived unless the caller names the
public, synthetic measurement corpus.

See Also:
    :class:`~application.ledger.document_transcription.DocumentTranscription`
        The typed stage-one artefact this module produces.
    :func:`~application.ledger.evidence_textlayer.transcribe_text_layer`
        The deterministic sibling for a document that HAS a text layer.
    :func:`~llm.extract_invoice_fields_from_text`
        The stage-two semantic reader that consumes what this produces.
"""

from __future__ import annotations

import asyncio
from typing import Final

from ..application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ..application.ledger.evidence import PurchaseInvoiceEvidenceInputError
from ..core import LLM_EXTRA, ActionEvidenceProvenance, FieldOrigin, provenance_transport_label, require_optional_extra
from ..core.config import Settings, load_settings
from .client import LLMClient
from .consent import EvidenceConsentToken
from .errors import LLMConfigError
from .models import LLMProvider, LLMRequest, MultimodalImageInput, PromptDefinition, PromptRegistry
from .preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

__all__ = [
    "VISION_TRANSCRIPTION_PROMPT",
    "VISION_TRANSCRIPTION_PROMPT_ID",
    "VISION_TRANSCRIPTION_PROMPT_VERSION",
    "LocalVisionDocumentTranscriber",
    "transcribe_document_images",
    "vision_transcription_prompt_registry",
]

VISION_TRANSCRIPTION_PROMPT_ID: Final[str] = "ledger-document-vision-transcription"
"""Registry id of the transcription-only vision prompt."""

VISION_TRANSCRIPTION_PROMPT_VERSION: Final[int] = 1
"""Version of the transcription prompt.

Part of the transcriber's recorded revision, so a prompt change re-keys the
transcription cache. Two prompts produce two different readings of the same
pixels, and a cache that could not tell them apart would serve one document's
text for another document's question.
"""

VISION_TRANSCRIPTION_PROMPT: Final[str] = """\
Transcribe this document. Write out the text you can see, in reading order.

Rules:
- Copy every character EXACTLY as printed. Keep the document's own spelling, \
capitalisation, punctuation, spacing, separators and symbols.
- Keep numbers exactly as written. Do not convert, round, reformat or normalise \
any figure, date or amount.
- Keep every heading and label. They are part of the document.
- Transcribe in reading order, one line per printed line.
- Where you cannot read a character or a word, write [?] in its place. Never \
guess what it might have been and never leave it out silently.
- Do not summarise, explain, translate, correct or comment. Return the \
document's text and nothing else.
"""
"""The transcription instruction: read the page, do not interpret it.

Every rule here exists to protect a downstream check. Printed forms survive
verbatim because the anchor check searches this text for the form a value claims
to have been read from, so normalising a separator here deletes the evidence
that check runs against. Headings and labels survive because they are what
assigns an identifier to a party, and an identity with no role evidence does not
resolve. The illegible marker exists because an invented character is
indistinguishable from a read one once it is in the transcription -- it would
anchor perfectly against itself.

The prompt names no invoice field, and that absence is load-bearing rather than
incidental: a model told what to look for finds it, and this stage must not
decide what the document is before the stage that decides has run.
"""


def vision_transcription_prompt_registry() -> PromptRegistry:
    """Return the registry holding the transcription prompt.

    Registered rather than reachable only as a module constant, so the id and
    version travel with the artefact the way the extraction template's do.

    Returns:
        :class:`~llm.PromptRegistry`: A registry carrying the
        transcription prompt at :data:`VISION_TRANSCRIPTION_PROMPT_VERSION`.
    """
    registry = PromptRegistry()
    registry.register(
        PromptDefinition(
            id=VISION_TRANSCRIPTION_PROMPT_ID,
            version=VISION_TRANSCRIPTION_PROMPT_VERSION,
            template=VISION_TRANSCRIPTION_PROMPT,
            expected_output_schema=None,
            description="Transcribe a rendered document page into reading-order text, interpreting nothing.",
        ),
    )
    return registry


class LocalVisionDocumentTranscriber:
    """Transcribe rendered document pages on-host with a local vision model.

    Stage one of the reading pipeline for evidence that carries no text layer.
    It produces text and nothing else; every judgement about what that text
    MEANS belongs to the semantic stage, which runs separately over what this
    returns.

    Args:
        model: Vision model identifier; ``None`` uses the configured LOCAL
            vision model. Required when ``provider`` is not LOCAL, because the
            only default that exists names a local model no vendor serves.
        provider: Which provider carries the read. Defaults to LOCAL so a
            taxpayer's document does not leave the host by default.
        client: Injected :class:`~llm.LLMClient` (dependency
            injection for tests); default-constructed against the resolved
            settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
        consent_token: Per-invocation off-host consent proof, minted through
            :func:`~llm.consent.mint_evidence_consent_token`. Required only for
            an off-host read of real evidence; ``None`` is correct for every
            on-host read.
        public_corpus: Whether the pages handed to this reader come from the
            public, synthetic measurement corpus rather than from a taxpayer's
            document. Defaults to ``False`` -- the fail-closed direction, so a
            caller that says nothing gets the gate.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        provider: LLMProvider = LLMProvider.LOCAL,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        consent_token: EvidenceConsentToken | None = None,
        public_corpus: bool = False,
    ) -> None:
        """Build the vision reader, subject to the on-host consent gate."""
        # Ahead of every other statement, so the refusal is what an operator
        # without the extra sees rather than a settings or model-resolution
        # error raised on the way to it.
        require_optional_extra(LLM_EXTRA)
        resolved_settings = settings if settings is not None else load_settings()
        self._provider = provider
        self._consent_token = consent_token
        self._public_corpus = public_corpus
        self._prompt = vision_transcription_prompt_registry().get(VISION_TRANSCRIPTION_PROMPT_ID)
        if provider is LLMProvider.LOCAL:
            self._model = model if model is not None else resolved_settings.cadrumo_llm_ollama_vision_model
        elif model is None:
            # The only default that exists is the local Ollama vision model, and
            # forwarding that identifier to another vendor asks for a model it
            # does not serve. Refuse rather than send a name that cannot resolve.
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
                caller="cadrumo.llm.evidence_vision_transcription",
                prompt_id=VISION_TRANSCRIPTION_PROMPT_ID,
            )
        )

    @property
    def transcriber_identity(self) -> TranscriberIdentity:
        """Return the provenance stamp for this reader.

        The revision folds the prompt version because the prompt is half of what
        produced the text: the same model under different instructions returns a
        different reading of the same pixels, and the transcription cache keys
        on this identity. A revision naming only the model would let one
        prompt's output be served for another prompt's question.

        The TRANSPORT is recorded for a different reason, and it is not
        tidiness. A transcription is a durable artefact derived from the
        document, so if it was produced off-host it is one of the artefacts a
        consent withdrawal must enumerate -- and a model identifier reveals the
        vendor only to a reader who already knows the catalogue. Recorded this
        way, the artefact that most needs re-deriving is not the one the survey
        cannot see.

        It rides its own field rather than the name, which is where it began.
        ``name`` is contracted to say which reader produced the text and
        explicitly not to carry a coarse label, so folding the transport
        through it broke that contract and made a third provenance grammar --
        one no parser knew, on top of the two the stamp constructor had just
        collapsed into one. The reason for recording it was right; only the
        place was wrong.
        """
        return TranscriberIdentity(
            origin=FieldOrigin.VISION,
            name=self._model,
            transport=provenance_transport_label(self._provider),
            revision=f"prompt-v{self._prompt.version}",
        )

    def transcribe(
        self,
        *,
        evidence_images: tuple[MultimodalImageInput, ...],
        source_content_sha256: str,
    ) -> DocumentTranscription:
        """Transcribe ``evidence_images`` into the acquisition-stage record.

        Args:
            evidence_images: In-memory page/image renders of the evidence, each
                carrying its declared media type (built by the caller from
                :func:`~llm.rasterise_pdf_pages_to_base64_png`
                for a scan-only PDF, or from the raw bytes of an image
                attachment).
            source_content_sha256: Content address of the SOURCE bytes. Supplied
                by the caller rather than computed here, because the address
                must identify the document -- the same document rasterised at a
                different resolution is one document, and hashing the renders
                would make it two.

        Returns:
            :class:`~application.ledger.document_transcription.DocumentTranscription`: The reading-order
            text with printed forms intact.

        Raises:
            PurchaseInvoiceEvidenceInputError: When no pages were supplied, or
                the model returned no text. An empty transcription is a failed
                read, never an empty success: passed on it would tell the
                semantic stage the document is blank, which is a fact about the
                reader being reported as a fact about the document.
        """
        if not evidence_images:
            raise PurchaseInvoiceEvidenceInputError(
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.EVIDENCE_IMAGES_PRESENT,
                    facts={"evidence_image_count": 0, "evidence_images_present": False},
                    provenance=ActionEvidenceProvenance.APPLICATION_STATE,
                ),
            )
        request = LLMRequest(
            prompt=self._prompt.template,
            provider_override=self._provider,
            model_override=self._model,
            images=evidence_images,
            evidence_derived=not self._public_corpus,
            consent_token=self._consent_token,
        )
        response = asyncio.run(self._client.complete(request))
        text = response.text.strip()
        if not text:
            raise PurchaseInvoiceEvidenceInputError(
                precondition_verdict=llm_no_recovery_verdict(
                    LLMPreconditionCondition.EVIDENCE_TRANSCRIPTION_NONEMPTY,
                    facts={"transcription_nonempty": False},
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                ),
            )
        return DocumentTranscription(
            text=text,
            page_count=len(evidence_images),
            source_content_sha256=source_content_sha256,
            transcriber=self.transcriber_identity,
        )


def transcribe_document_images(
    evidence_images: tuple[MultimodalImageInput, ...],
    *,
    source_content_sha256: str,
    model: str | None = None,
    provider: LLMProvider = LLMProvider.LOCAL,
    settings: Settings | None = None,
) -> DocumentTranscription:
    """Convenience wrapper: build a :class:`LocalVisionDocumentTranscriber` and transcribe.

    Args:
        evidence_images: In-memory page/image renders of the evidence.
        source_content_sha256: Content address of the source bytes.
        model: Optional vision model override.
        provider: Transport serving the read. Defaults to
            :attr:`~llm.LLMProvider.LOCAL`, so the production
            route stays on-host; naming another provider is the caller's
            explicit, per-invocation decision to read off-host.
        settings: Optional resolved settings override.

    Returns:
        :class:`~application.ledger.document_transcription.DocumentTranscription`: The transcription.
    """
    transcriber = LocalVisionDocumentTranscriber(model=model, provider=provider, settings=settings)
    return transcriber.transcribe(evidence_images=evidence_images, source_content_sha256=source_content_sha256)
