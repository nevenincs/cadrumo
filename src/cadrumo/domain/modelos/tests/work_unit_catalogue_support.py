"""Build work-unit catalogues for tests."""

from __future__ import annotations

from collections.abc import Mapping

from ..errors import ModeloValidationError
from ..work_unit import WorkUnit, WorkUnitCatalogue


def build_work_unit_catalogue(units: Mapping[str, WorkUnit] | tuple[WorkUnit, ...]) -> WorkUnitCatalogue:
    """Key ``units`` by ``work_unit_id``, refusing duplicates, and validate the catalogue."""
    if isinstance(units, tuple):
        mapping: dict[str, WorkUnit] = {}
        for unit in units:
            if unit.work_unit_id in mapping:
                raise ModeloValidationError(f"duplicate work_unit_id {unit.work_unit_id!r}")
            mapping[unit.work_unit_id] = unit
        return WorkUnitCatalogue(work_units=mapping)
    return WorkUnitCatalogue(work_units={str(k): v for k, v in units.items()})
