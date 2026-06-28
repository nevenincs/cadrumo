"""Cross-domain snapshot referential-integrity hooks.

Defines the :class:`CrossDomainSnapshotCheck` protocol and the registry
used to run peer-domain checks against a :class:`RegistrySnapshot` at
snapshot-build time without importing peer domains directly.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from ....core import Modelo
from ._ids import CasillaId

if TYPE_CHECKING:
    from ._snapshot import RegistrySnapshot


class CrossDomainSnapshotCheck(Protocol):
    """Snapshot-time referential-integrity check owned by a peer domain.

    A peer domain (for example :mod:`aeat.domain.renta`) may need to
    assert that the casilla ids it routes to are real casillas on a
    registry snapshot. The registry must not import the peer domain
    directly -- that reverses the hexagonal dependency direction. Instead
    the peer domain registers a :class:`CrossDomainSnapshotCheck` via
    :func:`register_cross_domain_snapshot_check`; the registry calls
    every registered check at snapshot-build time without naming the
    peer.

    A check receives the modelo id and the snapshot's casilla id set
    and returns a list of failure strings (empty when consistent).
    """

    def __call__(self, modelo_id: str, casilla_ids: frozenset[CasillaId]) -> list[str]: ...


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
    :mod:`aeat.domain.renta`. That check registers itself only as an
    import side effect of the ``renta`` package. A ``build_snapshot``
    caller that never imports ``renta`` would otherwise validate an
    M100 snapshot with the gate silently absent. Rather than skip a
    known-required gate, fail loudly so the missing registration
    surfaces at snapshot build instead of as a later runtime KeyError.
    """
    casilla_ids = frozenset(checker.casilla_ids)
    if snapshot.modelo.id == Modelo.M100 and not _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        checker.failures.append(
            f"{checker.prefix}: modelo 100 requires the renta first-slice "
            "routing cross-domain snapshot check, but no cross-domain checks "
            "are registered -- import aeat.domain.renta at the composition "
            "point that builds the snapshot so register_cross_domain_snapshot_check "
            "runs before validation",
        )
    for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        for failure in check(snapshot.modelo.id, casilla_ids):
            checker.failures.append(f"{checker.prefix}: {failure}")
