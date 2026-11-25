"""Resolve the dictionary rows of an XML export layout against its own edition's casillas."""

from __future__ import annotations

from ...domain.calculations.registry.errors import (
    RegistryFailureClassification,
    RegistryFailureCondition,
    RegistryValidationError,
)
from ...domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry, xml_dictionary_entries
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.calculations.registry.schema_surfaces import CasillaDefinition
from .runtime import RegistrySchemaAccessor


def xml_dictionary_layout_casillas(
    layout: ExportLayoutDefinition, *, schema_provider: RegistrySchemaAccessor
) -> tuple[CasillaDefinition, ...]:
    """Return the casillas of the one selected edition whose revision declares ``layout``.

    Args:
        layout: The ``xml_dictionary`` layout whose rows are being resolved.
        schema_provider: Holds the immutable snapshot selected for each modelo.

    Raises:
        RegistryValidationError: No selected edition declares the layout.
    """
    for snapshot in schema_provider.snapshots.values():
        if any(declared.id == layout.id for declared in snapshot.revision.export_layouts):
            return snapshot.revision.casillas
    raise RegistryValidationError(
        f"XML export layout {layout.id!r} is declared by no selected registry edition",
        registry_failure=RegistryFailureClassification(
            condition=RegistryFailureCondition.SNAPSHOT_EXPORT_LAYOUT_DECLARED,
            facts={"export_layout": str(layout.id), "export_layout_declared": False},
        ),
    )


def xml_dictionary_layout_entries(
    layout: ExportLayoutDefinition, *, schema_provider: RegistrySchemaAccessor
) -> tuple[XmlDictionaryEntry, ...]:
    """Resolve ``layout``'s dictionary rows to the casillas its own edition declares for them."""
    return xml_dictionary_entries(
        layout,
        sources=schema_provider.sources,
        source_payloads=schema_provider.source_payloads,
        casillas=xml_dictionary_layout_casillas(layout, schema_provider=schema_provider),
    )
