"""Namespace root for AEAT calculation-domain authorities.

This package is a namespace container, not a public aggregation facade. Callers
import the filing-grade registry authority from
:mod:`registry`, where
:class:`registry.ValidatedRegistryAuthority`,
:class:`registry.RegistrySnapshot`, and
:func:`registry.calculate_registry_snapshot` live.

Nothing is re-exported at this level by design. Exporting here would couple
callers to the internal subpackage layout and undermine the hexagonal-layer
discipline.

See Also:
    :mod:`registry`
        Legal calculation registry, snapshot, formula, binding, relation,
        export-layout, and observation authority.
    :mod:`application.calculations`
        Application-side source stores and prefill helpers that prepare
        registry binding and relation inputs without becoming domain authority.
"""
