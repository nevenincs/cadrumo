"""Validate declared form authority and resolve its input addresses."""

from __future__ import annotations

from ....domain.calculations.registry.form_projection_fields import resolve_form_projection_fields
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_form_layouts import (
    FormBlockDefinition,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
)
from .errors import CalcSheetsEngineError
from .records import (
    SheetCellAddress,
    SheetExportMetadata,
    SheetExportPlan,
    SheetReviewMetadata,
    SheetTemplatePreviewMetadata,
    TabName,
)

_BINDING_COLUMN = 3


def form_binding_addresses[M: (SheetExportMetadata, SheetReviewMetadata, SheetTemplatePreviewMetadata)](
    plan: SheetExportPlan[M],
    registry_revision: ModeloRevision,
) -> dict[str, SheetCellAddress]:
    """Map bindings to their declared input cells.

    Takes ``registry_revision`` as a :class:`ModeloRevision`.
    """
    binding_addresses = {
        str(cell.value): SheetCellAddress.at(cell.address.tab, cell.address.row, 4)
        for cell in plan.value_cells
        if cell.address.tab is TabName.ENTRADAS
        and cell.address.column == _BINDING_COLUMN
        and cell.value in {binding.id for binding in registry_revision.bindings}
    }
    input_addresses = {
        cell.casilla_id: cell.address
        for cell in plan.value_cells
        if cell.casilla_id is not None and cell.address.tab is TabName.ENTRADAS
    }
    _manual_addresses(registry_revision, input_addresses, binding_addresses)
    return binding_addresses


def _manual_addresses(
    registry_revision: ModeloRevision,
    input_addresses: dict[str, SheetCellAddress],
    binding_addresses: dict[str, SheetCellAddress],
) -> None:
    for binding in registry_revision.bindings:
        if binding.id in binding_addresses or not isinstance(binding.provider, ManualInputProvider):
            continue
        owners = {casilla.id for casilla in registry_revision.casillas if casilla.binding == binding.id}
        if binding.provider.casilla_id is not None:
            owners.add(binding.provider.casilla_id)
        addresses = {input_addresses[key].qualified(): input_addresses[key] for key in owners if key in input_addresses}
        if len(addresses) == 1:
            binding_addresses[binding.id] = next(iter(addresses.values()))


def _grid_casillas(block: FormGridBlock) -> list[str]:
    return [
        cell.casilla_id for row in block.rows for cell in row.cells if cell.casilla_id is not None and cell.casilla_id
    ]


def _repeating_casillas(block: FormRepeatingGroupBlock, revision: ModeloRevision) -> list[str]:
    if any(column.export_field_id is not None for column in block.columns):
        resolve_form_projection_fields(revision, block)
    return [column.casilla_id for column in block.columns if column.casilla_id is not None and column.casilla_id]


def _block_casillas(block: FormBlockDefinition, revision: ModeloRevision) -> list[str]:
    if isinstance(block, FormFieldBlock):
        return [block.casilla_id] if block.casilla_id is not None else []
    if isinstance(block, FormGridBlock):
        return _grid_casillas(block)
    if isinstance(block, FormRepeatingGroupBlock):
        return _repeating_casillas(block, revision)
    return []


def _form_positions(
    layout: FormLayoutDefinition, revision: ModeloRevision
) -> tuple[list[str], dict[str, list[tuple[str, str]]]]:
    shown: list[str] = []
    positions: dict[str, list[tuple[str, str]]] = {}
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                entries = _block_casillas(block, revision)
                shown.extend(entries)
                for casilla_id in entries:
                    positions.setdefault(casilla_id, []).append((page.id, section.id))
    return shown, positions


def _bad_aliases(layout: FormLayoutDefinition, positions: dict[str, list[tuple[str, str]]]) -> bool:
    placements = {p.casilla_id: p for p in layout.placements}
    bad_alias = any(
        len(locations) != len(set(locations))
        or any(
            position not in {(a.page_id, a.section_id) for a in placements[key].aliases} for position in locations[1:]
        )
        for key, locations in positions.items()
        if key in placements
    )
    return bad_alias


def validate_form_layout(layout: FormLayoutDefinition, registry_revision: ModeloRevision) -> None:
    """Require complete and unambiguous declared form placements.

    Takes ``registry_revision`` as a :class:`ModeloRevision`.
    """
    if layout.revision_id != registry_revision.id:
        raise CalcSheetsEngineError("form layout belongs to another revision")
    expected = {c.id for c in registry_revision.casillas}
    declared = [p.casilla_id for p in layout.placements]
    if len(declared) != len(set(declared)) or set(declared) != expected:
        raise CalcSheetsEngineError("form placements must account for every revision casilla exactly once")
    shown, positions = _form_positions(layout, registry_revision)
    on_form = {p.casilla_id for p in layout.placements if p.kind is FormPlacementKind.ON_FORM}
    bad_alias = _bad_aliases(layout, positions)
    if set(shown) != on_form or bad_alias:
        raise CalcSheetsEngineError("form blocks contain missing, unknown, or duplicate casilla placements")
