"""Finite fixture authoring over real typed and atomic storage kernels."""

from __future__ import annotations

from .....domain.prorrata_register.register import ProrrataActivityRow, ProrrataRegister
from ..prorrata_register import ProrrataRegisterRepository


def upsert_activity_row(self: ProrrataRegisterRepository, row: ProrrataActivityRow) -> ProrrataRegister:
    """Atomically add or replace one row by its ``(ejercicio, activity_id)`` key."""

    def _apply(current: ProrrataRegister) -> ProrrataRegister:
        retained = tuple(

                existing
                for existing in current.activity_rows
                if (existing.ejercicio, existing.activity_id) != (row.ejercicio, row.activity_id)

        )
        return ProrrataRegister(
            entries=current.entries, sector_definitions=current.sector_definitions, activity_rows=(*retained, row)
        )

    return self._storage.mutate(_apply)
