"""Namespace root for AEAT calculation-domain authorities.

This package is a namespace container, not a public aggregation facade. Callers
import the filing-grade registry authority from
:mod:`aeat.domain.calculations.registry`, where
:class:`~aeat.domain.calculations.registry.ValidatedRegistryAuthority`,
:class:`~aeat.domain.calculations.registry.RegistrySnapshot`, and
:func:`~aeat.domain.calculations.registry.calculate_registry_snapshot` live.

Nothing is re-exported at this level by design. Exporting here would couple
callers to the internal subpackage layout and undermine the hexagonal-layer
discipline.

See Also:
    :mod:`aeat.domain.calculations.registry`
        Legal calculation registry, snapshot, formula, binding, relation,
        export-layout, and observation authority.
    :mod:`aeat.application.calculations`
        Application-side source stores and prefill helpers that prepare
        registry binding and relation inputs without becoming domain authority.
"""
