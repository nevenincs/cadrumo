"""Private provider adapters for the LLM package.

The two underscore-prefixed names ``_ProviderAdapter`` and
``_DeterministicAdapter`` are intentionally available to internal
callers via this package as redundant aliases; they are NOT part of
the public star-import surface and stay absent from ``__all__``.
"""

from .anthropic import AnthropicAdapter
from .base import ProviderCompletion, ProviderRequest
from .base import _ProviderAdapter as _ProviderAdapter
from .deterministic import _DeterministicAdapter as _DeterministicAdapter
from .gemini import GeminiAdapter
from .local import LocalAdapter, rasterise_pdf_pages_to_base64_png
from .openai import OpenAIAdapter

__all__ = [
    "AnthropicAdapter",
    "GeminiAdapter",
    "LocalAdapter",
    "OpenAIAdapter",
    "ProviderCompletion",
    "ProviderRequest",
    "rasterise_pdf_pages_to_base64_png",
]
