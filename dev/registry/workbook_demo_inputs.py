"""Resolve fictional workbook inputs without reading a taxpayer profile."""

from __future__ import annotations

from decimal import Decimal

from cadrumo.application.storage.calc_sheets.records import OperatorInputs
from cadrumo.domain.calculations.registry.schema import RegistrySnapshot

from .workbook_demo_cases import DemoCase
from .workbook_demo_direct_inputs import direct_inputs
from .workbook_demo_formula_inputs import formula_inputs


def demonstration_inputs(snapshot: RegistrySnapshot, case: DemoCase) -> tuple[OperatorInputs, dict[str, Decimal]]:
    """Seed fictional figures and declared context; unselected branches remain unknown."""
    direct = direct_inputs(snapshot, case)
    return direct if direct is not None else formula_inputs(snapshot, case)
