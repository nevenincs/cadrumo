"""AEAT apoderamiento scope catalogue and token parser.

The defining ``catalogue`` module adapts the published runtime scope catalogue
as an :class:`ApoderamientosCatalogue` of :class:`ApoderadoScope` records and
defines :func:`parse_scope_tokens` for operator-supplied ``--scope``
values. The parser is a domain validation boundary: scope codes must be
uppercase catalogue tokens, ``ALL`` expands to every catalogue code,
comma-separated values are rejected, duplicate scopes are deduplicated, and
unknown codes raise :class:`UnknownScopeError`.

The subpackage only owns the scope vocabulary and validation rules; its
initializer exports no symbols. Persisted
represented-party configuration, active-bucket routing, and the permanent
refusal of live AEAT-side apoderamiento mutation are application concerns owned
by :class:`application.auth.ApoderadoService`.

See Also:
    - :mod:`domain.auth` for the inert parent namespace.
    - :class:`application.auth.ApoderadoService` for the encrypted
      bucket-scoped configuration service that consumes these parsed scope
      codes.
    - :mod:`entrypoints.cli.config._apoderado` for CLI commands that
      collect repeated ``--scope`` options before calling the application
      service.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
