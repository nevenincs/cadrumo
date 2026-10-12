"""The transport omits request parameters the resolved model does not accept.

The sibling of the vision boundary, and the second half of one defect. Both are
a request field the transport assumed was universal, and they fail in opposite
directions: ``images`` was silently DROPPED by adapters that could not carry it,
and ``temperature`` was unconditionally SENT to models that reject it with a
400 -- which capped the product at the older model generation. One was dropped
without telling anyone; one was sent without asking.

The claim under test is ABSENCE FROM THE WIRE SHAPE, not a defaulted value. A
defaulted parameter and an omitted one are different requests, and only the
second is accepted by the models that refuse it. Nothing here is mocked: the
payload asserted is the payload the adapter actually builds, and the wire case
reads the JSON body the real SDK sends to a loopback endpoint.

The Anthropic SDK's ``messages.create`` accepts no sampling parameters at all,
so for that adapter ``temperature`` is unsupported for every model and must
never reach the wire, whatever the operator configured.
"""

from __future__ import annotations

import asyncio
import inspect
from collections.abc import Generator, Mapping
from contextlib import contextmanager
from http import HTTPStatus
from queue import Queue
from typing import Final, override

import pytest

from .....tests.loopback_llm import SilentLoopbackHandler, read_json_body, serving_loopback, write_json_response
from ..client import LLMClient
from ..providers.anthropic import AnthropicAdapter, build_message_kwargs
from ..providers.base import ProviderAdapter, ProviderCompletion, ProviderRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_SAMPLING_PARAMETERS: Final = frozenset({"temperature", "top_p", "top_k"})
_MESSAGES_PATH: Final = "/v1/messages"


def _request(
    *,
    model: str = "test-model",
    system: str | None = None,
    temperature: float | None = None,
) -> ProviderRequest:
    """Build a request carrying only the fields a case varies.

    A factory rather than a shared dict splatted into the constructor. An
    inferred ``dict`` widens every value to the union of all of them, so
    ``ProviderRequest(**_BASE)`` checked that each field accepted ``str | int``
    -- which none of them do -- and the splat verified nothing about the shape
    it was building. The fields that never vary stay here so a case reads as
    the one axis it exercises.
    """
    return ProviderRequest(
        request_id="req-1",
        model=model,
        prompt="read this",
        system=system,
        max_tokens=64,
        temperature=temperature,
        timeout_s=30,
    )


class _RefusesTemperature(ProviderAdapter):
    """An adapter whose model rejects an explicitly-sent temperature."""

    provider = None  # type: ignore[assignment]  # reason: payload-shape probe, never dispatched

    @override
    def unsupported_parameters(self, model: str) -> frozenset[str]:
        return frozenset({"temperature"}) if model == "picky-model" else frozenset[str]()

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:  # pragma: no cover - never called
        raise NotImplementedError


def test_an_omitted_temperature_is_absent_from_the_wire_shape() -> None:
    """Absent means the key is not in the payload, not that it carries a default.

    Asserted on membership rather than on the value, because ``temperature:
    null`` is a STATED value on the wire and draws the same rejection the number
    would. A test asserting ``kwargs["temperature"] is None`` would pass against
    exactly the payload that fails in production.
    """
    kwargs = build_message_kwargs(_request())

    assert "temperature" not in kwargs


def test_a_supplied_temperature_never_reaches_the_anthropic_wire_shape() -> None:
    """The builder carries no sampling key even when the request holds one.

    The SDK's ``messages.create`` has no ``temperature``, ``top_p`` or ``top_k``
    parameter, so a payload carrying one would raise ``TypeError`` at the call.
    The operator's setting is cleared at dispatch through the adapter's declared
    capability, asserted separately below.
    """
    kwargs = build_message_kwargs(_request(temperature=0.25))

    assert _SAMPLING_PARAMETERS.isdisjoint(kwargs)


def test_every_payload_key_is_a_parameter_the_installed_sdk_accepts() -> None:
    """The payload matches the real ``messages.create`` signature, key for key.

    The independent oracle is the installed SDK itself: a key it does not
    declare is a ``TypeError`` at the call site, and the sampling parameters
    must be absent from both sides.
    """
    from anthropic.resources.messages import AsyncMessages

    accepted = frozenset(inspect.signature(AsyncMessages.create).parameters)
    kwargs = build_message_kwargs(_request(system="be terse", temperature=0.25))

    assert frozenset(kwargs) <= accepted
    assert _SAMPLING_PARAMETERS.isdisjoint(accepted)


def test_the_anthropic_adapter_declares_temperature_unsupported_for_every_model() -> None:
    """The adapter states the SDK's constraint through the capability axis.

    Checked across model identities because the declaration is adapter-wide:
    no Anthropic model can receive a parameter the SDK cannot send.
    """
    adapter = AnthropicAdapter(api_key="sk-test-not-a-key", timeout_s=30)

    for model in ("claude-sonnet-4-6", "claude-opus-4-1", "any-future-model"):
        assert "temperature" in adapter.unsupported_parameters(model)


def test_the_dispatch_point_clears_temperature_for_the_anthropic_adapter() -> None:
    """The client's single omission path clears the operator's temperature."""
    adapter = AnthropicAdapter(api_key="sk-test-not-a-key", timeout_s=30)
    request = _request(model="claude-sonnet-4-6", temperature=0.7)

    cleared = LLMClient._omit_unsupported_parameters(adapter, request)

    assert cleared.temperature is None


@contextmanager
def _serve_anthropic_messages() -> Generator[tuple[str, Queue[Mapping[str, object]]]]:
    """Serve a Messages-API-shaped endpoint that records every request body."""
    bodies: Queue[Mapping[str, object]] = Queue()

    class _MessagesEndpoint(SilentLoopbackHandler):
        @override
        def do_POST(self) -> None:
            bodies.put(read_json_body(self))
            write_json_response(
                self,
                {
                    "id": "msg_loopback",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-6",
                    "content": [{"type": "text", "text": " read "}],
                    "stop_reason": "end_turn",
                    "stop_sequence": None,
                    "usage": {"input_tokens": 7, "output_tokens": 2},
                },
                status=HTTPStatus.OK,
            )

    with serving_loopback(_MessagesEndpoint, path=_MESSAGES_PATH) as endpoint:
        yield endpoint.removesuffix(_MESSAGES_PATH), bodies


def test_the_anthropic_request_body_on_the_wire_carries_no_sampling_parameter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The JSON the real SDK sends holds no ``temperature``, ``top_p`` or ``top_k``.

    Crosses the production dispatch clearing, the adapter, the SDK and its HTTP
    transport against a loopback endpoint, so the assertion is on the bytes that
    actually left the process rather than on a builder's return value.
    """
    with _serve_anthropic_messages() as (base_url, bodies):
        monkeypatch.setenv("ANTHROPIC_BASE_URL", base_url)
        adapter = AnthropicAdapter(api_key="sk-test-not-a-key", timeout_s=5)
        request = LLMClient._omit_unsupported_parameters(
            adapter,
            _request(model="claude-sonnet-4-6", system="be terse", temperature=0.7),
        )
        completion = asyncio.run(adapter.complete(request))

    assert bodies.qsize() == 1
    body = bodies.get_nowait()
    assert _SAMPLING_PARAMETERS.isdisjoint(body)
    assert body["model"] == "claude-sonnet-4-6"
    assert body["system"] == "be terse"
    assert completion.text == "read"
    assert completion.provider_request_id == "msg_loopback"


def test_the_dispatch_point_clears_a_parameter_the_model_refuses() -> None:
    """The omission decision is made once, at dispatch, not in each adapter.

    Mirrors where the image boundary is enforced, and for the same reason: which
    parameters a model accepts is a property of the dispatch, never of every
    adapter remembering to check.
    """
    request = _request(model="picky-model", temperature=0.7)

    cleared = LLMClient._omit_unsupported_parameters(_RefusesTemperature(), request)

    assert cleared.temperature is None
    assert "temperature" not in build_message_kwargs(cleared)


def test_the_dispatch_point_leaves_a_parameter_the_model_accepts() -> None:
    """Positive control for the clearing above.

    A dispatch that cleared every parameter unconditionally would satisfy the
    previous case. This pins that the model identity is what decides, so the
    same adapter keeps the parameter for a model that accepts it.
    """
    request = _request(model="tolerant-model", temperature=0.7)

    kept = LLMClient._omit_unsupported_parameters(_RefusesTemperature(), request)

    assert kept.temperature == 0.7


def test_an_adapter_declares_no_unsupported_parameters_by_default() -> None:
    """The default is permissive here, and deliberately unlike ``supports_images``.

    Silently dropping an image makes a model answer from nothing, so that axis
    defaults restrictive. Omitting a sampling parameter falls back to the
    vendor's own default, so this axis defaults permissive: a restrictive
    default would strip ``temperature`` from every working provider on the day
    it landed. The asymmetry is the size of the harm, not an oversight.
    """

    class _Plain(ProviderAdapter):
        provider = None  # type: ignore[assignment]  # reason: probe only

        @override
        async def complete(self, request: ProviderRequest) -> ProviderCompletion:  # pragma: no cover
            raise NotImplementedError

    assert _Plain().unsupported_parameters("any-model") == frozenset()


def test_the_system_prompt_is_omitted_rather_than_sent_as_null() -> None:
    """The same absence rule the collapsed call sites used to express as a branch.

    ``system`` was previously handled by duplicating the whole ``messages.create``
    call; the builder now expresses its absence by omitting the key.
    """
    without = build_message_kwargs(_request())
    with_system = build_message_kwargs(_request(system="be terse"))

    assert "system" not in without
    assert with_system["system"] == "be terse"
