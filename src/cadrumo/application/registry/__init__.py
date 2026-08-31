"""Application services for read-only registry workflows.

Registry query and corpus validation services consume a
:class:`domain.calculations.registry.ValidatedRegistryAuthority` as
the single entry point for
:class:`domain.calculations.registry.ModeloDefinition` instances,
:class:`domain.calculations.registry.RegistrySnapshot` values, and
deadline windows.

This package root owns no type or function definitions of its own. It
once re-exported 87 sibling names through a lazy map; that map is retired
and the root exports nothing. The three local read surfaces each live in
their own module and are imported directly:
:mod:`application.registry.tree` (registry-tree inspection and
verification over the bundled ``registry/aeat`` tree),
:mod:`application.registry.corpus` (corpus/manual projection over
:class:`~application.registry.corpus.RegistryTopicProjection` and related
report records), and :mod:`application.registry.filed_state` (filed-state
comparison that loads captured AEAT observations before recomputing a
registry snapshot locally).

The observation-persistence path reads captured filed state through the
active-bucket encrypted observation store.

This namespace is inert: it declares an empty ``__all__``, defines nothing
and imports nothing. It once ran ``import_module("cadrumo.domain.renta")``
at module scope for one side effect -- registering the renta first-slice
routing cross-domain snapshot check that a Modelo 100 snapshot requires.
That registration is no longer a composition-root duty: the snapshot builder
imports the registering module by name at the start of every snapshot build,
so the gate is present regardless of which packages the importing process
happened to load. Importing this root now costs only its parent packages;
the weight is in the submodules, and :mod:`application.registry.tree` alone
pulls in roughly six hundred. A consumer measuring this package's cost must
measure the submodule it actually imports, never the root.

See Also:
    :class:`domain.calculations.registry.ValidatedRegistryAuthority`
        Domain authority used to load, validate, and snapshot modelo registry
        definitions.
    :class:`~application.registry.tree.RegistryTreeReport`
        Application report returned by registry-tree inspection and verification.
    :class:`RegistryCitationsListReport`
        Citation projection over reviewed registry legal references and topics.
    :class:`RegistryManualVerificationReport`
        Manual/casilla verification report for bundled manual corpus checks.
    :mod:`domain.manuals`
        Strict manual schema and loader surface that owns extracted manual
        records and :class:`domain.manuals.ManualCasillaReference` values.
    :mod:`core.resources`
        Bundled-data boundary used to locate packaged registry and corpus
        material without repository-relative path reads.
    :class:`~application.registry.filed_state.FiledStateVerificationReport`
        Filed-state comparison report built from encrypted captured AEAT
        observations and local registry recalculation.
    :class:`adapters.outbound.aeat.sede.FiledDeclaracionObservationStore`
        Active-bucket observation store that persists captured filed state for
        local registry comparison.
    :mod:`application.modelo.registry_discovery`
        Modelo work-unit discovery queries consumed by operator surfaces.
"""

from __future__ import annotations

__all__: tuple[str, ...] = ()
