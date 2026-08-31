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

THIS NAMESPACE IS NOT INERT TO IMPORT: the root still eagerly runs
``import_module("cadrumo.domain.renta")`` at module scope to register the
first-slice routing cross-domain snapshot check required by Modelo 100
snapshots. That import alone costs roughly 613 modules and ~1.3s wall
time (measured against a clean interpreter) -- retiring the lazy-export
map and moving the tree/filed-state definitions out did NOT make touching
this package cheap. Any future consumer measuring this package's cost
must account for that eager renta import, not just the (now-retired) lazy
map.

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

from importlib import import_module

# RULED SUPERSEDED, not yet removed. This import exists to trigger
# ``cadrumo.domain.renta``'s cross-domain check registration, and
# ``domain.calculations.registry._snapshot_internals`` now does the same thing
# better: idempotent, flag-guarded, and run at the start of EVERY snapshot
# build. Its docstring names this site as the problem it solves -- "registration
# no longer relies on a composition root happening to import renta before the
# first M100 snapshot".
#
# So this namespace is inert (`__all__` is empty) and its only content is a side
# effect, which is the worst pairing: nothing to import it FOR, yet importing it
# does work. Removing it is a behaviour change on a registration path and wants
# a green tree to land against; recorded here rather than deleted blind.
import_module("cadrumo.domain.renta")

__all__: tuple[str, ...] = ()
