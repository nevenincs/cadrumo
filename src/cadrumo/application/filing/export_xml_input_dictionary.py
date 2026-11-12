"""Admit the input-dictionary rows that a repeated record needs and the declaration dictionary lacks.

An edition's declaration dictionary leaves out some repeated detail records that
its XSD declares and its input dictionary names. A row binding that names such a
field is placed through the input dictionary, but only under four conditions read
from the official files themselves: the input dictionary declares the field, the
XSD declares its element, that element sits inside an element the XSD repeats,
and the declaration dictionary carries nothing inside that repeated element nor
at the same path. Anything else is a design fault of the registry, refused before
any value is written, so the declaration dictionary is never displaced.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from ...core.aggregation import BindingAggregationOp
from ...domain.calculations.registry.binding_aggregation import binding_aggregation_op
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.export_xml_dictionary import (
    XmlDictionaryEntry,
    xml_dictionary_entries,
    xml_input_dictionary_entries,
)
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.calculations.registry.schema_references import SourceReference
from ...domain.filing.errors import FilingExportDesignIntegrityError
from .export_xml_dictionary_xsd import (
    xml_dictionary_element_order,
    xml_dictionary_repeating_element_paths,
    xml_dictionary_xsd_source,
)
from .export_xml_row_columns import nearest_repeating_element_path

__all__ = ["admitted_input_dictionary_entries", "xml_dictionary_layout_entries"]


def _demanded_fields(bindings: Iterable[BindingDefinition], declared: tuple[XmlDictionaryEntry, ...]) -> list[str]:
    """Return the dictionary fields row bindings name that the declaration dictionary does not declare."""
    declared_fields = {entry.field_id for entry in declared}
    demanded = {
        field
        for binding in bindings
        if binding_aggregation_op(binding) is BindingAggregationOp.ROWS
        and isinstance(field := selector_as_dict(binding).get("dictionary_field"), str)
        and field not in declared_fields
    }
    return sorted(demanded)


def _refused(
    layout: ExportLayoutDefinition, entry_field: str, message_key: str, detail: str, **context: object
) -> FilingExportDesignIntegrityError:
    return FilingExportDesignIntegrityError(
        f"export layout {layout.id!r} cannot admit input-dictionary field {entry_field!r}: {detail}",
        translated_message=f"errors.integrity.{message_key}",
        context={"layout": layout.id, "field": entry_field, **context},
    )


def _xsd_declares(path: str, element_order: Mapping[str, tuple[str, ...]]) -> bool:
    """Say whether the XSD declares ``path`` as an element under its parent."""
    parent, _, name = path.rpartition("/")
    return not name.startswith("@") and name in element_order.get(parent, ())


def _require_admissible(
    layout: ExportLayoutDefinition,
    entry: XmlDictionaryEntry,
    *,
    declared: tuple[XmlDictionaryEntry, ...],
    repeating: Mapping[str, int | None],
    element_order: Mapping[str, tuple[str, ...]],
) -> None:
    if not _xsd_declares(entry.path, element_order):
        raise _refused(
            layout,
            entry.field_id,
            "filing_export_input_dictionary_outside_xsd",
            "the XSD declares no such element",
            path=entry.path,
        )
    record = nearest_repeating_element_path(entry.path, repeating)
    if record is None:
        raise _refused(
            layout,
            entry.field_id,
            "filing_export_input_dictionary_not_repeated",
            "no repeated element encloses it",
            path=entry.path,
        )
    clash = next((item for item in declared if item.path == entry.path), None) or next(
        (item for item in declared if item.path.startswith(f"{record}/")), None
    )
    if clash is not None:
        raise _refused(
            layout,
            entry.field_id,
            "filing_export_input_dictionary_path_conflict",
            f"the declaration dictionary already defines {clash.path} as {clash.field_id}",
            path=entry.path,
            declared_field=clash.field_id,
        )


def admitted_input_dictionary_entries(
    layout: ExportLayoutDefinition,
    *,
    bindings: Iterable[BindingDefinition],
    declared: tuple[XmlDictionaryEntry, ...],
    sources: Mapping[str, SourceReference],
    source_payloads: Mapping[str, bytes],
) -> tuple[XmlDictionaryEntry, ...]:
    """Return the input-dictionary rows the layout's row bindings need, each checked against the official design.

    Args:
        layout: The ``xml_dictionary`` layout being validated or rendered.
        bindings: The revision's bindings; row columns naming a dictionary field
            the declaration dictionary lacks are the only demand.
        declared: The declaration dictionary's rows for the layout.
        sources: Resolved source declarations, including the XSD and both dictionaries.
        source_payloads: Their published bytes.

    Returns:
        One row per demanded field, in field order; empty when nothing is demanded.

    Raises:
        FilingExportDesignIntegrityError: A demanded field has no input dictionary to
            come from, is not declared there, is outside the XSD or any repeated
            element, or meets a row the declaration dictionary already defines.
    """
    demanded = _demanded_fields(bindings, declared)
    if not demanded:
        return ()
    offered = {
        entry.field_id: entry
        for entry in xml_input_dictionary_entries(layout, sources=sources, source_payloads=source_payloads)
    }
    xsd = xml_dictionary_xsd_source(layout, sources)
    repeating = xml_dictionary_repeating_element_paths(xsd, source_payloads=source_payloads)
    element_order = xml_dictionary_element_order(xsd, source_payloads=source_payloads)
    admitted: list[XmlDictionaryEntry] = []
    for field in demanded:
        entry = offered.get(field)
        if entry is None:
            raise _refused(
                layout,
                field,
                "filing_export_input_dictionary_field_undeclared",
                "neither dictionary declares it",
            )
        _require_admissible(layout, entry, declared=declared, repeating=repeating, element_order=element_order)
        admitted.append(entry)
    return tuple(admitted)


def xml_dictionary_layout_entries(
    layout: ExportLayoutDefinition,
    *,
    bindings: Iterable[BindingDefinition],
    sources: Mapping[str, SourceReference],
    source_payloads: Mapping[str, bytes],
) -> tuple[tuple[XmlDictionaryEntry, ...], tuple[XmlDictionaryEntry, ...]]:
    """Return the declaration dictionary's rows and, apart, the input-dictionary rows admitted beside them.

    The writer, the verifier and the parser all read the layout through this call,
    so a file is never written through rows its own check does not read.
    """
    declared = xml_dictionary_entries(layout, sources=sources, source_payloads=source_payloads)
    admitted = admitted_input_dictionary_entries(
        layout, bindings=bindings, declared=declared, sources=sources, source_payloads=source_payloads
    )
    return declared, admitted
