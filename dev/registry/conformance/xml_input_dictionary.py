"""Registry validation of the input-dictionary rows an XML export layout admits.

The registry loader has no source payloads, so it cannot read either official
dictionary or the XSD. This check runs where the payloads are on disk: every
``xml_dictionary`` layout that names an input dictionary has the rows its
revision's row bindings demand admitted exactly as the export will admit them,
and a field outside the XSD, outside any repeated element, or meeting a path the
declaration dictionary already defines fails registry validation before any
export can reach it.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from pathlib import Path

from cadrumo.application.filing.export_xml_input_dictionary import xml_dictionary_layout_entries
from cadrumo.core.export_layout_format import ExportLayoutFormat
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.schema import BindingDefinition
from cadrumo.domain.calculations.registry.schema_exports import ExportLayoutDefinition
from cadrumo.domain.calculations.registry.schema_references import SourceReference
from cadrumo.domain.filing.errors import FilingExportDesignIntegrityError

__all__ = ["check_xml_input_dictionary_layout", "verify_xml_input_dictionary_layouts"]


def check_xml_input_dictionary_layout(
    layout: ExportLayoutDefinition,
    *,
    bindings: Iterable[BindingDefinition],
    sources: Mapping[str, SourceReference],
    source_payloads: Mapping[str, bytes],
) -> None:
    """Admit one layout's demanded input-dictionary rows, refusing the layout if any is inadmissible.

    Raises:
        RegistryValidationError: A demanded row is outside the edition's XSD, outside
            any repeated element, undeclared, or meets a declaration-dictionary path.
    """
    try:
        xml_dictionary_layout_entries(layout, bindings=bindings, sources=sources, source_payloads=source_payloads)
    except FilingExportDesignIntegrityError as error:
        raise RegistryValidationError(str(error)) from error


def _layout_payloads(
    layout: ExportLayoutDefinition, sources: Mapping[str, SourceReference], source_root: Path
) -> dict[str, bytes]:
    return {
        reference: (source_root / source.corpus_path).read_bytes()
        for reference in layout.source_refs
        if (source := sources.get(reference)) is not None
    }


def verify_xml_input_dictionary_layouts(authority: ValidatedRegistryAuthority, *, source_root: Path) -> None:
    """Check every revision's XML layout that names an input dictionary against its official payloads.

    Raises:
        RegistryValidationError: Naming every revision and layout whose admission fails.
    """
    sources = authority.catalogues.sources
    failures: list[str] = []
    for modelo in authority.modelos:
        for revision_id, revision in modelo.revisions.items():
            for layout in revision.export_layouts:
                if layout.format is not ExportLayoutFormat.XML_DICTIONARY or layout.input_dictionary_source_ref is None:
                    continue
                try:
                    check_xml_input_dictionary_layout(
                        layout,
                        bindings=revision.bindings,
                        sources=sources,
                        source_payloads=_layout_payloads(layout, sources, source_root),
                    )
                except RegistryValidationError as error:
                    failures.append(f"modelo {modelo.id} revision {revision_id}: {error}")
    if failures:
        raise RegistryValidationError("XML input-dictionary admission failed:\n - " + "\n - ".join(failures))
