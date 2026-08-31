"""Cross-domain snapshot referential-integrity hooks.

Defines the :class:`CrossDomainSnapshotCheck` protocol and the registry
used to run peer-domain checks against a :class:`RegistrySnapshot` at
snapshot-build time without importing peer domains directly.
"""

from __future__ import annotations

from collections.abc import Collection, Mapping
from types import MappingProxyType
from typing import TYPE_CHECKING, Protocol

from ....core.casilla_id import CasillaId
from ....core.modelo import Modelo
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
        ...


#: The cross-domain check each modelo requires, keyed by the module that owns
#: it. A modelo absent from this mapping declares no required peer-domain gate.
#:
#: This is the ONLY place a required check module is named. The snapshot
#: builder installs exactly these modules, so the set it imports and the set
#: the guard demands cannot drift apart, and moving a check module is one edit
#: that fails loudly at import rather than two edits of which one can be
#: forgotten silently.
#:
#: Keyed by :class:`Modelo` member and typed on ``str`` because the lookup axis
#: is the modelo id a snapshot carries: a ``StrEnum`` member hashes and compares
#: as its value, so declaring the member keeps the key greppable while the
#: annotation states what callers may pass.
REQUIRED_CROSS_DOMAIN_CHECK_IDENTITIES: Mapping[str, str] = MappingProxyType(
    {
        Modelo.M100: "cadrumo.domain.renta.first_slice_routing_integrity",
        Modelo.M130: "cadrumo.domain.renta.retenciones_routing_integrity",
    },
)

_CROSS_DOMAIN_SNAPSHOT_CHECKS: list[CrossDomainSnapshotCheck] = []
CROSS_DOMAIN_SNAPSHOT_CHECKS = _CROSS_DOMAIN_SNAPSHOT_CHECKS
_CROSS_DOMAIN_CHECK_IDENTITIES: dict[str, list[CrossDomainSnapshotCheck]] = {}


def register_cross_domain_snapshot_check(check: CrossDomainSnapshotCheck) -> None:
    """Register a peer-domain snapshot referential-integrity check under its owner.

    The identity a check is registered under is the canonical defining module
    that owns it, recorded here at registration rather than re-derived by a
    reader. Owning module, not function name: a check renamed in place is the
    same gate and must keep the same identity, while the module path is the
    one fact the registry already declares in
    :data:`REQUIRED_CROSS_DOMAIN_CHECK_IDENTITIES`.

    Idempotent: registering the same callable twice is a no-op so a
    peer-domain module re-imported in a fresh interpreter (or under
    test reload) does not stack duplicate checks.
    """
    if check in _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        return
    _CROSS_DOMAIN_SNAPSHOT_CHECKS.append(check)
    _CROSS_DOMAIN_CHECK_IDENTITIES.setdefault(check.__module__, []).append(check)


def registered_cross_domain_check_identities() -> frozenset[str]:
    """Return the owning module of every currently registered check."""
    return frozenset(_CROSS_DOMAIN_CHECK_IDENTITIES)


def missing_required_cross_domain_check(modelo_id: str, registered_identities: Collection[str]) -> str | None:
    """Return the required check identity ``modelo_id`` is missing, or ``None``.

    Asking whether ANY check is registered is not the question the guard
    needs to answer. A process that registered some other peer-domain check
    leaves the registration list non-empty while the gate this modelo
    actually requires is absent, and a guard reading only emptiness grants
    passage to precisely that state.
    """
    required = REQUIRED_CROSS_DOMAIN_CHECK_IDENTITIES.get(modelo_id)
    if required is None or required in registered_identities:
        return None
    return required


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

    A modelo named in :data:`REQUIRED_CROSS_DOMAIN_CHECK_IDENTITIES` has a
    known-required gate -- Modelo 100's is the renta first-slice routing
    referential-integrity check. Each check registers itself as the import
    side effect of the module that owns it, and the snapshot builder installs
    those modules before validation. Rather than skip a known-required gate,
    fail loudly so a missing registration surfaces at snapshot build instead
    of as a later runtime KeyError.

    The requirement is judged by NAME, not by population. A process that
    registered some other peer-domain check -- the M130 retenciones gate, say,
    which any importer of ``application.aggregation`` brings in -- leaves the
    registration list non-empty while the first-slice gate is absent. Reading
    only emptiness grants passage to exactly that state, which is the silent
    half of the failure this guard exists to make loud.
    """
    from .ledger_renta_gastos_estimacion_directa_bindings import renta_first_slice_binding_target_casillas

    casilla_ids = frozenset(checker.casilla_ids)
    renta_first_slice_binding_targets = renta_first_slice_binding_target_casillas(snapshot.revision)
    revision_binding_ids = frozenset(binding.id for binding in snapshot.revision.bindings)
    registered_identities = registered_cross_domain_check_identities()
    missing = missing_required_cross_domain_check(snapshot.modelo.id, registered_identities)
    if missing is not None and not _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        checker.failures.append(
            f"{checker.prefix}: modelo {snapshot.modelo.id} requires the "
            f"cross-domain snapshot check owned by {missing}, but no "
            "cross-domain checks are registered at all -- the snapshot builder "
            "installs the declared peer-domain check modules before "
            "validation, so an empty registry means that install did not run",
        )
    elif missing is not None:
        checker.failures.append(
            f"{checker.prefix}: modelo {snapshot.modelo.id} requires the "
            f"cross-domain snapshot check owned by {missing}, but the "
            "registered checks are owned by "
            f"{', '.join(sorted(registered_identities))} -- a peer-domain "
            "module that no longer registers its check reaches validation as a "
            "silently absent gate, which another domain's check does not cover",
        )
    for check in _CROSS_DOMAIN_SNAPSHOT_CHECKS:
        for failure in check(
            snapshot.modelo.id,
            casilla_ids,
            renta_first_slice_binding_targets,
            revision_binding_ids,
        ):
            checker.failures.append(f"{checker.prefix}: {failure}")
