"""The transport omits request parameters the resolved model does not accept.

The sibling of the vision boundary, and the second half of one defect. Both are
a request field the transport assumed was universal, and they fail in opposite
directions: ``images`` was silently DROPPED by adapters that could not carry it,
and ``temperature`` was unconditionally SENT to models that reject it. The
omission is decided once, at the client's dispatch point, from what the adapter
declares for the resolved model.
"""

from __future__ import annotations

from typing import override

import pytest

from .....core.config_support import LLMProvider
from ..client import LLMClient
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

    provider = LLMProvider.AGENT

    @override
    def unsupported_parameters(self, model: str) -> frozenset[str]:
        return frozenset({"temperature"}) if model == "picky-model" else frozenset[str]()

    @override
    async def complete(self, request: ProviderRequest) -> ProviderCompletion:  # pragma: no cover - never called
        raise NotImplementedError


def test_the_dispatch_point_clears_a_parameter_the_model_refuses() -> None:
    """The omission decision is made once, at dispatch, not in each adapter.

    Mirrors where the image boundary is enforced, and for the same reason: which
    parameters a model accepts is a property of the dispatch, never of every
    adapter remembering to check.
    """
    request = _request(model="picky-model", temperature=0.7)

    cleared = LLMClient._omit_unsupported_parameters(_RefusesTemperature(), request)

    assert cleared.temperature is None


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
        provider = LLMProvider.AGENT

        @override
        async def complete(self, request: ProviderRequest) -> ProviderCompletion:  # pragma: no cover
            raise NotImplementedError

    assert _Plain().unsupported_parameters("any-model") == frozenset()
