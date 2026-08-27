"""Cross-domain snapshot referential-integrity hooks.

Defines the :class:`CrossDomainSnapshotCheck` protocol and the registry
used to run peer-domain checks against a :class:`RegistrySnapshot` at
snapshot-build time without importing peer domains directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ....core import CasillaId, Modelo
from .ids import BindingId

if TYPE_CHECKING:
    from .schema import RegistrySnapshot


class CrossDomainSnapshotCheck(Protocol):
    """Snapshot-time referential-integrity check owned by a peer domain.

    A peer domain (for example :mod:`cadrumo.domain.renta`) may need to
    assert that the casilla ids it routes to are real casillas on a
    registry snapshot. The registry must not import the peer domain
    directly -- that reverses the hexagonal dependency direction. Instead
    the peer domain registers a :class:`CrossDomainSnapshotCheck` via
    :func:`register_cross_domain_snapshot_check`; the registry calls
    every registered check at snapshot-build time without naming the
    peer.

    A check receives the modelo id, the snapshot's casilla id set, the
    revision's OWN renta first-slice ledger-aggregation binding target
    casillas (a strict subset of the universal routing table's codomain --
    older revisions may declare no such bindings at all, so their required
    set is legitimately empty), and the revision's declared binding ids. It
    returns a list of failure strings (empty when consistent).

    Both derived inputs exist for the same reason: a peer-domain routing
    assertion should be conditional on the revision actually declaring the
    thing that creates the requirement. A check that asserts unconditionally
    over a modelo fires on revisions it has no claim over -- including the
    synthetic ones built to exercise unrelated properties -- and a gate that
    reddens where it has no claim trains its readers to work around it.
    ``revision_binding_ids`` carries a default so a registered check that
    predates it stays callable, which keeps the widening additive.
    """

    def __call__(
        self,
        modelo_id: str,
        casilla_ids: frozenset[CasillaId],
        renta_first_slice_binding_targets: frozenset[CasillaId],
        revision_binding_ids: frozenset[BindingId] = ...,
    ) -> list[str]:
        """Return the snapshot-routing failures detected by this peer-domain check."""


_CROSS_DOMAIN_SNAPSHOT_CHECKS: list[CrossDomainSnapshotCheck] = []
CROSS_DOMAIN_SNAPSHOT_CHECKS = _CROSS_DOMAIN_SNAPSHOT_CHECKS


def register_cross_domain_snapshot_check(check: CrossDomainSnapshotCheck) -> None:
    """Register a peer-domain snapshot referential-integrity check.

    Idempotent: registering the same callable twice is a no-op so a
    peer-domain module re-imported in a fresh interpreter (or under
    test reload) does not stack duplicate checks.
    """
    if check not in _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        _CROSS_DOMAIN_SNAPSHOT_CHECKS.append(check)


class _SnapshotReferenceChecker(Protocol):
    prefix: str
    failures: list[str]
    casilla_ids: set[CasillaId]


def check_cross_domain_snapshot_routing(
    checker: _SnapshotReferenceChecker,
    snapshot: RegistrySnapshot,
) -> None:
    """Run every registered peer-domain referential-integrity check.

    The registry depends on the abstract :class:`CrossDomainSnapshotCheck`
    Protocol only. Concrete checks (such as the renta first-slice
    routing gate) are injected by their owning domain at import time
    via :func:`register_cross_domain_snapshot_check`.

    Args:
        checker: Snapshot reference checker that accumulates per-prefix
            ``failures`` and exposes the casilla id set against which
            registered cross-domain checks evaluate routing references.
        snapshot: The :class:`RegistrySnapshot` to run peer-domain checks against.

    Modelo 100 has a known-required cross-domain gate -- the renta
    first-slice routing referential-integrity check owned by
    :mod:`cadrumo.domain.renta`. That check registers itself only as an
    import side effect of the ``renta`` package. A ``build_snapshot``
    caller that never imports ``renta`` would otherwise validate an
    M100 snapshot with the gate silently absent. Rather than skip a
    known-required gate, fail loudly so the missing registration
    surfaces at snapshot build instead of as a later runtime KeyError.
    """
    from .ledger_bindings import renta_first_slice_binding_target_casillas

    casilla_ids = frozenset(checker.casilla_ids)
    renta_first_slice_binding_targets = renta_first_slice_binding_target_casillas(snapshot.revision)
    revision_binding_ids = frozenset(binding.id for binding in snapshot.revision.bindings)
    if snapshot.modelo.id == Modelo.M100 and not _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        checker.failures.append(
            f"{checker.prefix}: modelo 100 requires the renta first-slice "
            "routing cross-domain snapshot check, but no cross-domain checks "
            "are registered -- import cadrumo.domain.renta at the composition "
            "point that builds the snapshot so register_cross_domain_snapshot_check "
            "runs before validation",
        )
    for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        for failure in check(
            snapshot.modelo.id,
            casilla_ids,
            renta_first_slice_binding_targets,
            revision_binding_ids,
        ):
            checker.failures.append(f"{checker.prefix}: {failure}")
