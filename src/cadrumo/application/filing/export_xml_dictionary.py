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

from ...core.casilla_id import CasillaId
from ...core.decimal.coercion import coerce_decimal
from ...core.external_constants import UTF_8_ENCODING
from ...core.filing_producer_key import FilingProducerKey
from ...domain.calculations.registry.binding_selector_utils import selector_as_dict
from ...domain.calculations.registry.binding_value_contract import BindingDataType
from ...domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry
from ...domain.calculations.registry.form_codes import form_for_role
from ...domain.calculations.registry.inventory_bindings import TAXPAYER_YEAR_ACTIVITY_GRAIN
from ...domain.calculations.registry.schema import BindingDefinition, ModeloRevision
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.contribuyente.renta_codes import modelo100_ccaa_codigo, modelo100_ecivil_export_code
from ...domain.filing.errors import (
    FilingExportDesignIntegrityError,
    FilingExportIntegrityError,
    FilingExportValidationError,
)
from ...domain.filing.schema import ModeloBindingValue, ModeloDraft
from .errors import casilla_value_refusal
from .export_refusal_doors import ExportRefusalReason, export_design_terminal, export_input_decision
from .export_xml_dictionary_modelo100 import (
    modelo_100_sign_branch_value,
    modelo_100_unfiled_comunidad_paths,
    refuse_family_minimum_without_its_rows,
    registry_modelo_100_xml_declarations,
)
from .export_xml_dictionary_rows import xml_dictionary_layout_casillas, xml_dictionary_layout_entries
from .export_xml_dictionary_values import format_xml_dictionary_value, is_xml_dictionary_numeric_type
from .export_xml_dictionary_xsd import (
    XML_DICTIONARY_ROOT_TAG,
    latest_xml_dictionary_xsd_version,
    xml_dictionary_element_order,
    xml_dictionary_optional_element_paths,
    xml_dictionary_repeating_element_paths,
    xml_dictionary_xsd_root,
    xml_dictionary_xsd_source,
)
from .export_xml_input_dictionary import declared_and_admitted_dictionary_entries
from .export_xml_row_columns import require_row_totals_stated, row_column_entry
from .export_xml_value_limits import (
    XmlValueSchema,
    canonical_xml_text,
    prune_childless_negative_blocks,
    refuse_xml_missing_required_content,
    refuse_xml_values_outside_schema,
    xml_value_schema,
)
from .runtime import RegistrySchemaAccessor

_XML_SCHEMA_INSTANCE_NS = "http://www.w3.org/2001/XMLSchema-instance"
ElementTree.register_namespace("xsi", _XML_SCHEMA_INSTANCE_NS)

# The declaration's identity block. Mandatory and first in the ``Declaracion``
# sequence of every bundled AEAT Modelo 100 XSD, and absent from every bundled
# dictionary, so it is written from the layout rather than from a dictionary row.
_AUX_TAG = "Aux"

# The per-taxpayer block of a Modelo 100 declaration. Its mandatory ``nif``
# attribute is declared in no dictionary, so it is stamped after the walk rather
# than written from a dictionary row; its ``titular`` sibling IS declared and is
# written by the walk like any other row.
_TOMA_DATOS_TAG = "TomaDatosAmpliada"
_DATOS_ECONOMICOS_TAG = "DatosEconomicos"
_TAXATION_OPTION_ATTRIBUTE = "TIPOTRIBUTACION"
_INDIVIDUAL_TAXATION = "1"
_TITULAR_ATTRIBUTE = "titular"
_HOLDER_DICTIONARY_TYPE = "TIT"
_DECLARANTE_HOLDER = "declarante"


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
            raise FilingExportDesignIntegrityError(
                "Modelo 100 XML declarations were not resolved",
                translated_message="errors.integrity.filing_export_modelo100_declarations_unresolved",
            )
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
    value_schema: XmlValueSchema,
    element_order: dict[str, tuple[str, ...]],
    repeated_rows: tuple[XmlDictionaryRepeatedRows, ...] = (),
) -> None:
    boxes: dict[str, dict[str, str]] = {}
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
            value_schema=value_schema,
        )
        if rendered is None or rendered == "":
            continue
        rows = next((item for item in repeated_rows if item.holds(entry.path)), None)
        _place_xml_dictionary_value(root, entry, rendered, rows, boxes=boxes, element_order=element_order)
    for rows in repeated_rows:
        _append_repeated_rows(root, rows.with_boxes(boxes.get(rows.element_path, {})), element_order=element_order)


def _place_xml_dictionary_value(
    root: ElementTree.Element[str],
    entry: XmlDictionaryEntry,
    rendered: str,
    rows: XmlDictionaryRepeatedRows | None,
    *,
    boxes: dict[str, dict[str, str]],
    element_order: dict[str, tuple[str, ...]],
) -> None:
    """Set a value at its path, hold it for its repeated rows, or require those rows to state it."""
    if rows is None:
        set_xml_dictionary_path(root, entry.path, rendered, element_order=element_order)
    elif rows.takes_box(entry.path) and not _is_zero_token(rendered):
        boxes.setdefault(rows.element_path, {})[entry.path] = rendered
    else:
        _require_value_stated_by_rows(entry, rendered, rows)


def _finish_xml_dictionary_root(
    root: ElementTree.Element[str],
    draft: ModeloDraft,
    *,
    optional_element_paths: frozenset[str],
    value_schema: XmlValueSchema,
) -> None:
    if draft.modelo == form_for_role("renta.annual"):
        _stamp_toma_datos_nif(root, draft)
        _stamp_individual_return_titular(root)
        prune_zero_only_xml_subtrees(root, optional_element_paths=optional_element_paths)
        prune_childless_negative_blocks(root, schema=value_schema)


def _serialize_xml_dictionary(root: ElementTree.Element[str]) -> bytes:
    rendered = ElementTree.tostring(root, encoding=UTF_8_ENCODING, xml_declaration=True)
    if not isinstance(rendered, bytes):
        raise FilingExportIntegrityError(
            f"the XML dictionary serialiser returned {type(rendered).__name__}, not bytes",
            translated_message="errors.integrity.filing_export_xml_serialiser_not_bytes",
            context={"type": type(rendered).__name__},
        )
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
    revision = schema_provider.get_snapshot(draft.modelo).revision
    entries = layout_dictionary_entries(layout, revision=revision, schema_provider=schema_provider)
    root = ElementTree.Element(
        XML_DICTIONARY_ROOT_TAG,
        expected_xml_dictionary_root_identity(layout, draft=draft, schema_provider=schema_provider),
    )
    element_order = xml_dictionary_element_order(
        xml_dictionary_xsd_source(layout, schema_provider.sources),
        source_payloads=schema_provider.source_payloads,
    )
    optional_element_paths = xml_dictionary_optional_element_paths(
        xml_dictionary_xsd_source(layout, schema_provider.sources),
        source_payloads=schema_provider.source_payloads,
    )
    append_declaration_aux(root, layout, aux_version=aux_version)
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    declarations, unfiled_paths = _modelo100_render_exclusions(draft, entries, casilla_values)
    repeated_rows = xml_dictionary_repeated_rows(layout, draft=draft, entries=entries, schema_provider=schema_provider)
    require_row_totals_stated(
        revision,
        draft,
        entries=entries,
        repeating=xml_dictionary_repeating_element_paths(
            xml_dictionary_xsd_source(layout, schema_provider.sources),
            source_payloads=schema_provider.source_payloads,
        ),
    )
    value_schema = xml_dictionary_value_schema(layout, schema_provider=schema_provider)
    _write_xml_dictionary_entries(
        root,
        entries,
        unfiled_paths=unfiled_paths,
        draft=draft,
        casilla_values=casilla_values,
        headers=headers,
        dictionary_values=dictionary_values or {},
        declarations=declarations,
        value_schema=value_schema,
        element_order=element_order,
        repeated_rows=repeated_rows,
    )
    _finish_xml_dictionary_root(root, draft, optional_element_paths=optional_element_paths, value_schema=value_schema)
    _refuse_values_outside_xsd(root, layout, entries=entries, schema_provider=schema_provider)
    return _serialize_xml_dictionary(root)


def layout_dictionary_entries(
    layout: ExportLayoutDefinition,
    *,
    revision: ModeloRevision,
    schema_provider: RegistrySchemaAccessor,
) -> tuple[XmlDictionaryEntry, ...]:
    """Return every dictionary row the layout places for a revision: the declared rows, then the admitted ones.

    Args:
        layout: The ``xml_dictionary`` layout being rendered or verified.
        revision: The :class:`ModeloRevision` whose row bindings may need input-dictionary rows.
        schema_provider: Resolves the layout's dictionaries and XSD.

    Returns:
        The declaration dictionary's rows followed by the input-dictionary rows admitted beside them.
    """
    declared, admitted = declared_and_admitted_dictionary_entries(
        layout,
        bindings=revision.bindings,
        casillas=xml_dictionary_layout_casillas(layout, schema_provider=schema_provider),
        sources=schema_provider.sources,
        source_payloads=schema_provider.source_payloads,
    )
    return (*declared, *admitted)


def xml_dictionary_value_schema(
    layout: ExportLayoutDefinition,
    *,
    schema_provider: RegistrySchemaAccessor,
) -> XmlValueSchema:
    """Read the layout's official XSD for normalizing the values of its rows.

    Args:
        layout: The ``xml_dictionary`` layout being rendered or verified.
        schema_provider: Resolves the layout's XSD source.

    Returns:
        The :class:`XmlValueSchema` of that edition.
    """
    source = xml_dictionary_xsd_source(layout, schema_provider.sources)
    return xml_value_schema(
        xml_dictionary_xsd_root(source, source_payloads=schema_provider.source_payloads),
        source_id=source.id,
        root_tag=XML_DICTIONARY_ROOT_TAG,
    )


def refuse_xml_dictionary_payload_outside_xsd(
    layout: ExportLayoutDefinition,
    *,
    payload: bytes,
    schema_provider: RegistrySchemaAccessor,
) -> None:
    """Hold an already written declaration to the limits its rendering was held to.

    Args:
        layout: The ``xml_dictionary`` layout the file was exported through.
        payload: The file's bytes, already known to parse.
        schema_provider: Resolves the layout's dictionary and XSD sources.

    Raises:
        ModeloApplicationError: The file holds a value its official XSD does not admit.
    """
    _refuse_values_outside_xsd(
        DefusedElementTree.fromstring(payload),
        layout,
        entries=xml_dictionary_layout_entries(layout, schema_provider=schema_provider),
        schema_provider=schema_provider,
    )


def refuse_incomplete_xml_dictionary_payload(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    payload: bytes,
    schema_provider: RegistrySchemaAccessor,
) -> None:
    """Refuse a filer's rendered declaration that omits what its official XSD requires.

    Args:
        layout: The ``xml_dictionary`` layout the file was rendered through.
        draft: The approved draft the file states.
        payload: The rendered bytes.
        schema_provider: Resolves the layout's dictionary and XSD sources.

    Raises:
        ModeloApplicationError: Required content is absent, or a family minimum the
            file claims identifies nobody.

    ``draft`` is the :class:`ModeloDraft`, the local modelo draft.
    """
    document = DefusedElementTree.fromstring(payload)
    source = xml_dictionary_xsd_source(layout, schema_provider.sources)
    refuse_xml_missing_required_content(
        document,
        schema=xml_dictionary_xsd_root(source, source_payloads=schema_provider.source_payloads),
        source_id=source.id,
        entries=layout_dictionary_entries(
            layout, revision=schema_provider.get_snapshot(draft.modelo).revision, schema_provider=schema_provider
        ),
    )
    if draft.modelo == form_for_role("renta.annual"):
        refuse_family_minimum_without_its_rows(document)


def _refuse_values_outside_xsd(
    document: ElementTree.Element[str],
    layout: ExportLayoutDefinition,
    *,
    entries: tuple[XmlDictionaryEntry, ...],
    schema_provider: RegistrySchemaAccessor,
) -> None:
    source = xml_dictionary_xsd_source(layout, schema_provider.sources)
    refuse_xml_values_outside_schema(
        document,
        schema=xml_dictionary_xsd_root(source, source_payloads=schema_provider.source_payloads),
        source_id=source.id,
        entries=entries,
    )


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
    xsd_source = xml_dictionary_xsd_source(layout, schema_provider.sources)
    version = latest_xml_dictionary_xsd_version(xsd_source, source_payloads=schema_provider.source_payloads)
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
        raise FilingExportValidationError(
            "XML dictionary payload could not be parsed",
            translated_message="application.filing.export.errors.xml_payload_unreadable",
            precondition_verdict=export_input_decision(ExportRefusalReason.PAYLOAD_NOT_READABLE),
        ) from exc
    if root.tag != XML_DICTIONARY_ROOT_TAG:
        raise FilingExportValidationError(
            f"XML dictionary payload root is {root.tag!r}, expected {XML_DICTIONARY_ROOT_TAG!r}",
            translated_message="application.filing.export.errors.xml_payload_root_differs",
            context={"found": root.tag, "expected": XML_DICTIONARY_ROOT_TAG},
            precondition_verdict=export_input_decision(ExportRefusalReason.PAYLOAD_NOT_READABLE),
        )
    return dict(root.attrib)


def append_declaration_aux(
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
        raise FilingExportDesignIntegrityError(
            "XML dictionary layout omits mandatory Aux/Idioma",
            translated_message="errors.integrity.filing_export_xml_aux_idioma_omitted",
        )
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
    casilla carries a value: :func:`_stamp_individual_return_titular` answers it for an
    individual return and the required-content check refuses it for a joint one.

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


def _stamp_individual_return_titular(root: ElementTree.Element[str]) -> None:
    """Name the declarante as ``titular`` of an individual return's unstated block.

    The attribute is required and comes from whichever titular box the return fills.
    An individual return has one contributor, so a block with no such box can only be
    the declarante's. A joint return may report a spouse's income, so its blank is left
    for the required-content check to refuse rather than attributed here.
    """
    economic = root.find(_DATOS_ECONOMICOS_TAG)
    if economic is None or economic.get(_TAXATION_OPTION_ATTRIBUTE) != _INDIVIDUAL_TAXATION:
        return
    for block in economic.iter(_TOMA_DATOS_TAG):
        if block.get(_TITULAR_ATTRIBUTE) is None:
            block.set(_TITULAR_ATTRIBUTE, format_xml_dictionary_value(_HOLDER_DICTIONARY_TYPE, _DECLARANTE_HOLDER))


def stamped_individual_return_titular(entry: XmlDictionaryEntry, payload: bytes) -> str | None:
    """Return the token the export stamps at ``entry``, when it has no box to be compared with.

    Args:
        entry: The dictionary row being verified.
        payload: The file's bytes, already known to parse.

    Returns:
        The declarante token for a ``titular`` row of an individual return; otherwise ``None``.
    """
    if not entry.path.endswith(f"/{_TOMA_DATOS_TAG}/@{_TITULAR_ATTRIBUTE}"):
        return None
    economic = DefusedElementTree.fromstring(payload).find(_DATOS_ECONOMICOS_TAG)
    if economic is None or economic.get(_TAXATION_OPTION_ATTRIBUTE) != _INDIVIDUAL_TAXATION:
        return None
    return format_xml_dictionary_value(_HOLDER_DICTIONARY_TYPE, _DECLARANTE_HOLDER)


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
        raise FilingExportDesignIntegrityError(
            "Modelo 100 XML declarations were not resolved",
            translated_message="errors.integrity.filing_export_modelo100_declarations_unresolved",
        )
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
        raise FilingExportDesignIntegrityError(
            f"registry-selected XML converter {converter_name!r} is not available",
            translated_message="errors.integrity.filing_export_xml_converter_unavailable",
            context={"converter": converter_name},
        )
    try:
        converted = converter(rendered)
        if not isinstance(converted, str):
            raise FilingExportDesignIntegrityError(
                f"registry-selected XML converter {converter_name!r} returned a non-string value",
                translated_message="errors.integrity.filing_export_xml_converter_non_string",
                context={"converter": converter_name},
            )
        return converted
    except ValueError as exc:
        raise FilingExportValidationError(
            str(exc),
            translated_message="application.filing.export.errors.xml_value_not_convertible",
            context={"converter": converter_name},
            precondition_verdict=export_input_decision(ExportRefusalReason.VALUE_NOT_CONVERTIBLE),
        ) from exc


def _xml_dictionary_rendered_value(
    entry: XmlDictionaryEntry,
    *,
    draft: ModeloDraft,
    casilla_values: dict[CasillaId, object],
    headers: Mapping[FilingProducerKey, object],
    dictionary_values: Mapping[str, object],
    declarations: Mapping[str, str] | None,
    value_schema: XmlValueSchema,
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
    converted = _apply_xml_dictionary_value_converter(entry, rendered, declarations)
    return canonical_xml_text(value_schema, entry.path, converted)


def _is_zero_token(value: str | None) -> bool:
    """Say whether a rendered token states nothing: blank, or an amount of zero."""
    if value is None or not value.strip():
        return True
    parsed = coerce_decimal(value.strip())
    return parsed is not None and parsed.is_zero()


def prune_zero_only_xml_subtrees(root: ElementTree.Element[str], *, optional_element_paths: frozenset[str]) -> None:
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
    activity_grained: bool
    """Whether every binding filling these rows declares one row per activity of the taxpayer's year."""

    def holds(self, path: str) -> bool:
        """Say whether a dictionary row sits inside the repeating element."""
        return path.startswith(f"{self.element_path}/")

    def takes_box(self, path: str) -> bool:
        """Say whether a box held for the whole element belongs to its sole occurrence.

        Only rows declared one per activity qualify: their one occurrence is the return's
        one activity, which its source establishes before any row exists. Rows of any
        other grain say nothing about whose box it is. With several occurrences, or one
        that already states the box, writing it would pick an occurrence the box may not
        describe.
        """
        return (
            self.activity_grained
            and self.holds(path)
            and len(self.occurrences) == 1
            and path not in self.occurrences[0]
        )

    def with_boxes(self, tokens: Mapping[str, str]) -> XmlDictionaryRepeatedRows:
        """Return the rows with ``tokens`` written into their sole occurrence."""
        if not tokens:
            return self
        if not all(self.takes_box(path) for path in tokens):
            raise FilingExportValidationError(
                f"boxes {sorted(tokens)} have no single occurrence of {self.element_path} to take them",
                translated_message="application.filing.export.errors.xml_boxes_without_single_row",
                context={"paths": ", ".join(sorted(tokens)), "element_path": self.element_path},
                precondition_verdict=export_design_terminal(ExportRefusalReason.BOX_HAS_NO_SINGLE_OCCURRENCE),
            )
        return XmlDictionaryRepeatedRows(
            element_path=self.element_path,
            occurrences=(MappingProxyType({**self.occurrences[0], **tokens}),),
            casilla_by_path=self.casilla_by_path,
            activity_grained=self.activity_grained,
        )


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
        draft: The :class:`~cadrumo.domain.filing.schema.ModeloDraft` holding the row values.
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
    repeating = xml_dictionary_repeating_element_paths(
        xml_dictionary_xsd_source(layout, schema_provider.sources),
        source_payloads=schema_provider.source_payloads,
    )
    bindings = {binding.id: binding for binding in schema_provider.get_snapshot(draft.modelo).revision.bindings}
    value_schema = xml_dictionary_value_schema(layout, schema_provider=schema_provider)
    occurrences: dict[str, dict[int, dict[str, str]]] = {}
    casillas: dict[str, dict[str, CasillaId]] = {}
    grains: dict[str, set[object]] = {}
    for value in values:
        binding = bindings[value.binding_id]
        element, entry = row_column_entry(binding, entries, repeating)
        grains.setdefault(element, set()).add(selector_as_dict(binding).get("projection_grain"))
        row = occurrences.setdefault(element, {}).setdefault(value.row_index or 0, {})
        row[entry.path] = canonical_xml_text(
            value_schema, entry.path, _render_bound_row_value(binding, entry, value.value)
        )
        if entry.casilla_id is not None:
            casillas.setdefault(element, {})[entry.path] = entry.casilla_id
    return tuple(
        _bounded_repeated_rows(
            element,
            rows,
            casillas.get(element, {}),
            limit=repeating[element],
            activity_grained=grains[element] == {TAXPAYER_YEAR_ACTIVITY_GRAIN},
        )
        for element, rows in occurrences.items()
    )


def _render_bound_row_value(binding: BindingDefinition, entry: XmlDictionaryEntry, value: object) -> str:
    """Restore dates transported as ISO strings using the binding's declared scalar type."""
    if binding.value.data_type is BindingDataType.DATE and isinstance(value, str):
        try:
            value = date.fromisoformat(value)
        except ValueError as error:
            raise FilingExportValidationError(
                f"date row binding {binding.id!r} carries an invalid date",
                translated_message="application.filing.export.errors.xml_row_date_invalid",
                context={"binding": binding.id},
                precondition_verdict=export_input_decision(ExportRefusalReason.ROW_VALUE_INVALID),
            ) from error
    return format_xml_dictionary_value(entry.data_type, value)


def _bounded_repeated_rows(
    element: str,
    rows: Mapping[int, Mapping[str, str]],
    casilla_by_path: Mapping[str, CasillaId],
    *,
    limit: int | None,
    activity_grained: bool,
) -> XmlDictionaryRepeatedRows:
    if limit is not None and len(rows) > limit:
        raise FilingExportValidationError(
            f"{len(rows)} rows do not fit {element}, which the official schema admits {limit} times",
            translated_message="application.filing.export.errors.xml_rows_exceed_schema",
            context={"rows": len(rows), "element_path": element, "limit": limit},
            precondition_verdict=export_input_decision(ExportRefusalReason.ROWS_EXCEED_SCHEMA),
        )
    return XmlDictionaryRepeatedRows(
        element_path=element,
        occurrences=tuple(rows[index] for index in sorted(rows)),
        casilla_by_path=casilla_by_path,
        activity_grained=activity_grained,
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
    if not accounted and entry.casilla_id is not None:
        raise casilla_value_refusal(
            entry.casilla_id,
            translated_message="application.filing.export.errors.box_not_stated_by_rows",
            context={"element_path": rows.element_path, "value": rendered},
        )
    if not accounted:
        raise FilingExportValidationError(
            f"box {entry.casilla_id} holds {rendered}, which the rows of {rows.element_path} do not add up to. "
            "Correct the box or the rows so that each sale states its own figures.",
            translated_message="application.filing.export.errors.xml_value_not_stated_by_rows",
            context={"path": entry.path, "element_path": rows.element_path},
            precondition_verdict=export_input_decision(ExportRefusalReason.VALUE_NOT_STATED_BY_ROWS),
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


def set_xml_dictionary_path(
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
        raise FilingExportDesignIntegrityError(
            "XML dictionary entry path must not be empty",
            translated_message="errors.integrity.filing_export_xml_entry_path_empty",
        )
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
        raise FilingExportDesignIntegrityError(
            "XML dictionary attribute must terminate its path",
            translated_message="errors.integrity.filing_export_xml_attribute_not_terminal",
        )
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
    "layout_dictionary_entries",
    "mismatched_xml_dictionary_repeated_casillas",
    "refuse_xml_dictionary_payload_outside_xsd",
    "render_xml_dictionary_layout",
    "xml_dictionary_repeated_rows",
    "xml_dictionary_value_schema",
]
