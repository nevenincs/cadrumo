"""Derive repeating groups from export records, official repeating elements and row-set bindings."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cadrumo.core.aggregation import BindingAggregationOp
from cadrumo.domain.calculations.registry.binding_aggregation import binding_aggregation_op
from cadrumo.domain.calculations.registry.binding_selector_utils import selector_as_dict
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.schema_exports import (
    ExportRecordDefinition,
)
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormBlockDefinition,
    FormFieldBlock,
    FormPageDefinition,
    FormRepeatingColumn,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
)

from .column_vocabulary import shared_column_key
from .generation_models import Build, Item, Position, SectionDraft
from .heading_keys import column_form_heading_key, unique
from .official_text import description_path, node_slug


def _repeating_record(
    position: Position, repeating: Mapping[str, ExportRecordDefinition]
) -> ExportRecordDefinition | None:
    return next((repeating[record_id] for record_id in position.records if record_id in repeating), None)


def repeating_section_items(
    build: Build,
    draft: SectionDraft,
    repeating: Mapping[str, ExportRecordDefinition],
    emitted: set[str],
    blocks: list[FormBlockDefinition],
    block_ids: set[str],
) -> list[Item]:
    plain: list[Item] = []
    for item in draft.items:
        record = _repeating_record(build.positions[item.position], repeating)
        if record is None:
            plain.append(item)
            continue
        if record.id in emitted:
            continue
        emitted.add(record.id)
        block_id = unique(node_slug(record.id), block_ids)
        blocks.append(_repeating_record_block(build, record, block_id))
    return plain


def _repeating_record_block(build: Build, record: ExportRecordDefinition, block_id: str) -> FormRepeatingGroupBlock:
    columns: list[FormRepeatingColumn] = []
    used: set[str] = set()
    primary = {casilla_id: anchors[0] for casilla_id, anchors in build.anchors.items()}
    for index, position in enumerate(build.positions):
        if record.id not in position.records:
            continue
        for casilla_id in position.casilla_ids:
            if primary.get(casilla_id) != index:
                continue
            text = description_path(position.description).column
            key = unique(shared_column_key(text or "") or node_slug(text or casilla_id), used)
            columns.append(
                FormRepeatingColumn(
                    key=key,
                    heading_key=column_form_heading_key(build.modelo_id, key),
                    official_heading=text,
                    casilla_id=casilla_id,
                )
            )
    return FormRepeatingGroupBlock(
        id=block_id,
        row_source=FormRepeatingRowSource.EXPORT_RECORD,
        export_record_id=record.id,
        columns=tuple(columns),
    )


def _row_set_casillas(build: Build) -> dict[str, str]:
    """Map each casilla a row-set binding feeds to that binding."""
    channels = {binding.id: binding.value.channel for binding in build.revision.bindings}
    return {
        casilla.id: casilla.binding
        for casilla in build.revision.casillas
        if casilla.binding is not None and channels.get(casilla.binding) is BindingValueChannel.ROW_SET
    }


def _repeating_element(build: Build, position: Position) -> tuple[str, ...] | None:
    """Return the innermost official repeating element a dictionary position sits in."""
    container = position.xml_container
    if container is None:
        return None
    found: tuple[str, ...] | None = None
    for depth in range(1, len(container) + 1):
        if container[:depth] in build.repeats:
            found = container[:depth]
    return found


def _official_repeat_columns(
    build: Build, element: tuple[str, ...], row_set: Mapping[str, str], grouped: set[str]
) -> list[FormRepeatingColumn]:
    primary = {casilla_id: anchors[0] for casilla_id, anchors in build.anchors.items()}
    columns: list[FormRepeatingColumn] = []
    for index, position in enumerate(build.positions):
        if _repeating_element(build, position) != element:
            continue
        for casilla_id in position.casilla_ids:
            if casilla_id not in row_set or casilla_id in grouped or primary.get(casilla_id) != index:
                continue
            key = node_slug(f"box-{casilla_id}")
            columns.append(
                FormRepeatingColumn(
                    key=key,
                    heading_key=column_form_heading_key(build.modelo_id, key),
                    official_heading=None,
                    casilla_id=casilla_id,
                    binding_id=row_set[casilla_id],
                )
            )
    return columns


def official_repeat_items(
    build: Build,
    items: Sequence[Item],
    emitted: set[str],
    blocks: list[FormBlockDefinition],
    block_ids: set[str],
) -> list[Item]:
    """Open one repeating group per official repeating element over the row-set boxes inside it.

    The design's XSD says which elements repeat and how often; a box a row-set
    binding feeds inside such an element is one column of its rows, never a
    flat field. Boxes a per-item record already groups keep that group.
    """
    if not build.repeats:
        return list(items)
    row_set = _row_set_casillas(build)
    grouped = {casilla_id for columns in _row_column_groups(build).values() for _binding, casilla_id in columns}
    plain: list[Item] = []
    for item in items:
        element = _repeating_element(build, build.positions[item.position])
        if element is None or item.casilla_id is None or item.casilla_id not in row_set or item.casilla_id in grouped:
            plain.append(item)
            continue
        marker = "element:" + "/".join(element)
        if marker in emitted:
            continue
        emitted.add(marker)
        columns = _official_repeat_columns(build, element, row_set, grouped)
        blocks.append(
            FormRepeatingGroupBlock(
                id=unique(node_slug(f"{element[-1]}-rows"), block_ids),
                row_source=FormRepeatingRowSource.ROW_SET_BINDING,
                binding_id=columns[0].binding_id,
                max_rows=build.repeats[element],
                columns=tuple(columns),
            )
        )
    return plain


def _row_column_limit(build: Build, columns: Sequence[tuple[str, str]]) -> int | None:
    """Return the repeat limit of the one official element every column's box sits in, if any."""
    elements = {
        _repeating_element(build, build.positions[anchors[0]])
        for _binding_id, casilla_id in columns
        if (anchors := build.anchors.get(casilla_id)) is not None and len(anchors) > 0
    }
    if len(elements) != 1:
        return None
    element = next(iter(elements))
    return None if element is None else build.repeats[element]


def _row_column_groups(build: Build) -> dict[str, list[tuple[str, str]]]:
    """Group the row columns of each per-item record, as binding and box pairs in declared order."""
    groups: dict[str, list[tuple[str, str]]] = {}
    for binding in build.revision.bindings:
        selector = selector_as_dict(binding)
        record, grouping, casilla_id = (selector.get(key) for key in ("record", "grouping", "target_casilla_id"))
        if binding_aggregation_op(binding) is BindingAggregationOp.ROWS and record and grouping and casilla_id:
            groups.setdefault(str(record), []).append((binding.id, str(casilla_id)))
    return groups


def _row_column_block(build: Build, record: str, columns: list[tuple[str, str]]) -> FormRepeatingGroupBlock:
    return FormRepeatingGroupBlock(
        id=node_slug(f"{record}-rows"),
        row_source=FormRepeatingRowSource.ROW_SET_BINDING,
        binding_id=columns[0][0],
        max_rows=_row_column_limit(build, columns),
        columns=tuple(
            FormRepeatingColumn(
                key=f"box-{casilla_id}",
                heading_key=column_form_heading_key(build.modelo_id, f"box-{casilla_id}"),
                casilla_id=casilla_id,
                binding_id=binding_id,
            )
            for binding_id, casilla_id in columns
        ),
    )


def with_row_column_groups(build: Build, pages: list[FormPageDefinition]) -> list[FormPageDefinition]:
    """Open each per-item record's rows beside the box that holds their total; the box itself stays."""
    result = list(pages)
    for record, columns in _row_column_groups(build).items():
        boxes = {casilla_id for _binding_id, casilla_id in columns}
        for page_index, page in enumerate(result):
            target = next(
                (
                    index
                    for index, section in enumerate(page.sections)
                    if any(isinstance(block, FormFieldBlock) and block.casilla_id in boxes for block in section.blocks)
                ),
                None,
            )
            if target is None:
                continue
            section = page.sections[target]
            opened = section.model_copy(
                update={"blocks": (*section.blocks, _row_column_block(build, record, columns))},
            )
            result[page_index] = page.model_copy(
                update={"sections": (*page.sections[:target], opened, *page.sections[target + 1 :])},
            )
            break
    return result
