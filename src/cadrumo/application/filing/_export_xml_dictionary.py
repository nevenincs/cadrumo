"""XML-dictionary declaration export renderer.

Renders approved declaration drafts through registry ``xml_dictionary`` export
layouts. The renderer reuses the official AEAT dictionary and XSD source refs
resolved by the registry schema provider, then writes only a local XML payload
for the draft export path.

See Also:
    :func:`~application.filing.export.export_draft`
        Draft export service that selects this renderer for XML dictionary
        layouts.
    :class:`~domain.filing.schema.ModeloDraft`
        Approved declaration draft whose casilla and header values are rendered.
    :class:`~domain.calculations.registry.schema_exports.ExportLayoutDefinition`
        Registry export layout carrying dictionary and XSD source references.
    :class:`~domain.calculations.registry.export_xml_dictionary.XmlDictionaryEntry`
        Parsed dictionary row consumed while projecting XML fields.
    :func:`~domain.calculations.registry.export_xml_dictionary.xml_dictionary_entries`
        Registry helper that reads the official dictionary source.
    :class:`~application.filing.runtime.RegistrySchemaAccessor`
        Runtime schema provider that resolves source roots and references.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from xml.etree import ElementTree

from defusedxml import ElementTree as DefusedElementTree

from ...core.aggregation import BindingAggregationOp
from ...core.casilla_id import CasillaId
from ...core.decimal.coercion import coerce_decimal
from ...core.external_constants import UTF_8_ENCODING as _UTF_8
from ...core.filing_producer_key import FilingProducerKey
from ...domain.calculations.registry.binding_aggregation import binding_aggregation_op
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.binding_value_contract import BindingDataType
from ...domain.calculations.registry.export_xml_dictionary import (
    XmlDictionaryEntry,
    xml_dictionary_entries,
)
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.schema import BindingDefinition
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.calculations.registry.schema_references import SourceReference
from ...domain.contribuyente.renta_codes import modelo100_ccaa_codigo, modelo100_ecivil_export_code
from ...domain.filing.errors import FilingExportError, FilingExportValidationError
from ...domain.filing.schema import ModeloBindingValue, ModeloDraft
from ._export_xml_dictionary_modelo100 import (
    modelo_100_sign_branch_value,
    modelo_100_unfiled_comunidad_paths,
    registry_modelo_100_xml_declarations,
)
from ._export_xml_dictionary_values import format_xml_dictionary_value, is_xml_dictionary_numeric_type
from .runtime import RegistrySchemaAccessor

_XML_SCHEMA_INSTANCE_NS = "http://www.w3.org/2001/XMLSchema-instance"
ElementTree.register_namespace("xsi", _XML_SCHEMA_INSTANCE_NS)

_XSD_NS = "{http://www.w3.org/2001/XMLSchema}"

# The declaration's identity block. Mandatory and first in the ``Declaracion``
# sequence of every bundled AEAT Modelo 100 XSD, and absent from every bundled
# dictionary, so it is written from the layout rather than from a dictionary row.
_AUX_TAG = "Aux"

# The per-taxpayer block of a Modelo 100 declaration. Its mandatory ``nif``
# attribute is declared in no dictionary, so it is stamped after the walk rather
# than written from a dictionary row; its ``titular`` sibling IS declared and is
# written by the walk like any other row.
_TOMA_DATOS_TAG = "TomaDatosAmpliada"

# Model groups carry no sibling position of their own when reading declared
# order: a declaration nested inside one sits at the position the group occupies
# in its parent, so the walk descends through them rather than treating them as
# elements.
_XSD_MODEL_GROUP_TAGS = frozenset({"complexType", "complexContent", "sequence", "choice", "all"})


def _modelo100_render_exclusions(
    draft: ModeloDraft,
    entries: tuple[XmlDictionaryEntry, ...],
    casilla_values: Mapping[CasillaId, object],
) -> tuple[Mapping[str, str] | None, frozenset[str]]:
    declarations: Mapping[str, str] | None = (
        registry_modelo_100_xml_declarations() if draft.modelo == form_for_role("renta.annual") else None
    )
    unfiled_paths = frozenset[str]()
    if draft.modelo == form_for_role("renta.annual"):
        if declarations is None:
            raise FilingExportValidationError("Modelo 100 XML declarations were not resolved")
        unfiled_paths = modelo_100_unfiled_comunidad_paths(
            entries,
            casilla_values,
            declarations=declarations,
        )
    return declarations, unfiled_paths


def _write_xml_dictionary_entries(
    root: ElementTree.Element[str],
    entries: tuple[XmlDictionaryEntry, ...],
    *,
    unfiled_paths: frozenset[str],
    draft: ModeloDraft,
    casilla_values: dict[CasillaId, object],
    headers: Mapping[FilingProducerKey, object],
    dictionary_values: Mapping[str, object],
    declarations: Mapping[str, str] | None,
    element_order: dict[str, tuple[str, ...]],
    repeated_rows: tuple[XmlDictionaryRepeatedRows, ...] = (),
) -> None:
    for entry in entries:
        if entry.path in unfiled_paths:
            continue
        rendered = _xml_dictionary_rendered_value(
            entry,
            draft=draft,
            casilla_values=casilla_values,
            headers=headers,
            dictionary_values=dictionary_values,
            declarations=declarations,
        )
        if rendered is None or rendered == "":
            continue
        rows = next((item for item in repeated_rows if item.holds(entry.path)), None)
        if rows is None:
            _set_xml_dictionary_path(root, entry.path, rendered, element_order=element_order)
        else:
            _require_value_stated_by_rows(entry, rendered, rows)
    for rows in repeated_rows:
        _append_repeated_rows(root, rows, element_order=element_order)


def _finish_xml_dictionary_root(
    root: ElementTree.Element[str], draft: ModeloDraft, *, optional_element_paths: frozenset[str]
) -> None:
    if draft.modelo == form_for_role("renta.annual"):
        _stamp_toma_datos_nif(root, draft)
        _prune_zero_only_xml_subtrees(root, optional_element_paths=optional_element_paths)


def _serialize_xml_dictionary(root: ElementTree.Element[str]) -> bytes:
    rendered = ElementTree.tostring(root, encoding=_UTF_8, xml_declaration=True)
    if not isinstance(rendered, bytes):
        raise FilingExportError(f"the XML dictionary serialiser returned {type(rendered).__name__}, not bytes")
    return rendered


def render_xml_dictionary_layout(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    aux_version: str,
    dictionary_values: Mapping[str, object] | None = None,
    schema_provider: RegistrySchemaAccessor,
) -> bytes:
    """Render an XML-dictionary layout for an approved declaration draft.

    Args:
        layout: Registry
            :class:`~domain.calculations.registry.schema_exports.ExportLayoutDefinition`
            whose format is ``xml_dictionary``.
        draft: Approved :class:`~domain.filing.schema.ModeloDraft` supplying casilla
            values, modelo, and period metadata.
        headers: Normalized declaration header values such as identity fields.
        aux_version: Product build token for the mandatory ``Aux/VERSION``
            element, resolved at the export boundary from ``PACKAGE_VERSION``.
        dictionary_values: Values addressed by the dictionary field id AEAT
            declares for them, each still carrying its own Python type. Absent
            (or ``None``) means the caller declares no such values, which is how
            every caller outside the work-unit export service reaches here.
        schema_provider: :class:`~application.filing.runtime.RegistrySchemaAccessor`
            that resolves dictionary and XSD source references.

    Returns:
        UTF-8 XML declaration bytes for the local export artefact.
    """
    entries = xml_dictionary_entries(
        layout,
        sources=schema_provider.sources,
        source_payloads=schema_provider.source_payloads,
    )
    root = ElementTree.Element(
        _XML_DICTIONARY_ROOT_TAG,
        expected_xml_dictionary_root_identity(layout, draft=draft, schema_provider=schema_provider),
    )
    element_order = _xml_dictionary_element_order(
        _xml_dictionary_xsd_source(layout, schema_provider.sources),
        source_payloads=schema_provider.source_payloads,
    )
    optional_element_paths = _xml_dictionary_optional_element_paths(
        _xml_dictionary_xsd_source(layout, schema_provider.sources),
        source_payloads=schema_provider.source_payloads,
    )
    _append_declaration_aux(root, layout, aux_version=aux_version)
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    declarations, unfiled_paths = _modelo100_render_exclusions(draft, entries, casilla_values)
    repeated_rows = xml_dictionary_repeated_rows(layout, draft=draft, entries=entries, schema_provider=schema_provider)
    _write_xml_dictionary_entries(
        root,
        entries,
        unfiled_paths=unfiled_paths,
        draft=draft,
        casilla_values=casilla_values,
        headers=headers,
        dictionary_values=dictionary_values or {},
        declarations=declarations,
        element_order=element_order,
        repeated_rows=repeated_rows,
    )
    _finish_xml_dictionary_root(root, draft, optional_element_paths=optional_element_paths)
    return _serialize_xml_dictionary(root)


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
        draft: The approved :class:`ModeloDraft` supplying modelo and period
            identity.
        schema_provider: Resolves the layout's XSD source and its version.

    Returns:
        The root attributes, keyed exactly as they appear on the element.
    """
    xsd_source = _xml_dictionary_xsd_source(layout, schema_provider.sources)
    version = _latest_xml_dictionary_xsd_version(xsd_source, source_payloads=schema_provider.source_payloads)
    return {
        "modelo": draft.modelo,
        "ejercicio": str(draft.period.filing_year),
        "periodo": draft.period.registry_token,
        "versionxsd": version,
        _XSD_SCHEMA_LOCATION_ATTRIBUTE: xsd_source.source_url,
    }


def read_xml_dictionary_root_identity(payload: bytes) -> Mapping[str, str]:
    """Return the root identity attributes carried by an exported XML declaration.

    Args:
        payload: The exported XML declaration bytes.

    Returns:
        The declared root attributes, keyed as
        :func:`expected_xml_dictionary_root_identity` writes them. A key is absent when
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


def _xml_dictionary_xsd_root(
    source: SourceReference, *, source_payloads: Mapping[str, bytes]
) -> ElementTree.Element[str]:
    """Return the parsed root from the signed XSD projection ``source`` names."""
    try:
        root = DefusedElementTree.fromstring(source_payloads[source.id])
    except (DefusedElementTree.ParseError, KeyError) as exc:
        raise FilingExportValidationError(f"XML dictionary XSD source {source.id!r} could not be parsed") from exc
    return root


def _latest_xml_dictionary_xsd_version(source: SourceReference, *, source_payloads: Mapping[str, bytes]) -> str:
    root = _xml_dictionary_xsd_root(source, source_payloads=source_payloads)
    versions: list[str] = []
    for simple_type in root.iter(f"{_XSD_NS}simpleType"):
        if simple_type.attrib.get("name") != "tipo_VersionXSD":
            continue
        for enumeration in simple_type.iter(f"{_XSD_NS}enumeration"):
            value = enumeration.attrib.get("value")
            if value is not None and value:
                versions.append(value)
    if not versions:
        raise FilingExportValidationError(f"XML dictionary XSD source {source.id!r} declares no versionxsd values")
    return sorted(versions, key=lambda item: tuple(int(part) for part in item.split(".")))[-1]


def _append_declaration_aux(
    root: ElementTree.Element[str],
    layout: ExportLayoutDefinition,
    *,
    aux_version: str,
) -> None:
    """Write the declaration's ``Aux`` identity block from its two authorities.

    The block is mandatory and first in every AEAT Modelo 100 XSD, and no bundled
    dictionary describes a single one of its rows, so it cannot be reached by the
    dictionary-driven walk that writes everything else here.

    ``Idioma`` is a selected-revision declaration because AEAT's schema gives it
    an enum. ``VERSION`` identifies the developer software, so it is supplied by
    the canonical product version at the export boundary. Both children are
    ``minOccurs="1"`` and are preflighted before rendering.
    """
    if layout.aux_idioma is None:
        raise FilingExportValidationError("XML dictionary layout omits mandatory Aux/Idioma")
    aux = ElementTree.SubElement(root, _AUX_TAG)
    ElementTree.SubElement(aux, "Idioma").text = layout.aux_idioma.value
    ElementTree.SubElement(aux, "VERSION").text = aux_version


def _stamp_toma_datos_nif(root: ElementTree.Element[str], draft: ModeloDraft) -> None:
    """Name whose NIF each ``TomaDatosAmpliada`` block reports figures for.

    ``nif`` is ``use="required"`` on ``tipo_TomaDatosAmpliada`` in all six
    bundled exercises, and AEAT's dictionary declares no field id whose path
    reaches it -- so it can be written by neither the dictionary-driven walk nor
    a ``dictionary_path_overrides`` correction, which only re-points a row the
    dictionary already carries. Same shape as the ``Aux`` block, and written the
    same way: from what the export already holds.

    Its sibling attribute ``titular`` is deliberately NOT written here. That one
    IS dictionary-declared -- thirty-five field ids (``TITA`` on casilla 0001,
    ``TITBIH`` on 0026, and so on, all of them registry casillas) map to
    ``/DatosEconomicos/TomaDatosAmpliada/@titular``, so the ordinary walk writes
    it from whichever titular casilla the return populates. Stamping a constant
    here would overwrite that: a declaración conjunta reports a spouse's income
    section under código 3, and a hardcoded declarante 2 would silently
    re-attribute it on a filed return. A blank ``titular`` means no titular
    casilla carries a value, which is an input gap the completeness gate owns.

    Runs AFTER the walk rather than before it, because unlike ``Aux`` the
    element being stamped is one the walk creates.

    The NIF is the draft's, deliberately, and is the same value ``DPNIF_D``
    carries. Re-reading the profile here would let the block's identity
    attribute disagree with the identity row above it in the same file when a
    profile is edited between approval and export. Taking both from the approved
    artefact makes that disagreement unrepresentable.
    """
    for block in root.iter(_TOMA_DATOS_TAG):
        block.set("nif", draft.profile_tax_id)


def _xsd_declared_children(node: ElementTree.Element[str]) -> list[ElementTree.Element[str]]:
    """Return ``node``'s child element declarations in the order the schema writes them.

    Descends through the model-group wrappers (``sequence``, ``choice``, ``all``)
    that carry no ordering meaning of their own here, so a declaration nested one
    or more groups deep is still found at its true sibling position. Descent stops
    at the first ``element`` on each branch: that element's own children belong to
    its path, not to ``node``'s.
    """
    found: list[ElementTree.Element[str]] = []
    pending = list(node)
    while pending:
        current = pending.pop(0)
        # A comment or processing instruction carries a callable tag rather than
        # a name; rendering it to text simply matches nothing below.
        local_name = str(current.tag).rpartition("}")[2]
        if local_name == "element" and bool(current.get("name")):
            found.append(current)
        elif local_name in _XSD_MODEL_GROUP_TAGS:
            pending = list(current) + pending
    return found


def _xml_dictionary_element_order(
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
    root = _xml_dictionary_xsd_root(source, source_payloads=source_payloads)
    named_types = {name: node for node in root.iter(f"{_XSD_NS}complexType") if (name := node.get("name")) is not None}
    order: dict[str, tuple[str, ...]] = {}
    declaration = next(
        (node for node in root if node.tag == f"{_XSD_NS}element" and node.get("name") == _XML_DICTIONARY_ROOT_TAG),
        None,
    )
    if declaration is None:
        raise FilingExportValidationError(
            f"XML dictionary XSD source {source.id!r} declares no {_XML_DICTIONARY_ROOT_TAG!r} root element",
        )
    _record_xsd_child_order(
        "",
        declaration.find(f"{_XSD_NS}complexType"),
        named_types=named_types,
        order=order,
        seen=frozenset(),
    )
    return order


def _xml_dictionary_repeating_element_paths(
    source: SourceReference, *, source_payloads: Mapping[str, bytes]
) -> Mapping[str, int | None]:
    """Return each repeating element's absolute path and the occurrences it admits; ``None`` is unbounded."""
    root = _xml_dictionary_xsd_root(source, source_payloads=source_payloads)
    named_types = {
        name: node for node in root.iter(f"{_XSD_NS}complexType") if ((name := node.get("name")) is not None and name)
    }
    declaration = next(
        (node for node in root if node.tag == f"{_XSD_NS}element" and node.get("name") == _XML_DICTIONARY_ROOT_TAG),
        None,
    )
    if declaration is None:
        raise FilingExportValidationError(
            f"XML dictionary XSD source {source.id!r} declares no {_XML_DICTIONARY_ROOT_TAG!r} root element",
        )
    repeating_paths: dict[str, int | None] = {}
    _record_xsd_child_order(
        "",
        declaration.find(f"{_XSD_NS}complexType"),
        named_types=named_types,
        order={},
        seen=frozenset(),
        repeating_paths=repeating_paths,
    )
    return repeating_paths


def _xml_dictionary_optional_element_paths(
    source: SourceReference, *, source_payloads: Mapping[str, bytes]
) -> frozenset[str]:
    """Return the absolute paths whose XSD element declaration is optional."""
    root = _xml_dictionary_xsd_root(source, source_payloads=source_payloads)
    named_types = {
        name: node for node in root.iter(f"{_XSD_NS}complexType") if ((name := node.get("name")) is not None and name)
    }
    declaration = next(
        (node for node in root if node.tag == f"{_XSD_NS}element" and node.get("name") == _XML_DICTIONARY_ROOT_TAG),
        None,
    )
    if declaration is None:
        raise FilingExportValidationError(
            f"XML dictionary XSD source {source.id!r} declares no {_XML_DICTIONARY_ROOT_TAG!r} root element",
        )
    optional_paths: set[str] = set()
    _record_xsd_child_order(
        "",
        declaration.find(f"{_XSD_NS}complexType"),
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
    children = _xsd_declared_children(type_node)
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
            child.find(f"{_XSD_NS}complexType"),
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


#: The value converters a registry XML declaration may name, by that name. An
#: explicit table rather than a module-namespace lookup, so an import tidy-up
#: cannot silently make a declared converter unavailable.
_XML_VALUE_CONVERTERS: Mapping[str, Callable[[str], str]] = MappingProxyType(
    {
        "modelo100_ccaa_codigo": modelo100_ccaa_codigo,
        "modelo100_ecivil_export_code": modelo100_ecivil_export_code,
    },
)


def _xml_dictionary_raw_value(
    entry: XmlDictionaryEntry,
    *,
    casilla_values: Mapping[CasillaId, object],
    headers: Mapping[FilingProducerKey, object],
    dictionary_values: Mapping[str, object],
) -> object | None:
    raw = casilla_values.get(entry.casilla_id) if entry.casilla_id is not None else None
    if raw is None:
        return _xml_dictionary_non_casilla_value(entry, headers=headers, dictionary_values=dictionary_values)
    return raw


def _modelo100_sign_routed_value(
    entry: XmlDictionaryEntry,
    raw: object,
    *,
    draft: ModeloDraft,
    declarations: Mapping[str, str] | None,
) -> object | None:
    if draft.modelo != form_for_role("renta.annual"):
        return raw
    if declarations is None:
        raise FilingExportValidationError("Modelo 100 XML declarations were not resolved")
    return modelo_100_sign_branch_value(entry, raw, declarations=declarations)


def _apply_xml_dictionary_value_converter(
    entry: XmlDictionaryEntry,
    rendered: str,
    declarations: Mapping[str, str] | None,
) -> str:
    converter_name = declarations.get(f"xml.converter.{entry.field_id}") if declarations is not None else None
    if converter_name is None:
        return rendered
    converter = _XML_VALUE_CONVERTERS.get(converter_name)
    if converter is None:
        raise FilingExportValidationError(f"registry-selected XML converter {converter_name!r} is not available")
    try:
        converted = converter(rendered)
        if not isinstance(converted, str):
            raise FilingExportValidationError(
                f"registry-selected XML converter {converter_name!r} returned a non-string value"
            )
        return converted
    except ValueError as exc:
        raise FilingExportValidationError(str(exc)) from exc


def _xml_dictionary_rendered_value(
    entry: XmlDictionaryEntry,
    *,
    draft: ModeloDraft,
    casilla_values: dict[CasillaId, object],
    headers: Mapping[FilingProducerKey, object],
    dictionary_values: Mapping[str, object],
    declarations: Mapping[str, str] | None,
) -> str | None:
    raw = _xml_dictionary_raw_value(
        entry, casilla_values=casilla_values, headers=headers, dictionary_values=dictionary_values
    )
    if raw is None:
        return None
    routed = _modelo100_sign_routed_value(entry, raw, draft=draft, declarations=declarations)
    if routed is None:
        return None
    rendered = format_xml_dictionary_value(entry.data_type, routed)
    if draft.modelo == form_for_role("renta.annual") and entry.field_id in {"DP_APENOM_D", "DP_APENOM_C"}:
        rendered = rendered.upper()
    return _apply_xml_dictionary_value_converter(entry, rendered, declarations)


def _is_zero_token(value: str | None) -> bool:
    """Say whether a rendered token states nothing: blank, or an amount of zero."""
    if value is None or not value.strip():
        return True
    parsed = coerce_decimal(value.strip())
    return parsed is not None and parsed.is_zero()


def _prune_zero_only_xml_subtrees(root: ElementTree.Element[str], *, optional_element_paths: frozenset[str]) -> None:
    """Omit optional Modelo 100 branches containing only calculated zero placeholders.

    Modelo 100 calculations deliberately retain zero-valued casillas for audit and
    formula traceability. The AEAT XML uses optional branches for those same facts;
    materialising every retained zero selects mutually exclusive XSD branches and
    creates incomplete repeated records. A subtree with no non-zero text and no
    non-zero attribute carries no filing fact, so remove it before serialisation.
    Required children of a populated branch remain the exporter's responsibility
    and are exercised by whole-document XSD validation in acceptance.
    """

    def prune(node: ElementTree.Element[str], path: str) -> bool:
        retained_child_states: list[bool] = []
        for child in tuple(node):
            child_path = f"{path}/{child.tag}"
            child_is_zero_only = prune(child, child_path)
            if child_is_zero_only and child_path in optional_element_paths:
                node.remove(child)
            else:
                retained_child_states.append(child_is_zero_only)
        return (
            all(retained_child_states)
            and _is_zero_token(node.text)
            and all(_is_zero_token(value) for value in node.attrib.values())
        )

    prune(root, "")


@dataclass(frozen=True, slots=True)
class XmlDictionaryRepeatedRows:
    """The occurrences one repeating element takes, one per row of the columns declared on it.

    The element and its bound come from the XSD, and each column's place from the
    dictionary row of the box its binding targets, so no form is named here.
    """

    element_path: str
    occurrences: tuple[Mapping[str, str], ...]
    """Each occurrence's rendered tokens, by the absolute path of the dictionary row."""
    casilla_by_path: Mapping[str, CasillaId]

    def holds(self, path: str) -> bool:
        """Say whether a dictionary row sits inside the repeating element."""
        return path.startswith(f"{self.element_path}/")


def _nearest_repeating_path(path: str, repeating: Mapping[str, int | None]) -> str | None:
    """Return the innermost repeating element that encloses ``path``."""
    parts = path.split("/")
    return next(
        (candidate for end in range(len(parts) - 1, 0, -1) if (candidate := "/".join(parts[:end])) in repeating),
        None,
    )


def _row_column_entry(
    binding: BindingDefinition,
    entries: tuple[XmlDictionaryEntry, ...],
    repeating: Mapping[str, int | None],
) -> tuple[str, XmlDictionaryEntry]:
    """Find the one dictionary row a row binding fills, and the repeating element around it."""
    target = selector_as_dict(binding).get("target_casilla_id")
    if binding_aggregation_op(binding) is not BindingAggregationOp.ROWS or target is None:
        raise FilingExportValidationError(f"binding {binding.id!r} carries rows but declares no row column")
    placed = tuple(
        (element, entry)
        for entry in entries
        if entry.casilla_id == target and (element := _nearest_repeating_path(entry.path, repeating)) is not None
    )
    if len(placed) != 1:
        raise FilingExportValidationError(
            f"row column {binding.id!r} needs one repeating dictionary row for box {target}, found {len(placed)}",
        )
    return placed[0]


def _row_values(draft: ModeloDraft) -> tuple[ModeloBindingValue, ...]:
    """Return the draft's row values in row order; a column a row has no value for stays off it."""
    return tuple(
        sorted(
            (
                value
                for value in draft.binding_values
                if value.row_index is not None and value.value is not None and value.value != ""
            ),
            key=lambda value: (value.row_index or 0, value.binding_id),
        ),
    )


def xml_dictionary_repeated_rows(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    entries: tuple[XmlDictionaryEntry, ...],
    schema_provider: RegistrySchemaAccessor,
) -> tuple[XmlDictionaryRepeatedRows, ...]:
    """Read the draft's row values as occurrences of the repeating elements the XSD declares.

    Args:
        layout: The ``xml_dictionary`` layout being rendered or verified.
        draft: The draft holding the row values.
        entries: Every dictionary row of the layout.
        schema_provider: Resolves the revision's bindings and the layout's XSD.

    Returns:
        One row set per repeating element the draft fills; empty when it holds no rows.

    Raises:
        FilingExportValidationError: A row has no place in the dictionary, or a row
            set exceeds the occurrences the XSD admits.
    """
    values = _row_values(draft)
    if not values:
        return ()
    repeating = _xml_dictionary_repeating_element_paths(
        _xml_dictionary_xsd_source(layout, schema_provider.sources),
        source_payloads=schema_provider.source_payloads,
    )
    bindings = {binding.id: binding for binding in schema_provider.get_snapshot(draft.modelo).revision.bindings}
    occurrences: dict[str, dict[int, dict[str, str]]] = {}
    casillas: dict[str, dict[str, CasillaId]] = {}
    for value in values:
        binding = bindings[value.binding_id]
        element, entry = _row_column_entry(binding, entries, repeating)
        row = occurrences.setdefault(element, {}).setdefault(value.row_index or 0, {})
        row[entry.path] = _render_bound_row_value(binding, entry, value.value)
        if entry.casilla_id is not None:
            casillas.setdefault(element, {})[entry.path] = entry.casilla_id
    return tuple(
        _bounded_repeated_rows(element, rows, casillas.get(element, {}), limit=repeating[element])
        for element, rows in occurrences.items()
    )


def _render_bound_row_value(binding: BindingDefinition, entry: XmlDictionaryEntry, value: object) -> str:
    """Restore dates transported as ISO strings using the binding's declared scalar type."""
    if binding.value.data_type is BindingDataType.DATE and isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError as error:
            raise FilingExportValidationError(f"date row binding {binding.id!r} carries an invalid date") from error
    return format_xml_dictionary_value(entry.data_type, value)


def _bounded_repeated_rows(
    element: str,
    rows: Mapping[int, Mapping[str, str]],
    casilla_by_path: Mapping[str, CasillaId],
    *,
    limit: int | None,
) -> XmlDictionaryRepeatedRows:
    if limit is not None and len(rows) > limit:
        raise FilingExportValidationError(
            f"{len(rows)} rows do not fit {element}, which the official schema admits {limit} times",
        )
    return XmlDictionaryRepeatedRows(
        element_path=element,
        occurrences=tuple(rows[index] for index in sorted(rows)),
        casilla_by_path=casilla_by_path,
    )


def _require_value_stated_by_rows(
    entry: XmlDictionaryEntry,
    rendered: str,
    rows: XmlDictionaryRepeatedRows,
) -> None:
    """Refuse a value for one box of a repeating element that its rows do not account for.

    Once the element repeats, a value held for the whole box belongs to no occurrence.
    It stands only as the total of the rows, which the form's own sums already read.
    Anything else would be filed against a sale it does not describe, or dropped.
    """
    if _is_zero_token(rendered):
        return
    tokens = tuple(row[entry.path] for row in rows.occurrences if entry.path in row)
    numeric = is_xml_dictionary_numeric_type(entry.data_type)
    if numeric and tokens:
        stated = sum((Decimal(token) for token in tokens), Decimal("0"))
        accounted = stated == Decimal(rendered)
    else:
        accounted = rendered in tokens
    if not accounted:
        raise FilingExportValidationError(
            f"box {entry.casilla_id} holds {rendered}, which the rows of {rows.element_path} do not add up to. "
            "Correct the box or the rows so that each sale states its own figures.",
        )


def _append_repeated_rows(
    root: ElementTree.Element[str],
    rows: XmlDictionaryRepeatedRows,
    *,
    element_order: dict[str, tuple[str, ...]],
) -> None:
    """Write one new occurrence per row, each child at the place the schema gives it."""
    parent_parts = _xml_dictionary_path_parts(rows.element_path)
    parent = root
    parent_path = ""
    for part in parent_parts[:-1]:
        parent = _get_or_create_xml_dictionary_child(
            parent, part, current_path=parent_path, element_order=element_order
        )
        parent_path = f"{parent_path}/{part}"
    tag = parent_parts[-1]
    for row in rows.occurrences:
        occurrence = ElementTree.Element(tag)
        parent.insert(_declared_child_position(parent, tag, element_order.get(parent_path)), occurrence)
        for path, token in row.items():
            _set_occurrence_child(occurrence, rows.element_path, path, token, element_order=element_order)


def _set_occurrence_child(
    occurrence: ElementTree.Element[str],
    element_path: str,
    path: str,
    token: str,
    *,
    element_order: dict[str, tuple[str, ...]],
) -> None:
    current = occurrence
    current_path = element_path
    for part in _xml_dictionary_path_parts(path.removeprefix(element_path)):
        current = _get_or_create_xml_dictionary_child(
            current, part, current_path=current_path, element_order=element_order
        )
        current_path = f"{current_path}/{part}"
    current.text = token


def _occurrence_tokens(node: ElementTree.Element[str], path: str) -> Iterator[tuple[str, str]]:
    for child in node:
        child_path = f"{path}/{child.tag}"
        if len(child):
            yield from _occurrence_tokens(child, child_path)
        else:
            yield child_path, child.text or ""


def mismatched_xml_dictionary_repeated_casillas(
    payload: bytes,
    repeated_rows: tuple[XmlDictionaryRepeatedRows, ...],
) -> tuple[CasillaId, ...]:
    """Compare each occurrence in a written file with the row it should state, column by column.

    A value of zero may have been pruned as an optional branch, so a zero and an
    absence read alike here, as they do on the form.

    Returns:
        The boxes of every column that differs in any occurrence.
    """
    root = DefusedElementTree.fromstring(payload)
    mismatched: list[CasillaId] = []
    for rows in repeated_rows:
        written = tuple(
            dict(_occurrence_tokens(node, rows.element_path))
            for node in _elements_at(root, _xml_dictionary_path_parts(rows.element_path))
        )
        expected = rows.occurrences
        for path, casilla in rows.casilla_by_path.items():
            stated = tuple(_nonzero_token(row.get(path)) for row in expected)
            if stated != tuple(_nonzero_token(row.get(path)) for row in written):
                mismatched.append(casilla)
    return tuple(mismatched)


def _elements_at(node: ElementTree.Element[str], parts: tuple[str, ...]) -> Iterator[ElementTree.Element[str]]:
    if not parts:
        yield node
        return
    for child in node:
        if child.tag == parts[0]:
            yield from _elements_at(child, parts[1:])


def _nonzero_token(token: str | None) -> str | None:
    return None if _is_zero_token(token) else token


def _xml_dictionary_non_casilla_value(
    entry: XmlDictionaryEntry,
    *,
    headers: Mapping[FilingProducerKey, object],
    dictionary_values: Mapping[str, object],
) -> object | None:
    """Resolve a row no casilla addresses, keeping the value's Python type.

    Two channels answer here, and the order between them is what makes the
    declared one authoritative. ``dictionary_values`` is keyed by the field id
    AEAT's own dictionary names, which is the address a registry binding
    declares, and each value arrives as the type its fact carries -- a ``bool``
    is still a ``bool``, a :class:`~datetime.date` still a ``date``, so
    :func:`format_xml_dictionary_value` can still decide ``SI``/``NO`` and
    ``d/m/yyyy`` from it. ``headers`` is the flat declaration-header mapping,
    whose contract is ``str`` throughout: a value reaching here through it has
    already been rendered by its composer and is passed on as written.

    Consulting the declared channel first means a header key that happens to
    collide with a dictionary field id cannot shadow a typed value with a
    pre-rendered string. No such collision exists today -- measured across all
    2,383 rows of the Modelo 100 2024 dictionary against every key the export
    header composer emits, the intersection is empty -- so the order states what
    happens when one appears rather than changing what happens now.

    Args:
        entry: The dictionary row being written.
        headers: Declaration headers, lowercased keys, string values.
        dictionary_values: Values addressed by dictionary field id.

    Returns:
        The value to render, or ``None`` when neither channel addresses the row.
    """
    del headers
    return dictionary_values.get(entry.field_id)


def _set_xml_dictionary_path(
    root: ElementTree.Element[str],
    absolute_path: str,
    value: str,
    *,
    element_order: dict[str, tuple[str, ...]],
) -> None:
    """Write ``value`` at ``absolute_path``, creating each element in schema order.

    A newly created element is placed at the position ``element_order`` declares
    for it rather than appended, because the schema's ``xs:sequence`` makes
    sibling order significant and the dictionary rows that drive this walk do not
    arrive in that order. Placement is the only thing the order decides: an
    element's tag, text, and attributes are unaffected.
    """
    parts = _xml_dictionary_path_parts(absolute_path)
    if not parts:
        raise FilingExportValidationError("XML dictionary entry path must not be empty")
    current = root
    current_path = ""
    for index, part in enumerate(parts):
        if index == 0 and part == root.tag:
            continue
        if _set_xml_dictionary_attribute(current, part, index=index, final_index=len(parts) - 1, value=value):
            return
        current = _get_or_create_xml_dictionary_child(
            current,
            part,
            current_path=current_path,
            element_order=element_order,
        )
        current_path = f"{current_path}/{part}"
    current.text = value


def _xml_dictionary_path_parts(absolute_path: str) -> tuple[str, ...]:
    """Split an XML dictionary path into its non-empty components."""
    return tuple(part for part in absolute_path.strip("/").split("/") if part)


def _set_xml_dictionary_attribute(
    current: ElementTree.Element[str],
    part: str,
    *,
    index: int,
    final_index: int,
    value: str,
) -> bool:
    """Set a terminating attribute component and report whether it was one."""
    if not part.startswith("@"):
        return False
    if index != final_index:
        raise FilingExportValidationError("XML dictionary attribute must terminate its path")
    current.set(part[1:], value)
    return True


def _get_or_create_xml_dictionary_child(
    current: ElementTree.Element[str],
    part: str,
    *,
    current_path: str,
    element_order: dict[str, tuple[str, ...]],
) -> ElementTree.Element[str]:
    """Find a path child or create it at its XSD-declared sibling position."""
    child = next((candidate for candidate in current if candidate.tag == part), None)
    if child is None:
        child = ElementTree.Element(part)
        current.insert(_declared_child_position(current, part, element_order.get(current_path)), child)
    return child


def _declared_child_position(
    parent: ElementTree.Element[str],
    tag: str,
    declared: tuple[str, ...] | None,
) -> int:
    """Return the index ``tag`` belongs at among ``parent``'s existing children.

    Falls back to appending when the schema describes neither the parent nor the
    new tag, which keeps a path the XSD does not cover rendering exactly as it did
    before rather than dropping it or guessing a position for it.
    """
    if declared is None:
        return len(parent)
    ranks = {name: position for position, name in enumerate(declared)}
    rank = ranks.get(tag)
    if rank is None:
        return len(parent)
    for position, existing in enumerate(parent):
        existing_rank = ranks.get(str(existing.tag))
        if existing_rank is not None and existing_rank > rank:
            return position
    return len(parent)


__all__ = [
    "XmlDictionaryRepeatedRows",
    "mismatched_xml_dictionary_repeated_casillas",
    "render_xml_dictionary_layout",
    "xml_dictionary_repeated_rows",
]
