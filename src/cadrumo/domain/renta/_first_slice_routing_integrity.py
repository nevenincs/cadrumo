"""Snapshot-time referential integrity for the first-slice routing table.

When the registry builds a Modelo 100 snapshot, every casilla id an
actual ``ledger_renta_gastos_estimacion_directa_aggregation`` binding on THAT revision
targets MUST be a real casilla on the same revision. A divergence
between a revision's own bindings and its own casilla set is a
snapshot-build error, not a silent runtime ``KeyError`` when the renta
deductibility validator runs.

This check is intentionally scoped to each revision's OWN bindings
(:func:`~cadrumo.domain.calculations.registry.renta_first_slice_binding_target_casillas`),
not the universal BOE-prescribed
:data:`cadrumo.domain.renta._first_slice_routing.FIRST_SLICE_EXPENSE_CASILLAS`
codomain spanning every filing year. Casilla ids are added, split, and
renumbered across Modelo 100 revisions -- for example "Aportaciones a
mutualidades alternativas" shares a combined casilla with Seguridad
Social contributions (id ``0186``) on the 2020-2022 revisions but gets
its own dedicated casilla (id ``0195``) from 2023 onward. Revisions
that declare no ``ledger_renta_gastos_estimacion_directa_aggregation`` bindings at all
(the ledger-aggregation mechanism did not exist for them yet) have a
legitimately empty required set; requiring the full universal codomain
on every revision would fail revisions that never route through it.

This check is owned by the ``renta`` domain because the routing table
is renta domain knowledge. The registry must not import ``renta``
directly -- that reverses the dependency direction the hexagonal
architecture enforces. Instead this module registers a
:class:`~cadrumo.domain.calculations.registry.CrossDomainSnapshotCheck`
with the registry validator via
:func:`~cadrumo.domain.calculations.registry.register_cross_domain_snapshot_check`.
The registration runs at ``renta`` package import time (see
:mod:`cadrumo.domain.renta` ``__init__``); the registry calls the check
through the abstract Protocol without naming ``renta``.
"""

from __future__ import annotations

from ...core import CasillaId, Modelo
from ..calculations.registry.validate_cross_domain_snapshot import register_cross_domain_snapshot_check


def check_first_slice_routing(
    modelo_id: str,
    casilla_ids: frozenset[CasillaId],
    renta_first_slice_binding_targets: frozenset[CasillaId],
    revision_binding_ids: frozenset[str] = frozenset(),  # shared Protocol shape, unused here
) -> list[str]:
    """Assert every casilla a revision's own first-slice bindings target exists on it.

    Returns a list of failure strings (empty when consistent). The
    registry validator prefixes each failure with the snapshot
    coordinates and raises a single ``RegistryValidationError``.
    """
    if modelo_id != Modelo.M100:
        return []
    missing = renta_first_slice_binding_targets - casilla_ids
    if not missing:
        return []
    return [
        f"renta first-slice routing targets casillas {sorted(missing)!r} that are absent from the modelo-100 revision",
    ]


register_cross_domain_snapshot_check(check_first_slice_routing)


__all__ = ["check_first_slice_routing"]
