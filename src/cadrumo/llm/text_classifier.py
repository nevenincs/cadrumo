"""On-host TEXT evidence reader: classify/split from an extracted text layer.

Closes the capability gap that made the privacy posture inverted. Until this
existed, a document's transport was decided by an accident of how it was
produced: a scan-only PDF was read on-host by a local vision model, while a
PDF that happened to carry a text layer -- the *more* machine-readable
document -- was the one whose contents left the machine to a cloud subprocess.
The same taxpayer invoice took a different route depending on whether someone
had scanned it or exported it.

This reader removes the fork's cause rather than its symptom. Text-layer
evidence now takes the same on-host path scanned evidence already took, over
loopback HTTP to a local model, so no document class routes off-host and the
gestor bar that applied to one arm of the fork and not the other disappears
with it.

It is deliberately a sibling of :class:`LocalVisionLLMClassifier` rather than a
generalisation of it. The two differ only in transport -- text in the prompt
versus images on the message -- and they share the prompt spec and the
allow-list-guarded response parsing, which are the contracts that keep a model
selecting only ``classification`` / ``category`` / ``iva_category`` and never
emitting a regulated number. Merging them would fuse two payload shapes behind
one branch for no gain.
"""

from __future__ import annotations

import asyncio

from ..core.provenance_stamp import build_provenance_stamp
from ..core.optional_extras import LLM_EXTRA, require_optional_extra
from ..core.config import Settings, load_settings
from ..domain.transactions.llm import LLMClassificationResponse, LLMSplitResponse, PromptSpec, build_split_prompt, parse_response, parse_split_response
from ..domain.transactions.models import Transaction
from .client import LLMClient
from .models import LLMProvider, LLMRequest

__all__ = ["LocalTextLLMClassifier"]


class LocalTextLLMClassifier:
    """Classify or split a transaction from extracted evidence text, on-host.

    Args:
        spec: Prompt spec carrying the registry-grounded category and
            IVA-category allow-lists -- the same spec every other classifier
            uses, so the model's answer space is identical whichever transport
            reads the document.
        model: Local Ollama text model identifier; defaults to
            ``Settings.cadrumo_llm_ollama_text_model``.
        client: Injected :class:`LLMClient` for tests; default-constructed
            against the resolved settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
    """

    def __init__(
        self,
        *,
        spec: PromptSpec,
        model: str | None = None,
        client: LLMClient | None = None,
        settings: Settings | None = None,
    ) -> None:
        """Build the classifier around one prompt spec."""
        # Ahead of every other statement, so the refusal is what an operator
        # without the extra sees rather than a settings or model-resolution
        # error raised on the way to it.
        require_optional_extra(LLM_EXTRA)
        resolved_settings = settings if settings is not None else load_settings()
        self._spec = spec
        self._model = model if model is not None else resolved_settings.cadrumo_llm_ollama_text_model
        # Text generation on consumer hardware is slower than a cloud call and
        # faster than a vision read; it borrows the vision read's longer budget
        # rather than the general LLM timeout, which is sized for a hosted API.
        text_settings = resolved_settings.model_copy(
            update={"cadrumo_llm_default_timeout_s": resolved_settings.cadrumo_llm_vision_read_timeout_s},
        )
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=text_settings,
                caller="cadrumo.llm.text",
                prompt_id="ledger-text-classify",
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp recorded as ``classified_by``.

        Distinct from both the vision stamp and the retired cloud stamps, so a
        persisted record always says which on-host transport read it.
        """
        return build_provenance_stamp(provider=LLMProvider.LOCAL, reader="text", model=self._model)

    def classify(self, transaction: Transaction, *, evidence_text: str | None) -> LLMClassificationResponse:
        """Classify ``transaction``, reading any extracted evidence text on-host.

        Args:
            transaction: The transaction to classify.
            evidence_text: Text extracted from the linked document, or ``None``
                when the transaction carries no readable evidence.

        Returns:
            A validated, allow-list-guarded :class:`LLMClassificationResponse`.
        """
        prompt = self._spec.render(transaction, evidence_text=evidence_text)
        response = asyncio.run(self._client.complete(self._request(prompt)))
        return parse_response(response.text, spec=self._spec)

    def propose_split(self, transaction: Transaction, *, evidence_text: str | None) -> LLMSplitResponse:
        """Propose a split for ``transaction`` from its extracted evidence text.

        Args:
            transaction: The transaction to split.
            evidence_text: Text extracted from the linked document, or ``None``.

        Returns:
            A validated, allow-list-guarded :class:`LLMSplitResponse`.
        """
        prompt = build_split_prompt(transaction, spec=self._spec, evidence_text=evidence_text)
        response = asyncio.run(self._client.complete(self._request(prompt)))
        return parse_split_response(response.text, spec=self._spec)

    def _request(self, prompt: str) -> LLMRequest:
        """Build a LOCAL-provider text request; no images, no off-host transport."""
        return LLMRequest(
            prompt=prompt,
            provider_override=LLMProvider.LOCAL,
            model_override=self._model,
            # Marked even though the pin above makes the dispatch gate
            # unreachable from here: the marker states what the content IS, and
            # a later change that relaxes the pin must not silently also relax
            # the confidentiality posture.
            evidence_derived=True,
        )
