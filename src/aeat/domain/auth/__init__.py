"""Domain layer for AEAT auth protocol primitives.

Re-exports the apoderamientos scope vocabulary so callers import from the package
root rather than reaching into the ``apoderamientos`` submodule.
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
