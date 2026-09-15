"""Which catalogued official sources carry their bytes inside a published authority.

A published authority embeds the bytes of a source reference only when a runtime
workflow interprets those bytes: the XML dictionary that maps casillas to element
paths, and the XSD that fixes the declared schema version. Every other source
kind - record designs, form specifications, instructions, manuals, suppression
notices - is a citation. Its identifier, kind, digest and byte count travel in
the catalogue and into every observation, review row and explanation that cites
it, but its bytes are not part of the generation, because the fixed-width layout
already carries the compiled offsets, widths and order the design fixes.

The publisher selects the embedded set from this module, the artifact closure
check requires exactly that set, and runtime readers request bytes only for the
references this module declares embedded. A reader therefore never asks for a
payload the generation cannot hold, and a genuinely required dictionary or XSD
payload that is missing still refuses at the fetch.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Final

from ....core.export_layout_format import ExportLayoutFormat
from .errors import RegistryValidationError
from .schema_base import RegistrySourceKind
from .schema_exports import ExportLayoutDefinition
from .schema_references import SourceReference

__all__ = [
    "EMBEDDED_SOURCE_KINDS",
    "embedded_source_ids",
    "layout_embedded_source_ids",
    "source_bytes_are_embedded",
]

EMBEDDED_SOURCE_KINDS: Final[frozenset[RegistrySourceKind]] = frozenset(
    {RegistrySourceKind.DICTIONARY, RegistrySourceKind.XSD},
)
"""Source kinds whose bytes a published authority generation embeds."""


def source_bytes_are_embedded(source: SourceReference) -> bool:
    """Report whether a published generation embeds the bytes of ``source``."""
    return source.kind in EMBEDDED_SOURCE_KINDS


def embedded_source_ids(sources: Mapping[str, SourceReference]) -> frozenset[str]:
    """Return the identifiers in ``sources`` whose bytes a generation embeds."""
    return frozenset(str(source_id) for source_id, source in sources.items() if source_bytes_are_embedded(source))


def layout_embedded_source_ids(
    layouts: Iterable[ExportLayoutDefinition],
    *,
    sources: Mapping[str, SourceReference],
) -> frozenset[str]:
    """Return the embedded source identifiers a set of export layouts may read.

    Every layout source reference must resolve in ``sources``; an unresolved
    reference is a registry defect, not a citation to skip. An XML dictionary
    layout must name a dictionary source whose kind is embedded, because its
    parser cannot run without those bytes.

    Raises:
        RegistryValidationError: A layout cites a source absent from ``sources``,
            or an XML dictionary layout's dictionary source is missing or is not an
            embedded kind.
    """
    selected: set[str] = set()
    for layout in layouts:
        for source_id in layout.source_refs:
            source = sources.get(str(source_id))
            if source is None:
                raise RegistryValidationError(
                    f"export layout {layout.id!r} cites source {source_id!r} absent from the snapshot catalogue",
                )
            if source_bytes_are_embedded(source):
                selected.add(str(source_id))
        if layout.format is ExportLayoutFormat.XML_DICTIONARY:
            _require_embedded_dictionary(layout, sources=sources)
    return frozenset(selected)


def _require_embedded_dictionary(
    layout: ExportLayoutDefinition,
    *,
    sources: Mapping[str, SourceReference],
) -> None:
    dictionary_ref = layout.dictionary_source_ref
    dictionary = None if dictionary_ref is None else sources.get(str(dictionary_ref))
    if dictionary is None:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} has unresolved dictionary source {dictionary_ref!r}",
        )
    if not source_bytes_are_embedded(dictionary):
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} dictionary source {dictionary.id!r} has kind "
            f"{dictionary.kind.value!r}, whose bytes a published authority does not embed",
        )
