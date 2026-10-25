"""VISION TRANSCRIPTION of a scan-only PDF or image: stage one, and only stage one.

This module reads pixels into text. It does not read pixels into fields, and the
difference is the whole reason it was refitted.

**What it used to do, and why that could not stand.** One call handed rasterised
pages to a vision model and took back typed invoice fields with their anchors.
Two questions were answered together -- *what does this page say* and *what does
that mean* -- so a wrong result could not be attributed to either: a
transcription error and a reasoning error arrived in the same shape. Worse, the
anchors came back from the same call that produced the values, so there was
nothing independent to check them against. The provenance record had to say so
(:attr:`~application.ledger.invoice_draft_records.FieldProvenance.anchor_self_reported`), and a
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

**One dispatch path, and consent follows the lane.** Every read goes to the
agent service for the vision transcription role, and the person's selection
for that role decides the lane and model. Whether the lane reads off-host is the
catalogue entry's typed flag, never this module's guess. A lane that reads
off-host needs the per-invocation, digest-bound consent token, and every
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

from ....application.ledger.document_transcription import DocumentTranscription, TranscriberIdentity
from ....application.ledger.evidence_errors import PurchaseInvoiceEvidenceInputError
from ....core.config import Settings, load_settings
from ....core.config_support import LLMProvider
from ....core.field_origin import FieldOrigin
from ....core.model_catalogue import ModelRole
from ....core.operator_action_enums import ActionEvidenceProvenance
from ....core.optional_extras import LLM_EXTRA, require_optional_extra
from ....core.provenance_stamp import provenance_transport_label
from .client import LLMClient
from .consent import EvidenceConsentToken
from .models import LLMRequest, MultimodalImageInput, PromptDefinition, PromptRegistry
from .preconditions import LLMPreconditionCondition, llm_no_recovery_verdict

__all__ = [
    "VISION_TRANSCRIPTION_PROMPT",
    "VISION_TRANSCRIPTION_PROMPT_ID",
    "VISION_TRANSCRIPTION_PROMPT_VERSION",
    "VisionDocumentTranscriber",
    "vision_transcription_prompt_registry",
]

VISION_TRANSCRIPTION_PROMPT_ID: Final[str] = "ledger-document-vision-transcription"
"""Registry id of the transcription-only vision prompt."""

VISION_TRANSCRIPTION_PROMPT_VERSION: Final[int] = 1
"""Version of the transcription prompt.

Part of the transcriber's recorded revision because two prompts can produce
different readings of the same pixels.
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


class VisionDocumentTranscriber:
    """Transcribe rendered document pages with the model selected for vision transcription.

    Stage one of the reading pipeline for evidence that carries no text layer.
    It produces text and nothing else; every judgement about what that text
    MEANS belongs to the semantic stage, which runs separately over what this
    returns.

    Args:
        client: Injected :class:`~llm.LLMClient` (dependency
            injection for tests); default-constructed against the resolved
            settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
        consent_token: Per-invocation off-host consent proof, minted through
            :func:`~llm.consent.mint_evidence_consent_token`. Needed only when
            the selected lane reads off-host; ``None`` is correct for a lane
            that stays on this computer.
        public_corpus: Whether the pages handed to this reader come from the
            public, synthetic measurement corpus rather than from a taxpayer's
            document. Defaults to ``False`` -- the fail-closed direction, so a
            caller that says nothing gets the gate.
    """

    def __init__(
        self,
        *,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        consent_token: EvidenceConsentToken | None = None,
        public_corpus: bool = False,
    ) -> None:
        """Build the vision reader for the vision transcription role."""
        # Ahead of every other statement, so the refusal is what an operator
        # without the extra sees rather than a settings error raised on the way
        # to it.
        require_optional_extra(LLM_EXTRA)
        resolved_settings = settings if settings is not None else load_settings()
        self._consent_token = consent_token
        self._public_corpus = public_corpus
        self._prompt = vision_transcription_prompt_registry().get(VISION_TRANSCRIPTION_PROMPT_ID)
        # A vision read can take minutes; give it its own (longer) timeout,
        # mirroring VisionLLMClassifier.
        vision_settings = resolved_settings.model_copy(
            update={"cadrumo_llm_default_timeout_s": resolved_settings.cadrumo_llm_vision_read_timeout_s},
        )
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=vision_settings,
                caller="cadrumo.adapters.outbound.llm.evidence_vision_transcription",
                prompt_id=VISION_TRANSCRIPTION_PROMPT_ID,
            )
        )

    def transcriber_identity(self, model: str) -> TranscriberIdentity:
        """Return the provenance stamp for a read the agent served with ``model``.

        The revision folds the prompt version because the prompt is half of what
        produced the text: the same model under different instructions returns a
        different reading of the same pixels. A revision naming only the model
        would erase which instructions produced the recorded text.

        The TRANSPORT is recorded because a transcription is a durable artefact
        derived from the document: if a consent is withdrawn, the artefacts read
        through the agent must be enumerable. ``model`` is the lane-qualified
        label the agent reported for the run, so the name says which lane and
        model produced the text.
        """
        return TranscriberIdentity(
            origin=FieldOrigin.VISION,
            name=model,
            transport=provenance_transport_label(LLMProvider.AGENT),
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
                :func:`~llm.pdf_rasterisation.rasterise_pdf_pages_to_base64_png`
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
            provider_override=LLMProvider.AGENT,
            images=evidence_images,
            evidence_derived=not self._public_corpus,
            consent_token=self._consent_token,
            model_role=ModelRole.VISION_TRANSCRIPTION,
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
            transcriber=self.transcriber_identity(response.model),
        )
