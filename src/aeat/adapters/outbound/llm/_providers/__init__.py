"""Provider package facade for public LLM adapter helpers."""

from typing import TYPE_CHECKING

from .base import ProviderCompletion, ProviderRequest
from .gemini import GeminiAdapter
from .local import LocalAdapter, rasterise_pdf_pages_to_base64_png
from .openai import OpenAIAdapter

if TYPE_CHECKING:
    # Runtime access stays lazy so importing this package does not construct
    # the optional Anthropic SDK boundary. AnthropicAdapter itself remains
    # importable without the extra; construction performs the guarded load.
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
