"""Derive casilla placement facts and collect identifiers carried by form blocks."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence

from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormAliasPosition,
    FormBlockDefinition,
    FormFieldBlock,
    FormGridBlock,
    FormPlacementDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
    FormUnplacedReason,
)
from cadrumo.domain.calculations.registry.schema_input_kind import InputKind
from cadrumo.domain.calculations.registry.schema_surfaces import CasillaDefinition

from .generation_models import _Build
from .position_anchoring import _casilla_box


def _block_casillas(blocks: Iterable[FormBlockDefinition]) -> set[str]:
    return {casilla_id for block in blocks for casilla_id in _casillas_in_block(block)}


def _casillas_in_block(block: FormBlockDefinition) -> set[str]:
    if isinstance(block, FormFieldBlock) and block.casilla_id is not None:
        return {block.casilla_id}
    if isinstance(block, FormGridBlock):
        return {cell.casilla_id for row in block.rows for cell in row.cells if cell.casilla_id is not None}
    if isinstance(block, FormRepeatingGroupBlock):
        return {column.casilla_id for column in block.columns if column.casilla_id is not None}
    return set()


def _block_bindings(blocks: Iterable[FormBlockDefinition]) -> set[str]:
    return {binding_id for block in blocks for binding_id in _bindings_in_block(block)}


def _bindings_in_block(block: FormBlockDefinition) -> set[str]:
    if isinstance(block, FormFieldBlock) and block.binding_id is not None:
        return {block.binding_id}
    if isinstance(block, FormGridBlock):
        return {cell.binding_id for row in block.rows for cell in row.cells if cell.binding_id is not None}
    return set()


def _on_form_placement(
    build: _Build,
    casilla_id: str,
    anchors: Sequence[int],
    box: str | None,
    section_of: Mapping[int, tuple[str, str]],
    continued_aliases: Mapping[str, tuple[FormAliasPosition, ...]],
) -> FormPlacementDefinition:
    primary_section = section_of.get(anchors[0]) if anchors else None
    aliases = tuple(
        dict.fromkeys(
            FormAliasPosition(page_id=section[0], section_id=section[1], official_ref=build.positions[index].page_ref)
            for index in anchors[1:]
            if (section := section_of.get(index)) is not None and section != primary_section
        )
    ) or continued_aliases.get(casilla_id, ())
    return FormPlacementDefinition(
        casilla_id=casilla_id,
        kind=FormPlacementKind.ON_FORM,
        box_number=box,
        aliases=aliases,
    )


def _placement_box(build: _Build, casilla: CasillaDefinition, anchors: Sequence[int]) -> str | None:
    box = _casilla_box(casilla.number, casilla.form_number)
    return build.positions[anchors[0]].box if box is None and anchors else box


def _placement_for_casilla(
    build: _Build,
    casilla: CasillaDefinition,
    section_of: Mapping[int, tuple[str, str]],
    shown: set[str],
    continued_aliases: Mapping[str, tuple[FormAliasPosition, ...]],
) -> FormPlacementDefinition:
    casilla_id = casilla.id
    anchors = build.anchors.get(casilla_id, [])
    box = _placement_box(build, casilla, anchors)
    if casilla_id in shown:
        return _on_form_placement(build, casilla_id, anchors, box, section_of, continued_aliases)
    if casilla_id in build.ambiguous:
        return FormPlacementDefinition(
            casilla_id=casilla_id,
            kind=FormPlacementKind.UNPLACED,
            unplaced_reason=FormUnplacedReason.AMBIGUOUS_ANCHOR,
            box_number=box,
        )
    if casilla.input_kind is not InputKind.MANUAL or casilla.internal_only:
        return FormPlacementDefinition(casilla_id=casilla_id, kind=FormPlacementKind.WORKING_FIGURE)
    return FormPlacementDefinition(
        casilla_id=casilla_id,
        kind=FormPlacementKind.UNPLACED,
        unplaced_reason=FormUnplacedReason.NO_OFFICIAL_ANCHOR,
    )


def _placements(
    build: _Build,
    section_of: Mapping[int, tuple[str, str]],
    shown: set[str],
    continued_aliases: Mapping[str, tuple[FormAliasPosition, ...]],
) -> tuple[FormPlacementDefinition, ...]:
    ordered = sorted(build.revision.casillas, key=lambda item: item.id)
    return tuple(_placement_for_casilla(build, casilla, section_of, shown, continued_aliases) for casilla in ordered)
