"""On-host vision evidence reader: classify/split from an attached invoice image.

Reads scanned or image evidence with a LOCAL Ollama vision model entirely on the
host (``sensitive-financial-data-secure-storage-only``): the in-memory base64
images are sent over loopback HTTP to the local model; nothing is written to disk
and nothing leaves the machine. This is the ADR's default, gestor-allowed posture
for scanned/image evidence -- distinct from the consent-gated cloud subprocess
text path used for text-layer PDFs.

The prompt and the allow-list-guarded response parsing are the same domain
contracts the subprocess classifier uses (:func:`parse_response`,
:func:`parse_split_response`, :class:`PromptSpec`); only the transport -- a local
vision model fed in-memory images -- differs, so the model still selects only
``classification`` / ``category`` / ``iva_category`` and never emits a regulated
number.
"""

from __future__ import annotations

import asyncio
import base64

from ...adapters.outbound.llm import LLMClient, LLMProvider, LLMRequest, MultimodalImageInput
from ...core.config import Settings, load_settings
from ...core.hashing import sha256_hex
from ...domain.transactions import (
    LLMClassificationResponse,
    LLMSplitResponse,
    PromptSpec,
    Transaction,
    build_split_prompt,
    parse_response,
    parse_split_response,
)

__all__ = ["LocalVisionLLMClassifier"]


def _to_multimodal_images(images: tuple[str, ...]) -> tuple[MultimodalImageInput, ...]:
    """Pair each base64 image with its content address (sha256 of the raw bytes)."""
    resolved: list[MultimodalImageInput] = []
    for encoded in images:
        digest = sha256_hex(base64.b64decode(encoded))
        resolved.append(MultimodalImageInput(content_sha256=digest, base64_data=encoded))
    return tuple(resolved)


class LocalVisionLLMClassifier:
    """Classify or split a transaction from an attached invoice image, on-host.

    Args:
        spec: The prompt spec carrying the registry-grounded category / IVA-category
            allow-lists (the same spec the subprocess classifier uses).
        model: Local Ollama vision model identifier; defaults to
            ``Settings.aeat_llm_ollama_vision_model``.
        client: Injected :class:`LLMClient` (dependency injection for tests);
            default-constructed against the resolved settings otherwise.
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
        resolved_settings = settings if settings is not None else load_settings()
        self._spec = spec
        self._model = model if model is not None else resolved_settings.aeat_llm_ollama_vision_model
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=resolved_settings,
                caller="aeat.application.ledger.vision",
                prompt_id="ledger-vision-classify",
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp recorded as ``classified_by`` (distinct from cloud subprocess)."""
        return f"llm:local-vision:{self._model}"

    def classify(self, transaction: Transaction, *, evidence_images: tuple[str, ...]) -> LLMClassificationResponse:
        """Read the attached invoice image with the local vision model and classify.

        Args:
            transaction: The transaction to classify.
            evidence_images: In-memory base64 page/image renders of the evidence.

        Returns:
            A validated :class:`LLMClassificationResponse` (allow-list-guarded).
        """
        prompt = self._spec.render(transaction, evidence_image_present=True)
        response = asyncio.run(self._client.complete(self._request(prompt, evidence_images)))
        return parse_response(response.text, spec=self._spec)

    def propose_split(self, transaction: Transaction, *, evidence_images: tuple[str, ...]) -> LLMSplitResponse:
        """Read the attached invoice image with the local vision model and propose a split.

        Args:
            transaction: The transaction to split.
            evidence_images: In-memory base64 page/image renders of the evidence.

        Returns:
            A validated :class:`LLMSplitResponse` (allow-list-guarded).
        """
        prompt = build_split_prompt(transaction, spec=self._spec, evidence_image_present=True)
        response = asyncio.run(self._client.complete(self._request(prompt, evidence_images)))
        return parse_split_response(response.text, spec=self._spec)

    def _request(self, prompt: str, evidence_images: tuple[str, ...]) -> LLMRequest:
        """Build a LOCAL-provider multimodal request for ``prompt`` plus the images."""
        return LLMRequest(
            prompt=prompt,
            provider_override=LLMProvider.LOCAL,
            model_override=self._model,
            images=_to_multimodal_images(evidence_images),
        )
