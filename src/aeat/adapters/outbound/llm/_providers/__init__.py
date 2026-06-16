"""Private provider adapters for the LLM package.

The two underscore-prefixed names ``_ProviderAdapter`` and
``_DeterministicAdapter`` are intentionally available to internal
callers via this package as redundant aliases; they are NOT part of
the public star-import surface and stay absent from ``__all__``.
"""

from typing import TYPE_CHECKING

from .base import ProviderCompletion, ProviderRequest
from .base import _ProviderAdapter as _ProviderAdapter
from .deterministic import _DeterministicAdapter as _DeterministicAdapter
from .gemini import GeminiAdapter
from .local import LocalAdapter, rasterise_pdf_pages_to_base64_png
from .openai import OpenAIAdapter

if TYPE_CHECKING:
    # AnthropicAdapter eagerly imports the optional `anthropic` SDK at module
    # load, so it is exposed lazily via __getattr__ — importing this package (as
    # the LLM client does) must not pull in the `anthropic` extra. The boundary
    # guard lives in LLMClient._build_adapter (require_optional_extra).
    from .anthropic import AnthropicAdapter

__all__ = [
    "AnthropicAdapter",
    "GeminiAdapter",
    "LocalAdapter",
    "OpenAIAdapter",
    "ProviderCompletion",
    "ProviderRequest",
    "rasterise_pdf_pages_to_base64_png",
]


def __getattr__(name: str) -> object:
    if name == "AnthropicAdapter":
        from .anthropic import AnthropicAdapter

        return AnthropicAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
