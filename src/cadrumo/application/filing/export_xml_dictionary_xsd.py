"""Read the declaration structure an official AEAT XML dictionary XSD declares.

The XML dictionary writer and verifier take element order, repeating and
optional elements, and the schema version from the layout's signed XSD
projection rather than from the dictionary rows.
"""

from __future__ import annotations

from collections.abc import Mapping
from xml.etree import ElementTree

from defusedxml import ElementTree as DefusedElementTree

from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.calculations.registry.schema_references import SourceReference
from ...domain.filing.errors import (
    FilingExportDesignIntegrityError,
    FilingExportIntegrityError,
)
from .export_xml_value_limits import XSD_NS, xsd_declared_children

XML_DICTIONARY_ROOT_TAG = "Declaracion"


def xml_dictionary_xsd_source(
    layout: ExportLayoutDefinition,
    sources: Mapping[str, SourceReference],
) -> SourceReference:
    """Return the XSD source reference the layout names among the resolved sources."""
    refs = set(layout.source_refs)
    for source in sources.values():
        if source.id in refs and source.kind == "xsd":
            return source
    raise FilingExportIntegrityError(
        f"XML dictionary export layout {layout.id!r} has no resolved XSD source",
        translated_message="errors.integrity.filing_export_xsd_source_unresolved",
        context={"layout": layout.id},
    )


def xml_dictionary_xsd_root(
    source: SourceReference, *, source_payloads: Mapping[str, bytes]
) -> ElementTree.Element[str]:
    """Return the parsed root from the signed XSD projection ``source`` names."""
    try:
        root = DefusedElementTree.fromstring(source_payloads[source.id])
    except (DefusedElementTree.ParseError, KeyError) as exc:
        raise FilingExportDesignIntegrityError(
            f"XML dictionary XSD source {source.id!r} could not be parsed",
            translated_message="errors.integrity.filing_export_xsd_unparseable",
            context={"source": source.id},
        ) from exc
    return root


def latest_xml_dictionary_xsd_version(source: SourceReference, *, source_payloads: Mapping[str, bytes]) -> str:
    """Return the newest ``tipo_VersionXSD`` value the XSD enumerates."""
    root = xml_dictionary_xsd_root(source, source_payloads=source_payloads)
    versions: list[str] = []
    for simple_type in root.iter(f"{XSD_NS}simpleType"):
        if simple_type.attrib.get("name") != "tipo_VersionXSD":
            continue
        for enumeration in simple_type.iter(f"{XSD_NS}enumeration"):
            value = enumeration.attrib.get("value")
            if value is not None and value:
                versions.append(value)
    if not versions:
        raise FilingExportDesignIntegrityError(
            f"XML dictionary XSD source {source.id!r} declares no versionxsd values",
            translated_message="errors.integrity.filing_export_xsd_version_absent",
            context={"source": source.id},
        )
    return sorted(versions, key=lambda item: tuple(int(part) for part in item.split(".")))[-1]


def xml_dictionary_element_order(
    source: SourceReference,
    *,
    source_payloads: Mapping[str, bytes],
) -> dict[str, tuple[str, ...]]:
    """Return each element path's declared child order, read from the official XSD.

    AEAT declares the declaration body as ``xs:sequence``, so sibling order is
    part of the schema rather than a presentation choice. The dictionary's row
    order is NOT that order -- it lists ``CalculoImpuestoRes`` first under
    ``Resultados`` where the schema puts it later, and some sibling fields before
    others under ``Declarante`` where the schema places them later.
    Appending each element as its dictionary row is reached therefore emits a
    document AEAT's own schema rejects, so the writer reads the order from the
    schema instead.

    The map is keyed by absolute path rather than by element name because a name
    is not unique across the document: the same tag recurs under different
    parents carrying different types, and a name-keyed map would silently apply
    one parent's order to another's children.

    Args:
        source: The layout's resolved XSD :class:`SourceReference`.
        source_payloads: Published authority bytes keyed by source reference.

    Returns:
        Absolute element path (``""`` for the root's own children) mapped to the
        child element names the schema declares under it, in declared order. A
        path the schema does not describe is absent, and the writer falls back to
        first-encounter order for it.

    Raises:
        FilingExportValidationError: The published XSD projection could not be parsed, or declares no
            root ``Declaracion`` element to walk from.
    """
    root = xml_dictionary_xsd_root(source, source_payloads=source_payloads)
    named_types = {name: node for node in root.iter(f"{XSD_NS}complexType") if (name := node.get("name")) is not None}
    order: dict[str, tuple[str, ...]] = {}
    declaration = next(
        (node for node in root if node.tag == f"{XSD_NS}element" and node.get("name") == XML_DICTIONARY_ROOT_TAG),
        None,
    )
    if declaration is None:
        raise FilingExportDesignIntegrityError(
            f"XML dictionary XSD source {source.id!r} declares no {XML_DICTIONARY_ROOT_TAG!r} root element",
            translated_message="errors.integrity.filing_export_xsd_root_absent",
            context={"source": source.id, "root": XML_DICTIONARY_ROOT_TAG},
        )
    _record_xsd_child_order(
        "",
        declaration.find(f"{XSD_NS}complexType"),
        named_types=named_types,
        order=order,
        seen=frozenset(),
    )
    return order


def xml_dictionary_repeating_element_paths(
    source: SourceReference, *, source_payloads: Mapping[str, bytes]
) -> Mapping[str, int | None]:
    """Return each repeating element's absolute path and the occurrences it admits; ``None`` is unbounded."""
    root = xml_dictionary_xsd_root(source, source_payloads=source_payloads)
    named_types = {
        name: node for node in root.iter(f"{XSD_NS}complexType") if ((name := node.get("name")) is not None and name)
    }
    declaration = next(
        (node for node in root if node.tag == f"{XSD_NS}element" and node.get("name") == XML_DICTIONARY_ROOT_TAG),
        None,
    )
    if declaration is None:
        raise FilingExportDesignIntegrityError(
            f"XML dictionary XSD source {source.id!r} declares no {XML_DICTIONARY_ROOT_TAG!r} root element",
            translated_message="errors.integrity.filing_export_xsd_root_absent",
            context={"source": source.id, "root": XML_DICTIONARY_ROOT_TAG},
        )
    repeating_paths: dict[str, int | None] = {}
    _record_xsd_child_order(
        "",
        declaration.find(f"{XSD_NS}complexType"),
        named_types=named_types,
        order={},
        seen=frozenset(),
        repeating_paths=repeating_paths,
    )
    return repeating_paths


def xml_dictionary_optional_element_paths(
    source: SourceReference, *, source_payloads: Mapping[str, bytes]
) -> frozenset[str]:
    """Return the absolute paths whose XSD element declaration is optional."""
    root = xml_dictionary_xsd_root(source, source_payloads=source_payloads)
    named_types = {
        name: node for node in root.iter(f"{XSD_NS}complexType") if ((name := node.get("name")) is not None and name)
    }
    declaration = next(
        (node for node in root if node.tag == f"{XSD_NS}element" and node.get("name") == XML_DICTIONARY_ROOT_TAG),
        None,
    )
    if declaration is None:
        raise FilingExportDesignIntegrityError(
            f"XML dictionary XSD source {source.id!r} declares no {XML_DICTIONARY_ROOT_TAG!r} root element",
            translated_message="errors.integrity.filing_export_xsd_root_absent",
            context={"source": source.id, "root": XML_DICTIONARY_ROOT_TAG},
        )
    optional_paths: set[str] = set()
    _record_xsd_child_order(
        "",
        declaration.find(f"{XSD_NS}complexType"),
        named_types=named_types,
        order={},
        seen=frozenset(),
        optional_paths=optional_paths,
    )
    return frozenset(optional_paths)


def _record_xsd_child_order(
    path: str,
    type_node: ElementTree.Element[str] | None,
    *,
    named_types: Mapping[str, ElementTree.Element[str]],
    order: dict[str, tuple[str, ...]],
    seen: frozenset[str],
    optional_paths: set[str] | None = None,
    repeating_paths: dict[str, int | None] | None = None,
) -> None:
    """Record ``path``'s declared child order into ``order``, then descend into each child's type.

    ``seen`` carries the named types already open on this branch, so a type that
    reaches itself terminates instead of recursing without end.
    """
    if type_node is None or path in order:
        return
    children = xsd_declared_children(type_node)
    if not children:
        return
    order[path] = tuple(str(child.get("name")) for child in children)
    for child in children:
        _record_xsd_child(
            child,
            path=path,
            named_types=named_types,
            order=order,
            seen=seen,
            optional_paths=optional_paths,
            repeating_paths=repeating_paths,
        )


def _record_xsd_child(
    child: ElementTree.Element[str],
    *,
    path: str,
    named_types: Mapping[str, ElementTree.Element[str]],
    order: dict[str, tuple[str, ...]],
    seen: frozenset[str],
    optional_paths: set[str] | None,
    repeating_paths: dict[str, int | None] | None,
) -> None:
    child_path = f"{path}/{child.get('name')}"
    if optional_paths is not None and child.get("minOccurs", "1") == "0":
        optional_paths.add(child_path)
    max_occurs = child.get("maxOccurs", "1")
    if repeating_paths is not None and max_occurs != "1":
        repeating_paths[child_path] = None if max_occurs == "unbounded" else int(max_occurs)
    declared_type = child.get("type")
    if declared_type is None or declared_type not in named_types:
        _record_xsd_child_order(
            child_path,
            child.find(f"{XSD_NS}complexType"),
            named_types=named_types,
            order=order,
            seen=seen,
            optional_paths=optional_paths,
            repeating_paths=repeating_paths,
        )
    elif declared_type not in seen:
        # A type that reaches itself would recurse without end; its
        # order is already recorded at the shallower path.
        _record_xsd_child_order(
            child_path,
            named_types[declared_type],
            named_types=named_types,
            order=order,
            seen=seen | {declared_type},
            optional_paths=optional_paths,
            repeating_paths=repeating_paths,
        )


__all__ = [
    "XML_DICTIONARY_ROOT_TAG",
    "latest_xml_dictionary_xsd_version",
    "xml_dictionary_element_order",
    "xml_dictionary_optional_element_paths",
    "xml_dictionary_repeating_element_paths",
    "xml_dictionary_xsd_root",
    "xml_dictionary_xsd_source",
]
