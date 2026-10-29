"""TEXT evidence reader: classify/split from an extracted text layer.

A document's text layer and a scanned document's pixels reach the model by the
same route: through the agent service, on the lane and model it derives for
the role. Whether the read leaves this computer is that lane's catalogue
flag, never the shape of the document, and a lane that reads
off the host needs the per-invocation consent this reader's caller supplies.

It is deliberately a sibling of :class:`~llm.vision_classifier.VisionLLMClassifier` rather than a
generalisation of it. The two differ only in transport -- text in the prompt
versus images on the message -- and they share the prompt spec and the
allow-list-guarded response parsing, which are the contracts that keep a model
selecting only ``classification`` / ``category`` / ``iva_category`` and never
emitting a regulated number. Merging them would fuse two payload shapes behind
one branch for no gain.
"""

from __future__ import annotations

import asyncio

from ....core.config import Settings, load_settings
from ....core.config_support import LLMProvider
from ....core.model_roles import ModelRole
from ....core.provenance_stamp import build_provenance_stamp
from ....domain.transactions.llm import (
    LLMClassificationResponse,
    LLMSplitResponse,
    PromptSpec,
    build_split_prompt,
    parse_response,
    parse_split_response,
)
from ....domain.transactions.models import Transaction
from .client import LLMClient
from .consent import EvidenceConsentToken
from .models import LLMRequest

__all__ = ["TextLLMClassifier"]


class TextLLMClassifier:
    """Classify or split a transaction from extracted evidence text through the agent.

    Args:
        spec: Prompt spec carrying the registry-grounded category and
            IVA-category allow-lists -- the same spec every other classifier
            uses, so the model's answer space is identical whichever transport
            reads the document.
        client: Injected :class:`LLMClient` for tests; default-constructed
            against the resolved settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
        consent_token: Per-invocation off-host consent proof. ``None`` reads
            only on a lane that stays on this computer; a lane that reads off
            the host refuses the request without one.
    """

    def __init__(
        self,
        *,
        spec: PromptSpec,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        consent_token: EvidenceConsentToken | None = None,
    ) -> None:
        """Build the classifier around one prompt spec."""
        resolved_settings = settings if settings is not None else load_settings()
        self._spec = spec
        self._consent_token = consent_token
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
                caller="cadrumo.adapters.outbound.llm.text",
                prompt_id="ledger-text-classify",
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp recorded as ``classified_by``.

        Distinct from the vision stamp, so a persisted record always says which
        reader produced it. The model segment is ``configured`` because the
        agent resolves the model for the role at dispatch.
        """
        return build_provenance_stamp(provider=LLMProvider.AGENT, reader="text", model="configured")

    def classify(self, transaction: Transaction, *, evidence_text: str | None) -> LLMClassificationResponse:
        """Classify ``transaction``, reading any extracted evidence text.

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
        """Build a text extraction request for the agent; no images, always marked as evidence."""
        return LLMRequest(
            prompt=prompt,
            provider_override=LLMProvider.AGENT,
            evidence_derived=True,
            consent_token=self._consent_token,
            model_role=ModelRole.TEXT_EXTRACTION,
            expects_json=True,
        )
