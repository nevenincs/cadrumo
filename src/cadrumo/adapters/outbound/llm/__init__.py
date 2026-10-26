"""Inert namespace for the outbound LLM adapter.

Each public contract is imported from the module that defines it. For example,
``LLMClient`` comes from ``client``, ``LLMRequest`` from ``models``, and
``LLMCache`` from ``cache``. Keeping this initializer inert prevents a package
facade from becoming a second public definition or from eagerly importing the
optional provider boundary.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
