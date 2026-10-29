"""Vision evidence reader: classify/split from an attached invoice image.

Reads scanned or image evidence with the model the agent service derives for
the vision transcription role. The in-memory base64
images travel as image attachments of one model run; nothing is written to
disk. Whether they leave this computer is the derived lane's typed
``reads_off_host`` flag: a lane that reads off-host is refused unless the
caller supplies the per-invocation, digest-bound consent token for the
evidence, and a lane that stays on this computer needs none.

The prompt and the allow-list-guarded response parsing are the same domain
contracts the text classifier uses (:func:`parse_response`,
:func:`parse_split_response`, :class:`PromptSpec`); only the input -- images
rather than a text layer -- differs, so the model still selects only
``classification`` / ``category`` / ``iva_category`` and never emits a regulated
number.
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
from .models import LLMRequest, MultimodalImageInput

__all__ = ["VisionLLMClassifier"]


class VisionLLMClassifier:
    """Classify or split a transaction from an attached invoice image.

    Args:
        spec: The prompt spec carrying the registry-grounded category / IVA-category
            allow-lists (the same spec the text classifier uses).
        client: Injected :class:`LLMClient` (dependency injection for tests);
            default-constructed against the resolved settings otherwise.
        settings: Injected settings; defaults to ``load_settings()``.
        consent_token: Per-invocation off-host consent proof for the evidence
            the images were rendered from. Needed only when the selected lane
            reads off-host; ``None`` is correct for a lane that stays on this
            computer.
    """

    def __init__(
        self,
        *,
        spec: PromptSpec,
        client: LLMClient | None = None,
        settings: Settings | None = None,
        consent_token: EvidenceConsentToken | None = None,
    ) -> None:
        """Build the vision classifier around one prompt spec."""
        resolved_settings = settings if settings is not None else load_settings()
        self._spec = spec
        self._consent_token = consent_token
        self._served_model: str | None = None
        # A vision read can take minutes; give it its own (longer) timeout
        # without affecting text calls.
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
        """Provenance stamp recorded as ``classified_by``.

        Names the lane and model the agent reported for the last read. Before
        any read has been served the model is not known, so the stamp says
        ``configured``: the service's derived model, unresolved here.
        """
        return build_provenance_stamp(
            provider=LLMProvider.AGENT,
            reader="vision",
            model=self._served_model or "configured",
        )

    def classify(
        self,
        transaction: Transaction,
        *,
        evidence_images: tuple[MultimodalImageInput, ...],
    ) -> LLMClassificationResponse:
        """Read the attached invoice image with the selected vision model and classify.

        Args:
            transaction: The transaction to classify.
            evidence_images: In-memory page/image renders of the evidence, each
                carrying its declared media type.

        Returns:
            A validated :class:`LLMClassificationResponse` (allow-list-guarded).
        """
        prompt = self._spec.render(transaction, evidence_image_present=True)
        return parse_response(self._complete(prompt, evidence_images), spec=self._spec)

    def propose_split(
        self,
        transaction: Transaction,
        *,
        evidence_images: tuple[MultimodalImageInput, ...],
    ) -> LLMSplitResponse:
        """Read the attached invoice image with the selected vision model and propose a split.

        Args:
            transaction: The transaction to split.
            evidence_images: In-memory page/image renders of the evidence, each
                carrying its declared media type.

        Returns:
            A validated :class:`LLMSplitResponse` (allow-list-guarded).
        """
        prompt = build_split_prompt(transaction, spec=self._spec, evidence_image_present=True)
        return parse_split_response(self._complete(prompt, evidence_images), spec=self._spec)

    def _complete(self, prompt: str, evidence_images: tuple[MultimodalImageInput, ...]) -> str:
        response = asyncio.run(self._client.complete(self._request(prompt, evidence_images)))
        self._served_model = response.model
        return response.text

    def _request(self, prompt: str, evidence_images: tuple[MultimodalImageInput, ...]) -> LLMRequest:
        """Build the vision-role agent request for ``prompt`` plus the images."""
        return LLMRequest(
            prompt=prompt,
            provider_override=LLMProvider.AGENT,
            images=evidence_images,
            evidence_derived=True,
            consent_token=self._consent_token,
            model_role=ModelRole.VISION_TRANSCRIPTION,
            expects_json=True,
        )
