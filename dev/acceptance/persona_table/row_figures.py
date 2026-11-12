"""The figures a return's one row per property holds, which the public calculation prints only as column totals.

A casilla of a repeated row group (a let property's rendimientos) is stored per row, not as one scalar, so
the calculation's casilla values cannot answer for it. Where the return holds exactly one row, that row's
figure is the casilla's figure; with several rows no single figure answers, so none is given and a stated
amount stays unmet instead of passing on one row.
"""

from __future__ import annotations

from collections.abc import Mapping

from cadrumo.application.modelo.work_calculation_contracts import ModeloWorkCalculatePublicResultV3
from cadrumo.domain.calculations.registry.binding_targets import casillas_by_binding
from cadrumo.entrypoints.adapter_composition_work_ports import build_calculation_action_ports
from cadrumo.entrypoints.tests.persona_materialisation import PersonaWorld


def row_figures(world: PersonaWorld, calculated: ModeloWorkCalculatePublicResultV3) -> Mapping[str, str]:
    """The stored figure of each casilla fed by a row-valued binding of the single row, by casilla id."""
    ports = build_calculation_action_ports(bucket_id=str(world.profile_id), operation=world.operation)
    stored = ports.calculation_repository.load().get(calculated.calculation_revision_id)
    if stored is None:
        return {}
    fed = casillas_by_binding(world.operation.revision(str(calculated.unit.modelo), calculated.unit.revision_id))
    figures: dict[str, str] = {}
    for binding_id, rows in stored.row_binding_values.items():
        if len(rows) != 1:
            continue
        (value,) = rows.values()
        for casilla in fed.get(binding_id, ()):
            figures[str(casilla)] = str(value)
    return figures


__all__ = ["row_figures"]
