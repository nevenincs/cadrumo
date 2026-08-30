"""LLM provider adapters, one module per vendor boundary.

Inert namespace. Each adapter is reached at its own module --
:mod:`~cadrumo.llm.providers.base` for the request and completion contracts,
and ``anthropic``, ``gemini``, ``openai`` and ``local`` for the adapters.

This package re-exported all six eagerly and deferred ``AnthropicAdapter``
behind a ``__getattr__`` arm, so that importing the package would not construct
the optional Anthropic SDK boundary. The guard protected nothing: the only
caller, :mod:`~cadrumo.llm.client`, already imported that adapter from its own
module at the point of construction, and no code path ever reached the lazy
arm.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
