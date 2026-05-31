"""Central registry for legally approved AEAT calculation definitions.

This package is a namespace container. Callers must import from the
``aeat.domain.calculations.registry`` subpackage directly; nothing is
re-exported at this level by design. Exporting here would couple callers to
the internal subpackage layout and undermine the hexagonal-layer discipline.
"""
