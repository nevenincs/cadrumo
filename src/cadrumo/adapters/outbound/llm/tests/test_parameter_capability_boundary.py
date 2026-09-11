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
payload asserted is the payload the adapter actually builds, reachable with no
API key, no network, and no SDK.
"""

from __future__ import annotations

from typing import override

import pytest

from ..client import LLMClient
from ..providers.anthropic import build_message_kwargs
from ..providers.base import ProviderAdapter, ProviderCompletion, ProviderRequest

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]


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


def test_a_supplied_temperature_does_reach_the_wire_shape() -> None:
    """Positive control.

    Without it, a builder that never emitted ``temperature`` under any
    circumstance would satisfy the absence assertion and look correct while
    silently discarding an operator's explicit setting.
    """
    kwargs = build_message_kwargs(_request(temperature=0.25))

    assert kwargs["temperature"] == 0.25


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
    same adapter carries the parameter for a model that accepts it.
    """
    request = _request(model="tolerant-model", temperature=0.7)

    kept = LLMClient._omit_unsupported_parameters(_RefusesTemperature(), request)

    assert kept.temperature == 0.7
    assert build_message_kwargs(kept)["temperature"] == 0.7


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
    call. That duplication is why ``temperature`` appeared at two sites, and why
    changing one would have left the other sending it.
    """
    without = build_message_kwargs(_request())
    with_system = build_message_kwargs(_request(system="be terse"))

    assert "system" not in without
    assert with_system["system"] == "be terse"
