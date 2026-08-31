"""Namespace root for AEAT calculation-domain authorities.

This package is a namespace container, not a public aggregation facade. Callers
import the filing-grade registry authority from
:mod:`registry`, where
:class:`registry.ValidatedRegistryAuthority`,
:class:`registry.RegistrySnapshot`, and
:func:`registry.calculate_registry_snapshot` live.

Only the generic row-source identity value object is exported here because it
crosses application source resolution and domain revision persistence without
belonging to either adapter.

See Also:
    :mod:`registry`
        Legal calculation registry, snapshot, formula, binding, relation,
        export-layout, and observation authority.
    :mod:`application.calculations`
        Application-side source stores and prefill helpers that prepare
        registry binding and relation inputs without becoming domain authority.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
