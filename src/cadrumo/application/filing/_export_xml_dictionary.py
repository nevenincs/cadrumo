"""XML-dictionary declaration export renderer.

Renders approved declaration drafts through registry ``xml_dictionary`` export
layouts. The renderer reuses the official AEAT dictionary and XSD source refs
resolved by the registry schema provider, then writes only a local XML payload
for the draft export path.

See Also:
    :func:`~application.filing.export_draft`
        Draft export service that selects this renderer for XML dictionary
        layouts.
    :class:`~domain.filing.ModeloDraft`
        Approved declaration draft whose casilla and header values are rendered.
    :class:`~domain.calculations.registry.ExportLayoutDefinition`
        Registry export layout carrying dictionary and XSD source references.
    :class:`~domain.calculations.registry.XmlDictionaryEntry`
        Parsed dictionary row consumed while projecting XML fields.
    :func:`~domain.calculations.registry.xml_dictionary_entries`
        Registry helper that reads the official dictionary source.
    :class:`~application.filing.runtime.RegistrySchemaAccessor`
        Runtime schema provider that resolves source roots and references.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from pathlib import Path
from xml.etree import ElementTree

from defusedxml import ElementTree as DefusedElementTree

from ...core import Modelo
from ...core.decimal import coerce_decimal
from ...core.external_constants import UTF_8_ENCODING as _UTF_8
from ...core.money import round_to_cents
from ...domain.calculations.registry import (
    CasillaId,
    ExportLayoutDefinition,
    SourceReference,
    XmlDictionaryEntry,
    xml_dictionary_entries,
)
from ...domain.contribuyente import modelo100_ecivil_export_code
from ...domain.filing import FilingExportError, FilingExportValidationError, ModeloDraft
from .runtime import RegistrySchemaAccessor

_XML_SCHEMA_INSTANCE_NS = "http://www.w3.org/2001/XMLSchema-instance"
ElementTree.register_namespace("xsi", _XML_SCHEMA_INSTANCE_NS)


def render_xml_dictionary_layout(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
    schema_provider: RegistrySchemaAccessor,
) -> bytes:
    """Render an XML-dictionary layout for an approved declaration draft.

    Args:
        layout: Registry
            :class:`~domain.calculations.registry.ExportLayoutDefinition`
            whose format is ``xml_dictionary``.
        draft: Approved :class:`~domain.filing.ModeloDraft` supplying casilla
            values, modelo, and period metadata.
        headers: Normalized declaration header values such as identity fields.
        schema_provider: :class:`~application.filing.runtime.RegistrySchemaAccessor`
            that resolves dictionary and XSD source references.

    Returns:
        UTF-8 XML declaration bytes for the local export artefact.
    """
    entries = xml_dictionary_entries(layout, source_root=schema_provider.source_root, sources=schema_provider.sources)
    root = ElementTree.Element(
        _XML_DICTIONARY_ROOT_TAG,
        expected_xml_dictionary_root_identity(layout, draft=draft, schema_provider=schema_provider),
    )
    normalized_headers = {key.lower(): value for key, value in headers.items()}
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    for entry in entries:
        rendered = _xml_dictionary_rendered_value(
            entry,
            draft=draft,
            casilla_values=casilla_values,
            headers=normalized_headers,
        )
        if rendered is None or rendered == "":
            continue
        _set_xml_dictionary_path(root, entry.path, rendered)
    return ElementTree.tostring(root, encoding=_UTF_8, xml_declaration=True)


_XML_DICTIONARY_ROOT_TAG = "Declaracion"
_XSD_SCHEMA_LOCATION_ATTRIBUTE = f"{{{_XML_SCHEMA_INSTANCE_NS}}}noNamespaceSchemaLocation"


def expected_xml_dictionary_root_identity(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    schema_provider: RegistrySchemaAccessor,
) -> dict[str, str]:
    """Return the ``Declaracion`` root attributes ``draft`` identifies itself by.

    The sole declaration of the root-attribute contract. The writer builds the
    element from it and :func:`verify_export` rebuilds the same mapping to
    compare against what a file on disk actually carries, so the two halves
    cannot name different attributes — which is how the verifier came to check
    none of them at all.

    Args:
        layout: The ``xml_dictionary`` export layout being rendered or verified.
        draft: The approved draft supplying modelo and period identity.
        schema_provider: Resolves the layout's XSD source and its version.

    Returns:
        The root attributes, keyed exactly as they appear on the element.
    """
    xsd_source = _xml_dictionary_xsd_source(layout, schema_provider.sources)
    version = _latest_xml_dictionary_xsd_version(xsd_source, source_root=schema_provider.source_root)
    return {
        "modelo": draft.modelo,
        "ejercicio": str(draft.period.filing_year),
        "periodo": draft.period.registry_token,
        "versionxsd": version,
        _XSD_SCHEMA_LOCATION_ATTRIBUTE: xsd_source.source_url,
    }


def read_xml_dictionary_root_identity(payload: bytes) -> dict[str, str]:
    """Return the root identity attributes carried by an exported XML declaration.

    Args:
        payload: The exported XML declaration bytes.

    Returns:
        The declared root attributes, keyed as
        :func:`xml_dictionary_root_identity` writes them. A key is absent when
        the file omits that attribute, which the caller must treat as a
        divergence rather than as a match.

    Raises:
        FilingExportValidationError: The payload is not parseable XML, or its
            root is not a ``Declaracion`` element.
    """
    try:
        root = DefusedElementTree.fromstring(payload)
    except DefusedElementTree.ParseError as exc:
        raise FilingExportValidationError("XML dictionary payload could not be parsed") from exc
    if root.tag != _XML_DICTIONARY_ROOT_TAG:
        raise FilingExportValidationError(
            f"XML dictionary payload root is {root.tag!r}, expected {_XML_DICTIONARY_ROOT_TAG!r}",
        )
    return dict(root.attrib)


def _xml_dictionary_xsd_source(
    layout: ExportLayoutDefinition,
    sources: Mapping[str, SourceReference],
) -> SourceReference:
    refs = set(layout.source_refs)
    for source in sources.values():
        if source.id in refs and source.kind == "xsd":
            return source
    raise FilingExportError(f"XML dictionary export layout {layout.id!r} has no resolved XSD source")


def _latest_xml_dictionary_xsd_version(source: SourceReference, *, source_root: Path | None) -> str:
    if source_root is None:
        raise FilingExportError(f"XML dictionary XSD source {source.id!r} requires source_root")
    try:
        root = DefusedElementTree.parse(source_root / source.corpus_path).getroot()
    except (DefusedElementTree.ParseError, OSError) as exc:
        raise FilingExportValidationError(f"XML dictionary XSD source {source.id!r} could not be parsed") from exc
    if root is None:
        raise FilingExportValidationError(f"XML dictionary XSD source {source.id!r} could not be parsed")
    versions: list[str] = []
    for simple_type in root.iter("{http://www.w3.org/2001/XMLSchema}simpleType"):
        if simple_type.attrib.get("name") != "tipo_VersionXSD":
            continue
        for enumeration in simple_type.iter("{http://www.w3.org/2001/XMLSchema}enumeration"):
            value = enumeration.attrib.get("value")
            if value:
                versions.append(value)
    if not versions:
        raise FilingExportValidationError(f"XML dictionary XSD source {source.id!r} declares no versionxsd values")
    return sorted(versions, key=lambda item: tuple(int(part) for part in item.split(".")))[-1]


def _xml_dictionary_rendered_value(
    entry: XmlDictionaryEntry,
    *,
    draft: ModeloDraft,
    casilla_values: dict[CasillaId, object],
    headers: dict[str, str],
) -> str | None:
    raw = casilla_values.get(entry.casilla_id) if entry.casilla_id is not None else None
    if raw is None:
        raw = _xml_dictionary_header_value(entry, draft=draft, headers=headers)
    if raw is None:
        return None
    rendered = _format_xml_dictionary_value(entry.data_type, raw)
    if draft.modelo == Modelo.M100 and entry.field_id == "ECIVIL":
        try:
            return modelo100_ecivil_export_code(rendered)
        except ValueError as exc:
            raise FilingExportValidationError(str(exc)) from exc
    return rendered


def _xml_dictionary_header_value(
    entry: XmlDictionaryEntry,
    *,
    draft: ModeloDraft,
    headers: dict[str, str],
) -> object | None:
    path_tail = entry.path.rsplit("/", 1)[-1].lstrip("@").lower()
    for key in (entry.field_id.lower(), path_tail):
        value = headers.get(key)
        if value is not None:
            return value
    if entry.field_id == "DPNIF_D":
        return draft.profile_tax_id
    if entry.field_id == "DP_APENOM_D":
        return headers.get("legal_name") or " ".join(
            part for part in (headers.get("surnames", ""), headers.get("name", "")) if part
        )
    return None


def _format_xml_dictionary_value(data_type: str, value: object) -> str:
    if isinstance(value, bool):
        return "S" if value else "N"
    if isinstance(value, date):
        return f"{value.day}/{value.month}/{value.year}"
    normalized_type = data_type.upper()
    if normalized_type.startswith(("N", "P")):
        amount = coerce_decimal(value, default=Decimal("0")) or Decimal("0")
        return f"{round_to_cents(amount):.2f}"
    return str(value).strip()


def _set_xml_dictionary_path(root: ElementTree.Element[str], absolute_path: str, value: str) -> None:
    parts = tuple(part for part in absolute_path.strip("/").split("/") if part)
    if not parts:
        raise FilingExportValidationError("XML dictionary entry path must not be empty")
    current = root
    for index, part in enumerate(parts):
        if index == 0 and part == root.tag:
            continue
        if part.startswith("@"):
            if index != len(parts) - 1:
                raise FilingExportValidationError("XML dictionary attribute must terminate its path")
            current.set(part[1:], value)
            return
        child = next((candidate for candidate in current if candidate.tag == part), None)
        if child is None:
            child = ElementTree.SubElement(current, part)
        current = child
    current.text = value


__all__ = ["render_xml_dictionary_layout"]
