"""Offline registry-grounded modelo-export parity gate.

The export workbook must mirror the official AEAT casilla structure. This gate
asserts, purely offline (no Sheets / network), that the plan produced by
``build_export_plan`` for a modelo:

- covers every casilla the official completeness manifest requires (number +
  segmento) — a divergence from the official set is a hard failure (contract);
- emits a live spreadsheet formula for every computed casilla (contract).

Grounded against the registry completeness manifest (the in-repo projection of
the AEAT Diseño de Registros), which is the same authority the calculation
engine uses — never a hand-authored expectation that could drift from AEAT.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.resources import resources
from .....domain.calculations.registry import RegistrySnapshot
from .. import build_export_plan

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# (modelo, filing_year, period, on) — supported modelos whose registry formulas
# are export-capable (every formula op has a closed-form Sheets translation), so
# a live-formula workbook can be built and held to official-casilla parity.
_COVERED = [
    ("130", 2025, "1T", date(2025, 4, 1)),  # pagos fraccionados actividad
    ("303", 2025, "1T", date(2025, 4, 1)),  # IVA trimestral
    ("390", 2025, "0A", date(2026, 1, 20)),  # IVA resumen anual
    ("111", 2025, "1T", date(2025, 4, 1)),  # retenciones trabajo
    ("115", 2025, "1T", date(2025, 4, 1)),  # retenciones arrendamientos
    ("200", 2025, "0A", date(2026, 7, 1)),  # sociedades (bracket-by-entity-type translated)
    ("100", 2025, "0A", date(2025, 5, 1)),  # renta IRPF anual (age_at_year_end translated)
]


def _snapshot(modelo: str, year: int, period: str, on: date):
    return resources().modelos.authority.snapshot(modelo, filing_year=year, period=period, on=on)


def _plan_casilla_keys(snapshot: RegistrySnapshot) -> set[tuple[str, str | None]]:
    """Return the (number, segmento) key for every casilla the plan emits a cell for."""
    by_id = {c.id: c for c in snapshot.revision.casillas}
    plan = build_export_plan(snapshot)
    emitted_ids: set[str] = set()
    for cell in plan.value_cells:
        if cell.casilla is not None:
            emitted_ids.add(cell.casilla)
    for cell in plan.formula_cells:
        emitted_ids.add(cell.casilla)
    return {(by_id[cid].number, by_id[cid].segmento) for cid in emitted_ids if cid in by_id}


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_export_plan_covers_completeness_manifest(modelo: str, year: int, period: str, on: date) -> None:
    snapshot = _snapshot(modelo, year, period, on)
    manifest = snapshot.revision.completeness_manifest
    assert manifest is not None, f"modelo {modelo} has no completeness manifest to ground parity against"
    required = {(c.number, c.segmento) for c in manifest.casillas}
    emitted = _plan_casilla_keys(snapshot)
    missing = sorted(required - emitted)
    # Every official-manifest casilla must appear in the exported workbook.
    assert not missing, f"modelo {modelo} export omits official casillas: {missing}"


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_every_computed_casilla_has_a_live_formula(modelo: str, year: int, period: str, on: date) -> None:
    snapshot = _snapshot(modelo, year, period, on)
    computed_ids = {c.id for c in snapshot.revision.casillas if c.formula is not None}
    plan = build_export_plan(snapshot)
    formula_ids = {fc.casilla for fc in plan.formula_cells}
    assert computed_ids, f"modelo {modelo} declares no computed casillas"
    missing = sorted(computed_ids - formula_ids)
    # Every computed casilla must carry a live spreadsheet formula in the export.
    assert not missing, f"modelo {modelo} computed casillas without a live formula cell: {missing}"


_FORMAT_BY_REGISTRY_TYPE = {
    "money": ("money", "#,##0.00"),
    "integer": ("integer", "0"),
    "ratio": ("percentage", "0.00%"),
}


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_numeric_casillas_carry_number_format_facet(modelo: str, year: int, period: str, on: date) -> None:
    snapshot = _snapshot(modelo, year, period, on)
    plan = build_export_plan(snapshot)
    formats = {item.casilla: item for item in plan.number_formats}
    expected = {
        casilla.id: _FORMAT_BY_REGISTRY_TYPE[casilla.data_type]
        for casilla in snapshot.revision.casillas
        if casilla.data_type in _FORMAT_BY_REGISTRY_TYPE
    }

    missing = sorted(set(expected) - set(formats))
    assert not missing, f"modelo {modelo} numeric casillas without number format facet: {missing}"
    mismatched = {
        casilla_id: (formats[casilla_id].data_type, formats[casilla_id].pattern, expected_format)
        for casilla_id, expected_format in expected.items()
        if (formats[casilla_id].data_type, formats[casilla_id].pattern) != expected_format
    }
    assert not mismatched, f"modelo {modelo} numeric casilla format drift: {mismatched}"
