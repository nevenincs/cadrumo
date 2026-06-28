"""Domain facade for AEAT apoderamiento scope parsing primitives.

Re-exports :class:`ApoderadoScope`, :class:`ApoderamientosCatalogue`, and
:class:`UnknownScopeError` together with :func:`parse_scope_tokens` so callers
can import the scope vocabulary from :mod:`aeat.domain.auth`.
"""

from __future__ import annotations

from .apoderamientos import (
    ALL_TOKEN,
    ApoderadoScope,
    ApoderamientosCatalogue,
    UnknownScopeError,
    expand_all_token,
    load_default_catalogue,
    parse_scope_tokens,
)

__all__ = [
    "ALL_TOKEN",
    "ApoderadoScope",
    "ApoderamientosCatalogue",
    "UnknownScopeError",
    "expand_all_token",
    "load_default_catalogue",
    "parse_scope_tokens",
]
