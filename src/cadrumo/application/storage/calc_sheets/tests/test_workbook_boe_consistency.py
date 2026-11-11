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

Modelo 303 is covered: its módulos (régimen simplificado) advisory-support
figures use a ``keyed_bracket_table`` parameter and custom-runtime keyed-lookup
ops that have no spreadsheet translation, but they are ``internal_only`` casillas
the workbook correctly omits from the export (transitively, including the
``max`` casilla that depends on them), so ``build_export_plan`` produces a valid
303 plan and the consistency invariant holds.
"""

from __future__ import annotations

from datetime import date

import pytest

from .....core.export_layout_format import ExportLayoutFormat
from .....core.period import Period
from .....domain.calculations.export_field_kind import CasillaFieldKind
from .....domain.calculations.registry.authority import PinnedAuthorityOperation
from .....domain.calculations.registry.schema import RegistrySnapshot
from .....domain.calculations.registry.schema_exports import ExportLayoutDefinition
from .....domain.calculations.registry.tests.authored_editions import filing_year_envelope, open_ended_revision
from ....filing.runtime import build_runtime_schema_provider
from ..engine import build_export_plan

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# (modelo, filing_year, period, on) — fixed-width modelos whose workbook plan and
# fichero-BOE layout both build. Spanned across every supported filing year (and
# across revision boundaries) so the cross-transport invariant is locked for every
# year a revision covers, not just one. Modelo 303 in particular crosses its
# authored revision boundaries, and every supported year resolves its
# law-determined revision whose internal-only módulos casillas the workbook must
# omit.
_YEARS = filing_year_envelope().years
_SOCIEDADES_FROM = open_ended_revision("200").valid_from.year
_COVERED = [
    *((modelo, year, "1T", date(year, 4, 1)) for modelo in ("130", "111", "115", "303") for year in _YEARS),
    *(("200", year, "0A", date(year + 1, 7, 1)) for year in _YEARS if year >= _SOCIEDADES_FROM),
]


def _workbook_emitted_ids(snapshot: RegistrySnapshot) -> set[str]:
    plan = build_export_plan(snapshot)
    emitted = {cell.casilla_id for cell in plan.value_cells if cell.casilla_id is not None}
    emitted.update(cell.casilla_id for cell in plan.formula_cells if cell.casilla_id is not None)
    return emitted


def _boe_representable_ids(modelo: str, year: int, period: str, *, operation: PinnedAuthorityOperation) -> set[str]:
    provider = build_runtime_schema_provider(
        filing_year=year, period=Period.from_year_and_code(year, period), modelos=(modelo,), operation=operation
    )
    layout = provider.get_subview(modelo).export_layouts[0]
    return _fixed_width_layout_casilla_slots(layout)


def _fixed_width_layout_casilla_slots(layout: ExportLayoutDefinition) -> set[str]:
    assert layout.format is ExportLayoutFormat.FIXED_WIDTH, f"expected a fixed-width BOE layout, got {layout.format!r}"
    direct_slots = {
        field.casilla_id
        for record in layout.records
        for field in record.fields
        if field.kind == CasillaFieldKind.CASILLA and field.casilla_id is not None
    }
    row_slots = {casilla_id for record in layout.records for casilla_id in record.row_field_casilla_ids.values()}
    return set(direct_slots | row_slots)


@pytest.mark.parametrize(("modelo", "year", "period", "on"), _COVERED)
def test_fichero_boe_and_workbook_share_computed_export_surface(
    operation: PinnedAuthorityOperation, modelo: str, year: int, period: str, on: date
) -> None:
    snapshot = operation.snapshot(modelo, filing_year=year, period=period, on=on)
    revision = snapshot.revision
    by_id = {casilla.id: casilla for casilla in revision.casillas}
    workbook = _workbook_emitted_ids(snapshot)
    boe = _boe_representable_ids(modelo, year, period, operation=operation)

    assert boe, f"modelo {modelo} has an empty fichero-BOE representable set"
    assert workbook, f"modelo {modelo} has an empty workbook emitted set"
    orphaned = sorted(boe - workbook)
    assert not orphaned, (
        f"modelo {modelo}: fichero-BOE files casillas the workbook does not compute {orphaned} -- "
        f"the two transports diverge from the shared calculation surface"
    )

    # Both transports must cover every COMPUTED manifest casilla the fichero-BOE
    # can represent (the fichero-BOE via its representable set, the workbook via an
    # emitted cell), so neither drops a required calculation result the other keeps.
    assert revision.completeness_manifest is not None
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
