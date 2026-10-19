"""The transport boundary refuses a vision request an adapter cannot carry.

``ProviderRequest.images`` is populated for every provider, but only an adapter
declaring ``supports_images`` puts them on the wire. Before this boundary
existed, routing a vision read at a cloud provider dropped the images silently
and sent a text-only prompt: the model was asked to read an invoice it had never
been shown, and answered confidently from nothing. No exception, no warning, a
plausible fabricated figure.

These tests hold that shut. The refusal crosses the real :class:`LLMClient`
and the real agent adapter; only the agent service behind the model-run port
is a recording stand-in, so what reached the lane is observed, not assumed.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Mapping
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pydantic import ValidationError

from cadrumo_client.contracts.model_runs import ModelRunRefusalCode

from .....core.config_support import LLMProvider
from .....core.image_media_type import ImageMediaType
from .....core.model_catalogue import ModelRole
from .....tests.fixtures.settings import EnvFileFreeSettings
from ..client import LLMClient
from ..errors import LLMConfigError
from ..models import LLMRequest, MultimodalImageInput
from ..providers.agent import AgentAdapter
from ..providers.local import LocalAdapter
from .model_run_support import IMAGE_LANE, TEXT_ONLY_LANE, serving_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_PROMPT = "Read the attached invoice and report the total."


def _png_image() -> MultimodalImageInput:
    """Encode a small real PNG as one multimodal input."""
    buffer = BytesIO()
    Image.new("RGB", (12, 12), "white").save(buffer, format="PNG")
    return MultimodalImageInput.from_base64(
        base64.b64encode(buffer.getvalue()).decode("ascii"),
        ImageMediaType.PNG,
    )


def _settings(tmp_path: Path) -> EnvFileFreeSettings:
    """Settings whose LLM stores stay inside ``tmp_path``."""
    return EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_record_dir=tmp_path / "run-record",
    )


def _client(settings: EnvFileFreeSettings) -> LLMClient:
    """Build a real client, letting it construct its own core-side stores."""
    return LLMClient(settings=settings)


def _vision_request() -> LLMRequest:
    return LLMRequest(
        prompt=_PROMPT,
        provider_override=LLMProvider.AGENT,
        model_role=ModelRole.VISION_TRANSCRIPTION,
        images=(_png_image(),),
    )


def _refusal_facts(error: LLMConfigError) -> Mapping[str, object]:
    verdict = error.terminal_precondition_verdict
    assert verdict is not None
    assert verdict.failed_condition_id == "llm.agent.model_run_completed"
    return verdict.evidence[0].values


class TestALaneThatTakesNoImagesRefusesThem:
    """The safety-critical case: images must never be dropped in silence."""

    def test_images_for_a_lane_whose_catalog_takes_none_refuse_before_any_run(self, tmp_path: Path) -> None:
        """The lane's catalog entry says it takes no images, so nothing is sent.

        The empty run list is the load-bearing assertion: the refusal has to fire
        before dispatch, or the lane would be asked to read a page it never got.
        """
        with serving_agent(lane=TEXT_ONLY_LANE) as service, pytest.raises(LLMConfigError) as caught:
            asyncio.run(_client(_settings(tmp_path)).complete(_vision_request()))

        assert _refusal_facts(caught.value) == {
            "model_run_refusal": "input_not_supported",
            "model_role": ModelRole.VISION_TRANSCRIPTION.value,
        }
        assert service.runs == []

    def test_the_agents_own_admission_refusal_reaches_the_consumer_as_the_same_code(self, tmp_path: Path) -> None:
        """A lane whose catalog says nothing is asked; the agent decides at admission."""
        with (
            serving_agent(run_refusal=ModelRunRefusalCode.INPUT_NOT_SUPPORTED) as service,
            pytest.raises(LLMConfigError) as caught,
        ):
            asyncio.run(_client(_settings(tmp_path)).complete(_vision_request()))

        assert _refusal_facts(caught.value)["model_run_refusal"] == "input_not_supported"
        assert len(service.runs) == 1

    def test_a_text_only_request_at_a_text_only_lane_still_succeeds(self, tmp_path: Path) -> None:
        """The guard is scoped to image-bearing requests and regresses nothing."""
        request = LLMRequest(prompt=_PROMPT, provider_override=LLMProvider.AGENT, model_role=ModelRole.TEXT_EXTRACTION)
        with serving_agent(lane=TEXT_ONLY_LANE, replies=("text-only completion",)) as service:
            response = asyncio.run(_client(_settings(tmp_path)).complete(request))

        assert response.text == "text-only completion"
        assert response.provider is LLMProvider.AGENT
        ((_, body),) = service.runs
        assert body.prompt == _PROMPT
        assert body.attachments == ()


class TestDeclaredImageCapability:
    """Capability is data on the adapter class, not per-adapter memory."""

    def test_both_adapters_forward_images(self) -> None:
        """The local adapter sends images itself; the agent adapter hands them to the lane.

        Whether a given lane accepts them is the catalog's answer, checked at the
        client's dispatch point, so the agent adapter declares that it carries them.
        """
        assert LocalAdapter.supports_images is True
        assert AgentAdapter.supports_images is True


class TestAgentMultimodalPayload:
    """The agent adapter puts each image on the run as one attachment, in order."""

    def test_each_image_is_an_attachment_carrying_its_declared_media_type(self, tmp_path: Path) -> None:
        first = _png_image()
        second = MultimodalImageInput.from_base64(first.base64_data, ImageMediaType.JPEG)
        request = _vision_request().model_copy(update={"images": (first, second)})
        with serving_agent(lane=IMAGE_LANE) as service:
            asyncio.run(_client(_settings(tmp_path)).complete(request))

        ((_, body),) = service.runs
        assert [attachment.media_type for attachment in body.attachments] == ["image/png", "image/jpeg"]
        assert [attachment.base64_data for attachment in body.attachments] == [first.base64_data] * 2
        assert body.prompt == _PROMPT


class TestMultimodalImageInputDeclaresItsMediaType:
    """A defaulted media type is how a JPEG gets sent as a PNG."""

    def test_construction_without_a_media_type_refuses(self) -> None:
        """The field is required: there is no format to fall back to."""
        # Built as a mapping so the omission is a RUNTIME fact the validator must
        # catch, not a static-typing artefact a checker would reject first.
        without_media_type = {"content_sha256": "a" * 64, "base64_data": "QQ=="}
        with pytest.raises(ValidationError) as caught:
            MultimodalImageInput.model_validate(without_media_type)
        assert "media_type" in str(caught.value)

    def test_an_unrecognised_media_type_refuses(self) -> None:
        """The axis is a closed enum, so a free-form string cannot slip through."""
        bmp_declared = {"content_sha256": "a" * 64, "base64_data": "QQ==", "media_type": "image/bmp"}
        with pytest.raises(ValidationError):
            MultimodalImageInput.model_validate(bmp_declared)

    def test_the_content_address_is_the_digest_of_the_decoded_bytes(self) -> None:
        """The constructor derives the address, so payload and digest cannot diverge."""
        from .....core.hashing import sha256_hex

        buffer = BytesIO()
        Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
        raw = buffer.getvalue()
        built = MultimodalImageInput.from_base64(base64.b64encode(raw).decode("ascii"), ImageMediaType.PNG)
        assert built.content_sha256 == sha256_hex(raw)
