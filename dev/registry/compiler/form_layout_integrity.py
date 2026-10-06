"""Integrity of a revision's declared form layout against the revision it describes.

A layout is published beside its revision and read as that revision's form, so
it must describe exactly that revision: every casilla placed once, nothing
invented, repeated casillas only at declared alias positions, bindings addressed only where their
contract allows, and a source digest that still matches the revision facts the
layout was generated from. :func:`form_layout_failures` states every departure
as a failure line; the registry validator enrols it for every revision.

:func:`form_layout_source_digest` is the one definition of "the revision facts
a layout depends on". The generator writes it and the validator recomputes it,
so a revision whose casillas, bindings or export structure moved after
generation is refused as stale instead of being served a form for a different
revision.

See Also:
    :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
        The registry declaration supplying casillas, formulas, bindings and layout metadata.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterator

from cadrumo.core.aggregation import BindingSourceKind
from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from cadrumo.domain.calculations.registry.binding_targets import revision_bindings_by_id
from cadrumo.domain.calculations.registry.binding_value_contract import BindingValueChannel
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.export import derive_export_layouts_from_bindings
from cadrumo.domain.calculations.registry.form_context import resolve_form_context_field
from cadrumo.domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from cadrumo.domain.calculations.registry.schema_form_layouts import (
    FormBindingInputsBlock,
    FormBlockDefinition,
    FormCellKind,
    FormContextFieldBlock,
    FormFieldBlock,
    FormGridBlock,
    FormLayoutDefinition,
    FormPlacementDefinition,
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

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            The registry declaration supplying casillas, formulas, bindings and layout metadata.
    """
    casillas = _casilla_digest_rows(revision)
    bindings = _binding_digest_rows(revision)
    records = _export_record_digest_rows(revision)
    literal_scales = _literal_scale_digest_rows(revision)
    payload: dict[str, object] = {
        "bindings": bindings,
        "casillas": casillas,
        "records": records,
        "revision": revision.id,
    }
    if literal_scales:
        payload["literal_scales"] = literal_scales
    # Keep existing declarations' digest contract unchanged. Context-bearing
    # layouts additionally depend on the exact filing producer semantics.
    if any(
        isinstance(block, FormContextFieldBlock) for layout in revision.form_layouts for block in _layout_blocks(layout)
    ):
        payload["context_sources"] = [
            (layout.id, record.id, field.id, field.producer_key, field.draft_attribute, field.data_type)
            for layout in derive_export_layouts_from_bindings(revision)
            for record in layout.records
            for field in record.fields
        ]
    return sha256_hex(canonical_json_bytes(payload))


def _casilla_digest_rows(revision: ModeloRevision) -> list[tuple[object, ...]]:
    """Project only the casilla facts that affect layout structure."""
    return sorted(
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


def _binding_digest_rows(revision: ModeloRevision) -> list[tuple[object, ...]]:
    """Project binding identity, provider, and value-channel facts."""
    return sorted(
        (binding.id, str(binding.provider.kind), binding.value.channel.value) for binding in revision.bindings
    )


def _export_record_digest_rows(revision: ModeloRevision) -> list[tuple[object, ...]]:
    """Project derived export-record and field coordinates used by a layout."""
    return [
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


def _literal_scale_digest_rows(revision: ModeloRevision) -> list[tuple[object, ...]]:
    """Project literal decimal scales when an export literal declares one."""
    return [
        (layout.id, record.id, field.id, field.decimals)
        for layout in derive_export_layouts_from_bindings(revision)
        for record in layout.records
        for field in record.fields
        if field.literal is not None and field.decimals is not None
    ]


def _layout_blocks(layout: FormLayoutDefinition) -> Iterator[FormBlockDefinition]:
    """Yield blocks in authored page, section, and block order."""
    for page in layout.pages:
        for section in page.sections:
            yield from section.blocks


def _referenced_casillas(layout: FormLayoutDefinition) -> Iterator[str]:
    """Yield every casilla id a block addresses, once per reference."""
    for block in _layout_blocks(layout):
        yield from _block_casilla_references(block)


def _block_casilla_references(block: FormBlockDefinition) -> Iterator[str]:
    """Yield the casilla ids addressed by one authored layout block."""
    if isinstance(block, FormFieldBlock) and block.casilla_id is not None:
        yield block.casilla_id
    elif isinstance(block, FormGridBlock):
        yield from (cell.casilla_id for row in block.rows for cell in row.cells if cell.casilla_id is not None)
    elif isinstance(block, FormRepeatingGroupBlock):
        yield from (column.casilla_id for column in block.columns if column.casilla_id is not None)


def _referenced_bindings(layout: FormLayoutDefinition) -> Iterator[str]:
    """Yield every binding a block addresses as an input, once per reference."""
    for block in _layout_blocks(layout):
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
    bindings = revision_bindings_by_id(revision)
    repeating_records = {
        record.id
        for export_layout in derive_export_layouts_from_bindings(revision)
        for record in export_layout.records
        if record.repeat is not None
    }
    for block in _layout_blocks(layout):
        if not isinstance(block, FormRepeatingGroupBlock):
            continue
        failure = _repeating_block_failure(block, bindings, repeating_records)
        if failure is not None:
            yield failure


def _repeating_block_failure(
    block: FormRepeatingGroupBlock,
    bindings: dict[str, BindingDefinition],
    repeating_records: set[str],
) -> str | None:
    """Check the row-source contract for one repeating group."""
    if block.row_source is FormRepeatingRowSource.ROW_SET_BINDING:
        binding = bindings.get(str(block.binding_id))
        if binding is None:
            return f"repeating group {block.id!r} ranges over unknown binding {block.binding_id!r}"
        if binding.value.channel is not BindingValueChannel.ROW_SET:
            return f"repeating group {block.id!r} ranges over non-row-set binding {block.binding_id!r}"
        return None
    if block.export_record_id not in repeating_records:
        return (
            f"repeating group {block.id!r} ranges over {block.export_record_id!r}, "
            "which is not a repeating export record"
        )
    return None


def _placement_failures(layout: FormLayoutDefinition, revision: ModeloRevision) -> Iterator[str]:
    declared = {casilla.id for casilla in revision.casillas}
    placed = {placement.casilla_id: placement for placement in layout.placements}
    references = Counter(_referenced_casillas(layout))
    yield from _placement_domain_failures(declared, placed, references)
    yield from _placement_count_failures(layout, placed, references)


def _placement_domain_failures(
    declared: set[str],
    placed: dict[str, FormPlacementDefinition],
    references: Counter[str],
) -> Iterator[str]:
    """Report omitted, invented, or undeclared casilla placements and references."""
    for casilla_id in sorted(declared - placed.keys()):
        yield f"omits casilla {casilla_id!r}: every casilla carries exactly one placement"
    for casilla_id in sorted(placed.keys() - declared):
        yield f"places casilla {casilla_id!r}, which the revision does not declare"
    for casilla_id in sorted(references.keys() - declared):
        yield f"shows casilla {casilla_id!r}, which the revision does not declare"


def _placement_count_failures(
    layout: FormLayoutDefinition, placed: dict[str, FormPlacementDefinition], references: Counter[str]
) -> Iterator[str]:
    """Report references inconsistent with each placement's on-form status."""
    positions: dict[str, list[tuple[str, str]]] = {}
    for page in layout.pages:
        for section in page.sections:
            for block in section.blocks:
                for casilla_id in _block_casilla_references(block):
                    positions.setdefault(casilla_id, []).append((page.id, section.id))
    for casilla_id, placement in sorted(placed.items()):
        count = references.get(casilla_id, 0)
        if placement.kind is FormPlacementKind.ON_FORM and count != 1:
            locations = positions.get(casilla_id, [])
            aliases = {(alias.page_id, alias.section_id) for alias in placement.aliases}
            if (
                not locations
                or len(locations) != len(set(locations))
                or any(location not in aliases for location in locations[1:])
            ):
                yield f"shows on-form casilla {casilla_id!r} in {count} positions; it belongs in exactly one"
        if placement.kind is not FormPlacementKind.ON_FORM and count:
            yield f"shows casilla {casilla_id!r} on the form although it is placed {placement.kind.value!r}"


def _binding_failures(layout: FormLayoutDefinition, revision: ModeloRevision) -> Iterator[str]:
    bindings = revision_bindings_by_id(revision)
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


def _context_failures(layout: FormLayoutDefinition, revision: ModeloRevision) -> Iterator[str]:
    for block in _layout_blocks(layout):
        if isinstance(block, FormContextFieldBlock):
            try:
                resolve_form_context_field(revision, block)
            except RegistryValidationError as error:
                yield f"context field {block.id!r}: {error}"


def _choice_failures(layout: FormLayoutDefinition, revision: ModeloRevision) -> Iterator[str]:
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    for block in _layout_blocks(layout):
        if not isinstance(block, FormFieldBlock) or not block.choices:
            continue
        casilla = casillas.get(block.casilla_id)
        domain = casilla.constraints.enum if casilla is not None and casilla.constraints is not None else None
        if casilla is None or casilla.data_type.value != "text" or domain is None:
            yield f"choice field {block.id!r} requires a closed text casilla domain"
        elif any(choice.value not in domain for choice in block.choices):
            yield f"choice field {block.id!r} names a value outside its casilla domain"


def form_layout_failures(revision: ModeloRevision) -> tuple[str, ...]:
    """Return every way the revision's declared layout fails to describe it.

    A revision without a layout returns no failure: absence is the declared
    inspection-only arm and is reported by coverage, not refused here.

    See Also:
        :class:`~cadrumo.domain.calculations.registry.schema.ModeloRevision`
            The registry declaration supplying casillas, formulas, bindings and layout metadata.
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
    failures.extend(_context_failures(layout, revision))
    failures.extend(_choice_failures(layout, revision))
    return tuple(f"form layout {layout.id!r} {failure}" for failure in failures)
