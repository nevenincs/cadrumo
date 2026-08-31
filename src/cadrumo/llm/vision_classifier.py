"""On-host vision evidence reader: classify/split from an attached invoice image.

Reads scanned or image evidence with a LOCAL Ollama vision model entirely on the
host (``sensitive-financial-data-secure-storage-only``): the in-memory base64
images are sent over loopback HTTP to the local model; nothing is written to disk
and nothing leaves the machine. This is the default, gestor-allowed posture
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

from ..core.provenance_stamp import build_provenance_stamp
from ..core.optional_extras import LLM_EXTRA, require_optional_extra
from ..core.config import Settings, load_settings
from ..domain.transactions.llm import LLMClassificationResponse, LLMSplitResponse, PromptSpec, build_split_prompt, parse_response, parse_split_response
from ..domain.transactions.models import Transaction
from .client import LLMClient
from .models import LLMProvider, LLMRequest, MultimodalImageInput

__all__ = ["LocalVisionLLMClassifier"]


class LocalVisionLLMClassifier:
    """Classify or split a transaction from an attached invoice image, on-host.

    Args:
        spec: The prompt spec carrying the registry-grounded category / IVA-category
            allow-lists (the same spec the subprocess classifier uses).
        model: Local Ollama vision model identifier; defaults to
            ``Settings.cadrumo_llm_ollama_vision_model``.
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
        """Build the vision classifier around one prompt spec."""
        # Ahead of every other statement, so the refusal is what an operator
        # without the extra sees rather than a settings or model-resolution
        # error raised on the way to it.
        require_optional_extra(LLM_EXTRA)
        resolved_settings = settings if settings is not None else load_settings()
        self._spec = spec
        self._model = model if model is not None else resolved_settings.cadrumo_llm_ollama_vision_model
        # A local vision model on consumer hardware can take minutes; give the
        # vision read its own (longer) timeout without affecting cloud calls.
        vision_settings = resolved_settings.model_copy(
            update={"cadrumo_llm_default_timeout_s": resolved_settings.cadrumo_llm_vision_read_timeout_s},
        )
        self._client = (
            client
            if client is not None
            else LLMClient(
                settings=vision_settings,
                caller="cadrumo.application.ledger.vision",
                prompt_id="ledger-vision-classify",
            )
        )

    @property
    def decided_by(self) -> str:
        """Provenance stamp recorded as ``classified_by`` (distinct from cloud subprocess)."""
        return build_provenance_stamp(provider=LLMProvider.LOCAL, reader="vision", model=self._model)

    def classify(
        self,
        transaction: Transaction,
        *,
        evidence_images: tuple[MultimodalImageInput, ...],
    ) -> LLMClassificationResponse:
        """Read the attached invoice image with the local vision model and classify.

        Args:
            transaction: The transaction to classify.
            evidence_images: In-memory page/image renders of the evidence, each
                carrying its declared media type.

        Returns:
            A validated :class:`LLMClassificationResponse` (allow-list-guarded).
        """
        prompt = self._spec.render(transaction, evidence_image_present=True)
        response = asyncio.run(self._client.complete(self._request(prompt, evidence_images)))
        return parse_response(response.text, spec=self._spec)

    def propose_split(
        self,
        transaction: Transaction,
        *,
        evidence_images: tuple[MultimodalImageInput, ...],
    ) -> LLMSplitResponse:
        """Read the attached invoice image with the local vision model and propose a split.

        Args:
            transaction: The transaction to split.
            evidence_images: In-memory page/image renders of the evidence, each
                carrying its declared media type.

        Returns:
            A validated :class:`LLMSplitResponse` (allow-list-guarded).
        """
        prompt = build_split_prompt(transaction, spec=self._spec, evidence_image_present=True)
        response = asyncio.run(self._client.complete(self._request(prompt, evidence_images)))
        return parse_split_response(response.text, spec=self._spec)

    def _request(self, prompt: str, evidence_images: tuple[MultimodalImageInput, ...]) -> LLMRequest:
        """Build a LOCAL-provider multimodal request for ``prompt`` plus the images."""
        return LLMRequest(
            prompt=prompt,
            provider_override=LLMProvider.LOCAL,
            model_override=self._model,
            images=evidence_images,
            # Marked even though the pin above makes the dispatch gate
            # unreachable from here: the marker states what the content IS, and
            # a later change that relaxes the pin must not silently also relax
            # the confidentiality posture.
            evidence_derived=True,
        )
