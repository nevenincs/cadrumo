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

from .....domain.calculations.registry.authority import bundled_authority
from .....domain.calculations.registry.schema import RegistrySnapshot
from .. import build_export_plan
from .._layout import plan_layout
from .._translator import is_translatable

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _untranslatable_internal_only_ids(snapshot: RegistrySnapshot) -> set[str]:
    """Return ``internal_only`` computed casillas with no closed-form Sheets formula.

    These are app-internal calculation-support figures the AEAT Diseño de
    Registros omits and whose formula expressions have no closed-form Sheets
    translation. The exclusion is capability-based; it does not assert any
    particular runtime operator. A *translatable* internal_only casilla (M200
    ceiling) is NOT excluded.
    """
    revision = snapshot.revision
    formulas = {formula.id: formula for formula in revision.formulas}
    layout = plan_layout(revision, bracket_filter_date=date(snapshot.filing_year, 12, 31))
    excluded: set[str] = set()
    for casilla in revision.casillas:
        if not casilla.internal_only or casilla.formula is None:
            continue
        if not is_translatable(formulas[casilla.formula].expression, layout=layout):
            excluded.add(casilla.id)
    return excluded


# (modelo, filing_year, period, on) — supported modelos whose registry formulas
# are export-capable (every formula op has a closed-form Sheets translation), so
# a live-formula workbook can be built and held to official-casilla parity.
_COVERED = [
    ("130", 2025, "1T", date(2025, 4, 1)),  # pagos fraccionados actividad
    ("303", 2023, "1T", date(2023, 4, 1)),  # IVA trimestral — 2023 epoch
    ("303", 2024, "1T", date(2024, 4, 1)),  # IVA trimestral
    ("303", 2025, "1T", date(2025, 4, 1)),  # IVA trimestral
    ("303", 2026, "1T", date(2026, 4, 1)),  # IVA trimestral
    ("390", 2025, "0A", date(2026, 1, 20)),  # IVA resumen anual
    ("111", 2025, "1T", date(2025, 4, 1)),  # retenciones trabajo
    ("115", 2025, "1T", date(2025, 4, 1)),  # retenciones arrendamientos
    ("200", 2025, "0A", date(2026, 7, 1)),  # sociedades (bracket-by-entity-type translated)
    # M100 2025 is NOT covered: formula 0197 (Art. 85 renta inmobiliaria imputada,
    # casillas 0083-0089) evaluates through the custom
    # ``m100_resolve_renta_inmobiliaria_imputada`` op, which raises registry
    # validation errors on out-of-range inputs and has no closed-form Sheets
    # equivalent — the same closed-form gap as M210's ``irnr_resolve_tipo_gravamen``
    # / ``m210_resolve_base_imponible``, neither of which is covered either.
]


def _snapshot(modelo: str, year: int, period: str, on: date):
    return bundled_authority().snapshot(modelo, filing_year=year, period=period, on=on)


_FORMAT_BY_REGISTRY_TYPE = {
    "money": ("money", "#,##0.00"),
    "integer": ("integer", "0"),
    "ratio": ("percentage", "0.00%"),
}


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_export_plan_mirrors_registry_manifest_formulas_and_formats(
    modelo: str, year: int, period: str, on: date
) -> None:
    """Assert the exported plan mirrors the official manifest, formulas and formats.

    Three properties are enforced: every manifest-required casilla is emitted
    (matched on number and segmento, not on id), every computed casilla carries a
    live formula cell rather than a baked value, and every numeric casilla carries
    a number-format facet agreeing with its registry declaration.

    Casilla SECTION ORDER is deliberately not asserted here, and that omission is
    the point of this paragraph. Section is presentation -- the plan emits section
    headers so a human can read the workbook -- while what must mirror the official
    modelo is the casilla set and its numbering, both covered above. A project rule
    previously claimed this gate enforced registry-declaration section order; it
    never has, and the claim was corrected rather than satisfied. Anyone reading
    that history should not re-add the assertion on its authority: if section order
    earns enforcement, it earns it on its own grounds.
    """
    snapshot = _snapshot(modelo, year, period, on)
    revision = snapshot.revision
    manifest = revision.completeness_manifest
    assert manifest is not None, f"modelo {modelo} has no completeness manifest to ground parity against"
    by_id = {c.id: c for c in revision.casillas}
    plan = build_export_plan(snapshot)
    emitted_ids = {cell.casilla_id for cell in plan.value_cells if cell.casilla_id is not None}
    emitted_ids.update(cell.casilla_id for cell in plan.formula_cells)

    required = {(c.number, c.segmento) for c in manifest.casillas}
    emitted = {(by_id[cid].number, by_id[cid].segmento) for cid in emitted_ids if cid in by_id}
    missing = sorted(required - emitted)
    # Every official-manifest casilla must appear in the exported workbook.
    assert not missing, f"modelo {modelo} export omits official casillas: {missing}"

    # An ``internal_only`` casilla whose formula has no closed-form Sheets
    # translation is app-internal calculation-support the AEAT Diseño de Registros
    # omits and the workbook cannot render as a live formula. The export omits it
    # by design, so the gate scopes to casillas the official-structure workbook
    # renders.
    excluded = _untranslatable_internal_only_ids(snapshot)
    computed_ids = {c.id for c in revision.casillas if c.formula is not None and c.id not in excluded}
    formula_ids = {fc.casilla_id for fc in plan.formula_cells}
    assert computed_ids, f"modelo {modelo} declares no computed casillas"
    missing_formulas = sorted(computed_ids - formula_ids)
    # Every renderable computed casilla must carry a live spreadsheet formula in the export.
    assert not missing_formulas, f"modelo {modelo} computed casillas without a live formula cell: {missing_formulas}"

    formats = {item.casilla_id: item for item in plan.number_formats}
    # Untranslatable ``internal_only`` casillas are omitted from the export
    # layout entirely (see the live-formula assertion above), so
    # they carry no cell to format; scope the expectation to casillas the
    # official-structure workbook actually renders.
    expected = {
        casilla.id: _FORMAT_BY_REGISTRY_TYPE[casilla.data_type]
        for casilla in revision.casillas
        if casilla.data_type in _FORMAT_BY_REGISTRY_TYPE and casilla.id not in excluded
    }

    missing = sorted(set(expected) - set(formats))
    assert not missing, f"modelo {modelo} numeric casillas without number format facet: {missing}"
    mismatched = {
        casilla_id: (formats[casilla_id].data_type, formats[casilla_id].pattern, expected_format)
        for casilla_id, expected_format in expected.items()
        if (formats[casilla_id].data_type, formats[casilla_id].pattern) != expected_format
    }
    assert not mismatched, f"modelo {modelo} numeric casilla format drift: {mismatched}"
