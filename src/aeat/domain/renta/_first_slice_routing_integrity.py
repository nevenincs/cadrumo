"""Snapshot-time referential integrity for the first-slice routing table.

When the registry builds a Modelo 100 snapshot, every casilla id named
in :data:`aeat.domain.renta._first_slice_routing.FIRST_SLICE_EXPENSE_CASILLAS`
MUST be a real casilla on the revision. A divergence between the
BOE-prescribed routing and the modelo-100 registry casilla set is a
snapshot-build error, not a silent runtime ``KeyError`` when the renta
deductibility validator runs.

This check is owned by the ``renta`` domain because the routing table
is renta domain knowledge. The registry must not import ``renta``
directly -- that reverses the dependency direction the hexagonal
architecture enforces. Instead this module registers a
:class:`~aeat.domain.calculations.registry.CrossDomainSnapshotCheck`
with the registry validator via
:func:`~aeat.domain.calculations.registry.register_cross_domain_snapshot_check`.
The registration runs at ``renta`` package import time (see
:mod:`aeat.domain.renta` ``__init__``); the registry calls the check
through the abstract Protocol without naming ``renta``.
"""

from __future__ import annotations

from ...core import Modelo
from ..calculations.registry import register_cross_domain_snapshot_check
from ._first_slice_routing import first_slice_target_casillas


def check_first_slice_routing(modelo_id: str, casilla_ids: frozenset[str]) -> list[str]:
    """Assert every first-slice routing target exists on a modelo-100 snapshot.

    Returns a list of failure strings (empty when consistent). The
    registry validator prefixes each failure with the snapshot
    coordinates and raises a single ``RegistryValidationError``.
    """
    if modelo_id != Modelo.M100:
        return []
    missing = first_slice_target_casillas() - casilla_ids
    if not missing:
        return []
    return [
        f"renta first-slice routing targets casillas {sorted(missing)!r} that are absent from the modelo-100 revision",
    ]


register_cross_domain_snapshot_check(check_first_slice_routing)


__all__ = ["check_first_slice_routing"]
