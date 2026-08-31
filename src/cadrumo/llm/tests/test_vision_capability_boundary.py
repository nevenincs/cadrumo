"""The transport boundary refuses a vision request an adapter cannot carry.

``ProviderRequest.images`` is populated for every provider, but only an adapter
declaring ``supports_images`` puts them on the wire. Before this boundary
existed, routing a vision read at a cloud provider dropped the images silently
and sent a text-only prompt: the model was asked to read an invoice it had never
been shown, and answered confidently from nothing. No exception, no warning, a
plausible fabricated figure.

These tests hold that shut. Nothing here is mocked, stubbed, or patched: the
refusal crosses the real :class:`LLMClient` and a real adapter, the text-only
success crosses a real HTTP transport to a loopback endpoint, and the Anthropic
payload is the payload the adapter actually builds.
"""

from __future__ import annotations

import asyncio
import base64
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from queue import Queue
from typing import override

import pytest
from PIL import Image
from pydantic import SecretStr, ValidationError

from ...core.image_media_type import ImageMediaType
from ...core.config import LLMProvider, override_settings
from ...tests.fixtures.settings import EnvFileFreeSettings
from ...tests.loopback_llm import (
    SilentLoopbackHandler,
    openai_chat_reply,
    read_json_body,
    serving_loopback,
    write_json_response,
)
from ..client import LLMClient
from ..errors import LLMConfigError
from ..models import LLMRequest, MultimodalImageInput
from ..providers.anthropic import build_user_content
from ..providers.base import ProviderRequest
from ..providers.gemini import GeminiAdapter
from ..providers.local import LocalAdapter
from ..providers.openai import OpenAIAdapter

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


def _settings(tmp_path: Path, *, openai_chat_url: str | None = None) -> EnvFileFreeSettings:
    """Settings whose provider credentials exist but whose endpoints stay on this host."""
    base = EnvFileFreeSettings(
        cadrumo_llm_provider=LLMProvider.LOCAL,
        cadrumo_llm_model="gpt-oss",
        cadrumo_llm_cache_dir=tmp_path / "cache",
        cadrumo_llm_usage_dir=tmp_path / "usage",
        cadrumo_llm_run_telemetry_dir=tmp_path / "run-telemetry",
        cadrumo_llm_openai_api_key=SecretStr("sk-loopback-only"),
        cadrumo_llm_gemini_api_key=SecretStr("gemini-loopback-only"),
    )
    if openai_chat_url is None:
        return base
    return base.model_copy(update={"cadrumo_llm_openai_chat_completions_url": openai_chat_url})


def _client(settings: EnvFileFreeSettings) -> LLMClient:
    """Build a real client, letting it construct its own core-side stores.

    The cache and usage recorder are deliberately NOT injected. Passing them
    built exactly what ``LLMClient.__init__`` already defaults to, from the same
    two settings fields, so the injection changed nothing about the test and
    only added an import of the persistence-backed stores into this package.

    That import was the sole reason the inference subpackage appeared to reach
    persistence: the boundary contract walks import chains, and a test importing
    the core-side cache puts one there whether or not anything persists. The
    property the contract protects is real -- the encryption exemption rests on
    this package persisting nothing -- so the honest fix is to stop importing
    what the test never needed, not to carve the chain out.
    """
    return LLMClient(settings=settings)


@contextmanager
def _serve_openai() -> Iterator[tuple[str, Queue[dict[str, object]]]]:
    """Run a loopback endpoint speaking the OpenAI Chat Completions shape."""
    events: Queue[dict[str, object]] = Queue()

    class _Endpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            events.put({"body": read_json_body(self)})
            write_json_response(self, openai_chat_reply(" text-only completion "), status=HTTPStatus.OK)

    with serving_loopback(_Endpoint, path="/v1/chat/completions") as endpoint:
        yield endpoint, events


class TestTextOnlyProviderRefusesImages:
    """The safety-critical case: images must never be dropped in silence."""

    def test_a_vision_request_at_a_text_only_provider_refuses(self, tmp_path: Path) -> None:
        """Routing images at OpenAI raises, naming the provider and the images.

        The refusal must be reachable WITHOUT a network call -- it fires before
        dispatch, so no loopback endpoint is served here. If the guard were
        absent the request would leave for api.openai.com carrying only the
        prompt, which is precisely the silent discard being prevented.
        """
        settings = _settings(tmp_path)
        request = LLMRequest(
            prompt=_PROMPT,
            provider_override=LLMProvider.OPENAI,
            images=(_png_image(),),
        )
        with pytest.raises(LLMConfigError) as caught:
            asyncio.run(_client(settings).complete(request))
        verdict = caught.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.vision.input_supported"
        assert verdict.evidence[0].values == {
            "image_input_count": 1,
            "provider": LLMProvider.OPENAI.value,
            "vision_input_supported": False,
        }

    def test_the_refusal_also_covers_gemini(self, tmp_path: Path) -> None:
        """The second text-only adapter is gated by the same one guard.

        Named explicitly rather than left implied: the whole point of declaring
        capability as class data enforced at one dispatch point is that a
        second text-only adapter needs no code of its own to be safe.
        """
        settings = _settings(tmp_path)
        request = LLMRequest(
            prompt=_PROMPT,
            provider_override=LLMProvider.GEMINI,
            images=(_png_image(),),
        )
        with pytest.raises(LLMConfigError) as caught:
            asyncio.run(_client(settings).complete(request))
        verdict = caught.value.terminal_precondition_verdict
        assert verdict is not None
        assert verdict.failed_condition_id == "llm.vision.input_supported"
        assert verdict.evidence[0].values == {
            "image_input_count": 1,
            "provider": LLMProvider.GEMINI.value,
            "vision_input_supported": False,
        }

    def test_a_text_only_request_at_a_text_only_provider_still_succeeds(self, tmp_path: Path) -> None:
        """The guard is scoped to image-bearing requests and regresses nothing.

        A real HTTP round trip through the real OpenAI adapter to a loopback
        endpoint, so this fails if the guard ever widened to refuse an ordinary
        text completion.
        """
        with _serve_openai() as (endpoint, events):
            settings = _settings(tmp_path, openai_chat_url=endpoint)
            request = LLMRequest(prompt=_PROMPT, provider_override=LLMProvider.OPENAI)
            with override_settings(cadrumo_llm_openai_chat_completions_url=endpoint):
                response = asyncio.run(_client(settings).complete(request))

        assert response.text == "text-only completion"
        assert response.provider is LLMProvider.OPENAI
        observed = events.get_nowait()
        body = observed["body"]
        assert isinstance(body, Mapping)
        messages = body.get("messages")
        assert isinstance(messages, list)
        assert messages[-1] == {"role": "user", "content": _PROMPT}


class TestDeclaredImageCapability:
    """Capability is data on the adapter class, not per-adapter memory."""

    def test_only_the_adapters_that_forward_images_declare_support(self) -> None:
        """The declaration matches which adapters actually read ``request.images``.

        Anchored to the real classes rather than a hand-listed set of names, so
        a new adapter defaults to text-only and a rename cannot make this pass
        vacuously.
        """
        from ..providers.anthropic import AnthropicAdapter

        assert AnthropicAdapter.supports_images is True
        assert LocalAdapter.supports_images is True
        assert OpenAIAdapter.supports_images is False
        assert GeminiAdapter.supports_images is False


class TestAnthropicMultimodalPayload:
    """The Anthropic adapter builds a real Messages API content-block list."""

    def test_images_precede_the_text_and_carry_the_declared_media_type(self) -> None:
        """One base64 image block per input, then exactly one text block."""
        first = _png_image()
        second = MultimodalImageInput.from_base64(first.base64_data, ImageMediaType.JPEG)
        request = ProviderRequest(
            request_id="req",
            model="claude-opus-5",
            prompt=_PROMPT,
            system=None,
            max_tokens=64,
            temperature=0.0,
            timeout_s=3,
            images=(first, second),
        )

        content = build_user_content(request)

        assert isinstance(content, list)
        assert [block["type"] for block in content] == ["image", "image", "text"]
        assert content[0] == {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/png", "data": first.base64_data},
        }
        # The SECOND block proves the media type is carried per image from the
        # input that declared it, rather than assumed once for the whole request:
        # same bytes, different declaration, different block.
        assert content[1] == {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg", "data": second.base64_data},
        }
        assert content[2] == {"type": "text", "text": _PROMPT}

    def test_a_text_only_request_keeps_the_bare_string_content(self) -> None:
        """The text path is byte-identical to what it was before images existed."""
        request = ProviderRequest(
            request_id="req",
            model="claude-opus-5",
            prompt=_PROMPT,
            system=None,
            max_tokens=64,
            temperature=0.0,
            timeout_s=3,
        )
        assert build_user_content(request) == _PROMPT


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
        from ...core.hashing import sha256_hex

        buffer = BytesIO()
        Image.new("RGB", (4, 4), "white").save(buffer, format="PNG")
        raw = buffer.getvalue()
        built = MultimodalImageInput.from_base64(base64.b64encode(raw).decode("ascii"), ImageMediaType.PNG)
        assert built.content_sha256 == sha256_hex(raw)
