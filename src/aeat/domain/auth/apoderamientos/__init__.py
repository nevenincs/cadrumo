"""AEAT apoderamientos scope vocabulary domain layer.

Loads the shipped scopes catalogue from ``registry/aeat/apoderamientos/
scopes.toml`` and exposes typed parsing for operator-supplied scope
flags. Contract:

  * scope codes are uppercase tokens drawn from the shipped catalogue
  * the literal ``ALL`` expands at command time into every catalogue code
  * comma-separated values are rejected at the parser boundary
  * duplicate scopes in one invocation are silently deduplicated
  * unknown scopes refuse with a typed validation error

This module uses :class:`ApoderadoScope` for parsing and validating scope tokens.
"""

from __future__ import annotations

from ._catalogue import (
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
