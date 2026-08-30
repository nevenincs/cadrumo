"""Smoke tests for the :mod:`cadrumo.adapters.outbound.llm` subpackage."""

import pytest

from .....llm.client import LLMClient
from .....llm.errors import LLMError
from .....llm.models import LLMRequest, LLMResponse, PromptRegistry
from .. import LLMCache
from .. import __all__ as llm_all

pytestmark = [pytest.mark.unit, pytest.mark.hex_outbound_adapter]

_REQUIRED_SYMBOLS = [
    # Narrowed by the llm-package-split relocation: this package now owns ONLY
    # the three persistence-touching stores, which stay on the core side of the
    # boundary because they resolve secure storage. Everything else -- the
    # client, models, errors, pricing, retention selector and provider adapters
    # -- moved to the gated `cadrumo.llm` subpackage and is asserted there.
    "LLMCache",
    "LLMRunRecord",
    "LLMRunTelemetryRecorder",
    "LLMRunTelemetrySummary",
    "UsageRecorder",
]


def test_smoke_llm_public_surface_is_complete() -> None:
    """Every required public symbol is exported in __all__ and importable."""
    missing = [sym for sym in _REQUIRED_SYMBOLS if sym not in llm_all]
    assert not missing, f"llm __all__ is missing symbols: {missing}"


def test_smoke_llm_key_symbols_are_importable() -> None:
    """Key concrete symbols are importable and have the expected types."""
    import inspect

    assert inspect.isclass(LLMClient), "LLMClient must be a class"
    assert inspect.isclass(LLMCache), "LLMCache must be a class"
    assert inspect.isclass(LLMRequest), "LLMRequest must be a class"
    assert inspect.isclass(LLMResponse), "LLMResponse must be a class"
    assert inspect.isclass(PromptRegistry), "PromptRegistry must be a class"
    assert inspect.isclass(LLMError), "LLMError must be a class"
    assert issubclass(LLMError, Exception), "LLMError must inherit from Exception"
