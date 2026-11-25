"""Explicit unused rows for fictional templates, without source-evidence claims.

:class:`ModeloRevision` declares the form and its value contracts.
"""

from collections.abc import Mapping

from ....domain.calculations.record_row_membership import RecordRowMembership
from ....domain.calculations.registry.binding_provider import BindingProvider
from ....domain.calculations.registry.ids import BindingId
from ....domain.calculations.registry.manual_input_selector import ManualInputProvider
from ....domain.calculations.registry.schema import ModeloRevision
from ....domain.calculations.registry.schema_form_layouts import FormGridBlock, FormGridRow
from .errors import CalcSheetsEngineError


def fictional_unused_form_rows(
    revision: ModeloRevision, selections: Mapping[str, tuple[str, ...]]
) -> Mapping[BindingId, RecordRowMembership]:
    """Resolve explicit example assumptions against exact declared grid rows.

    No blank-cell inference or production evidence is created. Editing any
    member cell makes the spreadsheet row occupied through the shared translator.

    The ``revision`` parameter uses :class:`ModeloRevision`, which declares the form and its value contracts.
    """
    grids = _selected_grids(revision, selections)
    providers = {binding.id: binding.provider for binding in revision.bindings}
    result: dict[BindingId, RecordRowMembership] = {}
    for grid_id, keys in selections.items():
        grid = grids[grid_id]
        _collect_grid_rows(grid, keys, providers, result)
    return result


def _selected_grids(revision: ModeloRevision, selections: Mapping[str, tuple[str, ...]]) -> dict[str, FormGridBlock]:
    grids: dict[str, FormGridBlock] = {}
    blocks = (
        block
        for layout in revision.form_layouts
        for page in layout.pages
        for section in page.sections
        for block in section.blocks
    )
    for block in blocks:
        if isinstance(block, FormGridBlock) and block.id in selections:
            if block.id in grids:
                raise CalcSheetsEngineError("fictional row grid is ambiguous")
            grids[block.id] = block
    if set(selections) != set(grids):
        raise CalcSheetsEngineError("fictional row grid is not declared")
    return grids


def _collect_grid_rows(
    grid: FormGridBlock,
    keys: tuple[str, ...],
    providers: Mapping[BindingId, BindingProvider],
    result: dict[BindingId, RecordRowMembership],
) -> None:
    if len(keys) != len(set(keys)) or not set(keys).issubset(row.key for row in grid.rows):
        raise CalcSheetsEngineError("fictional row selection is duplicated or undeclared")
    for index, row in enumerate(grid.rows, start=1):
        if row.key not in keys:
            continue
        _collect_unused_row(row, index, providers, result)


def _collect_unused_row(
    row: FormGridRow,
    index: int,
    providers: Mapping[BindingId, BindingProvider],
    result: dict[BindingId, RecordRowMembership],
) -> None:
    bindings = tuple(cell.binding_id for cell in row.cells if cell.binding_id is not None)
    if len(bindings) != len(row.cells) or not bindings or len(bindings) != len(set(bindings)):
        raise CalcSheetsEngineError("fictional unused row must contain distinct binding inputs")
    records = _fixed_record_owners(bindings, providers)
    if len(records) != 1 or set(bindings).intersection(result):
        raise CalcSheetsEngineError("fictional unused rows have ambiguous record ownership")
    membership = RecordRowMembership(row_index=index, binding_ids=bindings, occupied=False)
    result.update((binding, membership) for binding in bindings)


def _fixed_record_owners(bindings: tuple[BindingId, ...], providers: Mapping[BindingId, BindingProvider]) -> set[str]:
    records: set[str] = set()
    for binding in bindings:
        provider = providers.get(binding)
        if not isinstance(provider, ManualInputProvider) or provider.record is None:
            raise CalcSheetsEngineError("fictional unused row requires fixed record bindings")
        records.add(provider.record)
    return records
