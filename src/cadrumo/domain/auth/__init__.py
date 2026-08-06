"""Domain facade for AEAT apoderamiento scope vocabulary.

This package re-exports the catalogue and parser primitives from
:mod:`domain.auth.apoderamientos` so callers can import the authorization
scope vocabulary from :mod:`domain.auth`. The domain layer owns
:class:`ApoderadoScope`, :class:`ApoderamientosCatalogue`,
:func:`parse_scope_tokens`, and :class:`UnknownScopeError`; it does not persist
represented-party configuration or contact AEAT.

See Also:
    - :mod:`domain.auth.apoderamientos` for the shipped scope catalogue,
      ``ALL`` expansion, comma rejection, deduplication, and unknown-scope
      refusal rules.
    - :class:`application.auth.ApoderadoService` for encrypted,
      bucket-scoped represented-party configuration built on this vocabulary.
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
