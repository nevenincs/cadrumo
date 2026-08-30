"""AEAT apoderamiento scope catalogue and token parser.

This package loads the shipped ``registry/aeat/apoderamientos/scopes.toml``
catalogue as an :class:`ApoderamientosCatalogue` of :class:`ApoderadoScope`
records and exposes :func:`parse_scope_tokens` for operator-supplied ``--scope``
values. The parser is a domain validation boundary: scope codes must be
uppercase catalogue tokens, ``ALL`` expands to every catalogue code,
comma-separated values are rejected, duplicate scopes are deduplicated, and
unknown codes raise :class:`UnknownScopeError`.

The package only defines the scope vocabulary and validation rules. Persisted
represented-party configuration, active-bucket routing, and the permanent
refusal of live AEAT-side apoderamiento mutation are application concerns owned
by :class:`application.auth.ApoderadoService`.

See Also:
    - :mod:`domain.auth` for the parent re-export facade.
    - :class:`application.auth.ApoderadoService` for the encrypted
      bucket-scoped configuration service that consumes these parsed scope
      codes.
    - :mod:`entrypoints.cli._config._apoderado` for CLI commands that
      collect repeated ``--scope`` options before calling the application
      service.
"""

from __future__ import annotations

from .catalogue import (
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
