"""Integrity of a revision's declared form layout against the revision it describes.

A layout is published beside its revision and read as that revision's form, so
it must describe exactly that revision: every casilla placed once, nothing
invented, no casilla shown in two cells, bindings addressed only where their
contract allows, and a source digest that still matches the revision facts the
layout was generated from. :func:`form_layout_failures` states every departure
as a failure line; the registry validator enrols it for every revision.

:func:`form_layout_source_digest` is the one definition of "the revision facts
a layout depends on". The generator writes it and the validator recomputes it,
so a revision whose casillas, bindings or export structure moved after
generation is refused as stale instead of being served a form for a different
revision.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator

from ....core.aggregation import BindingSourceKind
from ....core.hashing import canonical_json_bytes, sha256_hex
from .binding_value_contract import BindingValueChannel
from .export import derive_export_layouts_from_bindings
from .schema import ModeloRevision
from .schema_form_layouts import (
    FormBindingInputsBlock,
    FormCellKind,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormPlacementKind,
    FormRepeatingGroupBlock,
    FormRepeatingRowSource,
)

__all__ = ["form_layout_failures", "form_layout_source_digest"]


def form_layout_source_digest(revision: ModeloRevision) -> str:
    """Return the digest of the revision facts a generated layout depends on.

    The projection is structural: casilla identity, number, section, input
    kind and binding; binding identity, provider kind and value channel; and
    the derived export records with their field coordinates. Labels, help and
    legal grounding are deliberately outside it, because a layout neither
    reads nor restates them.
    """
    casillas = sorted(
        (
            casilla.id,
            casilla.number,
            casilla.segmento,
            list(casilla.section),
            casilla.input_kind.value,
            casilla.internal_only,
            casilla.binding,
        )
        for casilla in revision.casillas
    )
    bindings = sorted(
        (binding.id, str(binding.provider.kind), binding.value.channel.value) for binding in revision.bindings
    )
    records = [
        (
            layout.id,
            record.id,
            record.order,
            record.required,
            None if record.repeat is None else record.repeat.value,
            record.requires_positive_casilla_id,
            [
                (field.id, field.offset, field.length, str(field.kind), field.casilla_id, field.binding, field.literal)
                for field in record.fields
            ],
        )
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
    ]
    payload = {"bindings": bindings, "casillas": casillas, "records": records, "revision": revision.id}
    return sha256_hex(canonical_json_bytes(payload))


def _referenced_casillas(layout: FormLayoutDefinition) -> Iterator[str]:
    """Yield every casilla id a block addresses, once per reference."""
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                if isinstance(block, FormFieldBlock) and block.casilla_id is not None:
                    yield block.casilla_id
                elif isinstance(block, FormGridBlock):
                    yield from (
                        cell.casilla_id for row in block.rows for cell in row.cells if cell.casilla_id is not None
                    )
                elif isinstance(block, FormRepeatingGroupBlock):
                    yield from (column.casilla_id for column in block.columns if column.casilla_id is not None)


def _referenced_bindings(layout: FormLayoutDefinition) -> Iterator[str]:
    """Yield every binding a block addresses as an input, once per reference."""
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                if isinstance(block, FormFieldBlock) and block.binding_id is not None:
                    yield block.binding_id
                elif isinstance(block, FormGridBlock):
                    yield from (
                        cell.binding_id
                        for row in block.rows
                        for cell in row.cells
                        if cell.kind is FormCellKind.BINDING_INPUT and cell.binding_id is not None
                    )
                elif isinstance(block, FormBindingInputsBlock):
                    yield from block.binding_ids


def _repeating_failures(layout: FormLayoutDefinition, revision: ModeloRevision) -> Iterator[str]:
    bindings = {binding.id: binding for binding in revision.bindings}
    repeating_records = {
        record.id
        for export_layout in derive_export_layouts_from_bindings(revision)
        for record in export_layout.records
        if record.repeat is not None
    }
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                if not isinstance(block, FormRepeatingGroupBlock):
                    continue
                if block.row_source is FormRepeatingRowSource.ROW_SET_BINDING:
                    binding = bindings.get(str(block.binding_id))
                    if binding is None:
                        yield f"repeating group {block.id!r} ranges over unknown binding {block.binding_id!r}"
                    elif binding.value.channel is not BindingValueChannel.ROW_SET:
                        yield f"repeating group {block.id!r} ranges over non-row-set binding {block.binding_id!r}"
                elif block.export_record_id not in repeating_records:
                    yield (
                        f"repeating group {block.id!r} ranges over {block.export_record_id!r}, "
                        "which is not a repeating export record"
                    )


def _placement_failures(layout: FormLayoutDefinition, revision: ModeloRevision) -> Iterator[str]:
    declared = {casilla.id for casilla in revision.casillas}
    placed = {placement.casilla_id: placement for placement in layout.placements}
    for casilla_id in sorted(declared - placed.keys()):
        yield f"omits casilla {casilla_id!r}: every casilla carries exactly one placement"
    for casilla_id in sorted(placed.keys() - declared):
        yield f"places casilla {casilla_id!r}, which the revision does not declare"
    references = Counter(_referenced_casillas(layout))
    for casilla_id in sorted(references.keys() - declared):
        yield f"shows casilla {casilla_id!r}, which the revision does not declare"
    for casilla_id, placement in sorted(placed.items()):
        count = references.get(casilla_id, 0)
        if placement.kind is FormPlacementKind.ON_FORM and count != 1:
            yield f"shows on-form casilla {casilla_id!r} in {count} positions; it belongs in exactly one"
        if placement.kind is not FormPlacementKind.ON_FORM and count:
            yield f"shows casilla {casilla_id!r} on the form although it is placed {placement.kind.value!r}"


def _binding_failures(layout: FormLayoutDefinition, revision: ModeloRevision) -> Iterator[str]:
    bindings = {binding.id: binding for binding in revision.bindings}
    references = Counter(_referenced_bindings(layout))
    for binding_id, count in sorted(references.items()):
        binding = bindings.get(binding_id)
        if binding is None:
            yield f"shows binding {binding_id!r}, which the revision does not declare"
            continue
        if count > 1:
            yield f"shows binding input {binding_id!r} in {count} positions; it belongs in exactly one"
        if binding.provider.kind != BindingSourceKind.MANUAL_INPUT:
            yield f"offers binding {binding_id!r} as an input, but its provider is {binding.provider.kind!s}"


def _page_failures(layout: FormLayoutDefinition, revision: ModeloRevision) -> Iterator[str]:
    declared = {casilla.id for casilla in revision.casillas}
    for page in layout.pages:
        if page.condition_casilla_id is not None and page.condition_casilla_id not in declared:
            yield f"page {page.id!r} is conditioned on undeclared casilla {page.condition_casilla_id!r}"


def form_layout_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return every way the revision's declared layout fails to describe it.

    A revision without a layout returns no failure: absence is the declared
    inspection-only arm and is reported by coverage, not refused here.
    """
    match revision.form_layouts:
        case ():
            return ()
        case (layout,):
            pass
        case layouts:
            return (f"declares {len(layouts)} form layouts; a revision has at most one",)
    failures: list[str] = []
    if layout.revision_id != revision.id:
        failures.append(f"form layout describes revision {layout.revision_id!r}, not {revision.id!r}")
    if layout.source_state_digest != form_layout_source_digest(revision):
        failures.append(
            "form layout is stale: its source_state_digest no longer matches the revision; regenerate it",
        )
    failures.extend(_placement_failures(layout, revision))
    failures.extend(_binding_failures(layout, revision))
    failures.extend(_repeating_failures(layout, revision))
    failures.extend(_page_failures(layout, revision))
    return tuple(f"form layout {layout.id!r} {failure}" for failure in failures)
