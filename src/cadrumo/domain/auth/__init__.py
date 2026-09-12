"""Inert namespace for AEAT apoderamiento scope vocabulary.

The defining :mod:`domain.auth.apoderamientos.catalogue` module owns
:class:`ApoderadoScope`, :class:`ApoderamientosCatalogue`,
:func:`parse_scope_tokens`, and :class:`UnknownScopeError`; it does not persist
represented-party configuration or contact AEAT.

The package initializer exports no symbols.

See Also:
    - :mod:`domain.auth.apoderamientos` for the shipped scope catalogue,
      ``ALL`` expansion, comma rejection, deduplication, and unknown-scope
      refusal rules.
    - :class:`application.auth.ApoderadoService` for encrypted,
      bucket-scoped represented-party configuration built on this vocabulary.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
