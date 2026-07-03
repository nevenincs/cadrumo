"""The two export transports agree on the official casilla structure.

The ``modelo-export-mirrors-official-structure`` rule binds both export
transports -- the offline/online workbook (``build_export_plan``) and the
fixed-width fichero-BOE (``export_draft``) -- to the same registry authority. This
gate locks the consistency invariant between them for a shared revision: every
casilla the fichero-BOE files (its representable set) is also emitted by the
workbook plan. In other words, the ``.boe`` never files a casilla the workbook
does not compute, so a value on disk in the ``.boe`` is always grounded in the
same calculation the workbook renders.

The reverse containment does not hold and is not asserted: the workbook is the
full calculation surface and legitimately emits casillas the fichero-BOE does not
file (internal carries the official DR record omits, e.g. Modelo 130
``saldo-negativo-fin-periodo``).

Modelo 303 is covered: its 2025 módulos (régimen simplificado) advisory-support
figures use a ``keyed_bracket_table`` parameter and custom-runtime keyed-lookup
ops that have no spreadsheet translation, but they are ``internal_only`` casillas
the workbook correctly omits from the export (transitively, including the
``max`` casilla that depends on them), so ``build_export_plan`` produces a valid
303 plan and the consistency invariant holds.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....application.filing import build_runtime_schema_provider
from .....application.filing._export import boe_representable_casilla_ids
from .....core import Period
from .....core.resources import resources
from .. import build_export_plan

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# (modelo, filing_year, period, on) — fixed-width modelos whose workbook plan and
# fichero-BOE layout both build. Spanned across multiple filing years (and across
# revision boundaries) so the cross-transport invariant is locked for every year a
# revision covers, not just one. Modelo 303 in particular crosses the
# 2009-y-siguientes -> 2023-y-siguientes boundary (2022 vs 2023+), and 2023-2026 all
# resolve the 2023-y-siguientes revision whose internal-only módulos casillas the
# workbook must omit for every one of those years.
_COVERED = [
    ("130", 2024, "1T", date(2024, 4, 1)),
    ("130", 2025, "1T", date(2025, 4, 1)),
    ("111", 2024, "1T", date(2024, 4, 1)),
    ("111", 2025, "1T", date(2025, 4, 1)),
    ("115", 2024, "1T", date(2024, 4, 1)),
    ("115", 2025, "1T", date(2025, 4, 1)),
    ("303", 2022, "1T", date(2022, 4, 1)),
    ("303", 2023, "1T", date(2023, 4, 1)),
    ("303", 2024, "1T", date(2024, 4, 1)),
    ("303", 2025, "1T", date(2025, 4, 1)),
    ("303", 2026, "1T", date(2026, 4, 1)),
    ("200", 2024, "0A", date(2025, 7, 1)),
    ("200", 2025, "0A", date(2026, 7, 1)),
]


def _workbook_emitted_ids(snapshot) -> set:
    plan = build_export_plan(snapshot)
    emitted = {cell.casilla_id for cell in plan.value_cells if cell.casilla_id is not None}
    emitted.update(cell.casilla_id for cell in plan.formula_cells)
    return emitted


def _boe_representable_ids(modelo: str, year: int, period: str) -> set:
    provider = build_runtime_schema_provider(
        filing_year=year, period=Period.from_year_and_code(year, period), modelos=(modelo,)
    )
    layout = provider.get_subview(modelo).export_layouts[0]
    # Disposition-independent for this containment: a suppressed refund page only
    # ever removes casillas, so a refund header gives the maximal representable set.
    return set(boe_representable_casilla_ids(layout, headers={"declaration_type": "D"}, schema_provider=provider))


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_fichero_boe_files_no_casilla_the_workbook_does_not_compute(modelo, year, period, on) -> None:
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=year, period=period, on=on)
    workbook = _workbook_emitted_ids(snapshot)
    boe = _boe_representable_ids(modelo, year, period)

    assert boe, f"modelo {modelo} has an empty fichero-BOE representable set"
    assert workbook, f"modelo {modelo} has an empty workbook emitted set"
    orphaned = sorted(boe - workbook)
    assert not orphaned, (
        f"modelo {modelo}: fichero-BOE files casillas the workbook does not compute {orphaned} -- "
        f"the two transports diverge from the shared calculation surface"
    )


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_both_transports_cover_the_computed_manifest_casillas(modelo, year, period, on) -> None:
    # Both transports must cover every COMPUTED manifest casilla the fichero-BOE
    # can represent (the fichero-BOE via its representable set, the workbook via an
    # emitted cell), so neither drops a required calculation result the other keeps.
    snapshot = resources().modelos.authority.snapshot(modelo, filing_year=year, period=period, on=on)
    revision = snapshot.revision
    by_id = {casilla.id: casilla for casilla in revision.casillas}
    workbook = _workbook_emitted_ids(snapshot)
    boe = _boe_representable_ids(modelo, year, period)

    computed_representable = {
        mc.casilla_id
        for mc in revision.completeness_manifest.casillas
        if (cd := by_id.get(mc.casilla_id)) is not None and cd.formula is not None and mc.casilla_id in boe
    }
    assert computed_representable, f"modelo {modelo} has no computed, BOE-representable manifest casilla"
    missing_from_workbook = sorted(computed_representable - workbook)
    assert not missing_from_workbook, (
        f"modelo {modelo}: computed casillas the fichero-BOE files but the workbook omits {missing_from_workbook}"
    )
