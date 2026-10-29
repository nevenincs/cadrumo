"""Row-set layout derived from registry bindings."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from ....core.aggregation import BindingAggregationOp, BindingSourceKind
from ....core.i18n.render import tr
from ....domain.calculations.registry.binding_aggregation import binding_aggregation_op
from ....domain.calculations.registry.binding_selector_utils import BindingRowSetSelector, binding_row_set_selector
from ....domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from .records import SheetCellAddress, SheetRowSet, SheetRowSetColumn, TabName

_ACQUISITION_MIRROR_BINDING_SUFFIX: Final[str] = "-adquisicion"


def collect_row_sets(revision: ModeloRevision) -> tuple[SheetRowSet, ...]:
    """Collect row-producer bindings into per-grouping `SheetRowSet` blocks.

    Args:
        revision: The :class:`ModeloRevision` whose bindings are scanned for row-producer declarations.

    Walks `revision.bindings` for invoice / counterpart bindings with
    ``aggregation = { op = "rows" }``, groups them by ``selector.grouping``
    (typically ``operator_clave`` or ``operator_clave_period``), and lays
    them out as stacked header+data blocks in the `Detalle` tab. Each
    grouping occupies a contiguous column block; groupings stack
    vertically with a one-row gap between blocks. The pull adapter
    reads row data from `first_data_row` downwards.

    Each element in the returned tuple is a :class:`SheetRowSet`.
    """
    cohorts: dict[str, list[tuple[BindingDefinition, BindingRowSetSelector]]] = {}
    cohort_legal: dict[str, set[str]] = {}
    cohort_source: dict[str, set[str]] = {}
    public_row_bindings_by_id = _collectible_row_bindings_by_id(revision)
    for binding in revision.bindings:
        if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
            continue
        selector = binding_row_set_selector(binding)
        if selector is None:
            continue
        if _is_public_row_mirror(binding, selector, public_row_bindings_by_id):
            continue
        cohorts.setdefault(selector.grouping, []).append((binding, selector))
        cohort_legal.setdefault(selector.grouping, set()).update(binding.legal_refs)
        cohort_source.setdefault(selector.grouping, set()).update(binding.source_refs)

    row_sets: list[SheetRowSet] = []
    next_row = 1
    for grouping in sorted(cohorts):
        members = sorted(cohorts[grouping], key=lambda item: item[0].id)
        header_row = next_row
        first_data_row = next_row + 1
        columns = tuple(
            SheetRowSetColumn(
                binding=binding.id,
                header_address=SheetCellAddress.at(TabName.DETALLE, header_row, column_index),
                header_label=_row_set_column_label(binding, selector),
                legal_refs=tuple(sorted(binding.legal_refs)),
            )
            for column_index, (binding, selector) in enumerate(members, start=1)
        )
        row_sets.append(
            SheetRowSet(
                grouping=grouping,
                tab=TabName.DETALLE,
                header_row=header_row,
                first_data_row=first_data_row,
                columns=columns,
                legal_refs=tuple(sorted(cohort_legal[grouping])),
                source_refs=tuple(sorted(cohort_source[grouping])),
            ),
        )
        # Reserve 50 data rows per grouping + one blank separator. The
        # apply adapter does not protect this area; operators may extend
        # downwards if more rows are needed.
        next_row = first_data_row + 50 + 1
    return tuple(row_sets)


def _collectible_row_bindings_by_id(revision: ModeloRevision) -> dict[str, BindingDefinition]:
    return {
        binding.id: binding
        for binding in revision.bindings
        if binding.source == BindingSourceKind.COLLECTIBLE_INVOICE
        and binding_aggregation_op(binding) == BindingAggregationOp.ROWS
    }


def _is_public_row_mirror(
    binding: BindingDefinition,
    selector: BindingRowSetSelector,
    public_row_bindings_by_id: Mapping[str, BindingDefinition],
) -> bool:
    if binding.source != BindingSourceKind.PAYABLE_INVOICE:
        return False
    binding_id = binding.id
    if not binding_id.endswith(_ACQUISITION_MIRROR_BINDING_SUFFIX):
        return False
    public_binding_id = binding_id.removesuffix(_ACQUISITION_MIRROR_BINDING_SUFFIX)
    public_binding = public_row_bindings_by_id.get(public_binding_id)
    if public_binding is None:
        return False
    public_selector = binding_row_set_selector(public_binding)
    if public_selector is None:
        return False
    return selector.grouping == public_selector.grouping and selector.row_field == public_selector.row_field


def _row_set_column_label(binding: BindingDefinition, selector: BindingRowSetSelector) -> str:
    """Derive a human-readable column header for a row-set binding.

    Resolves the operator-facing label through the i18n translation
    catalogue keyed by ``selector.row_field``. Locale strings live
    under ``sheets.detalle.headers.*``. There is no runtime fallback: the
    locale gate enumerates every ``row_field`` the bundled registry declares
    and requires this key for each in every catalogue, so an unlabelled
    column fails that gate instead of reaching a workbook.
    """
    return tr(
        f"sheets.detalle.headers.{selector.row_field}",
    )
