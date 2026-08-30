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

import re
from collections.abc import Callable, Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from types import MappingProxyType
from xml.etree import ElementTree

from defusedxml import ElementTree as DefusedElementTree

from ...core import FilingProducerKey
from ...core.modelo import Modelo
from ...core.casilla_id import CasillaId
from ...core.decimal import coerce_decimal, try_parse_canonical_decimal
from ...core.external_constants import UTF_8_ENCODING as _UTF_8
from ...domain.calculations.registry.export_parse import (
    SINO_DICTIONARY_TYPE,
    XML_DICTIONARY_BOOLEAN_TYPES,
    XmlDictionaryEntry,
    xml_dictionary_entries,
)
from ...domain.calculations.registry.schema_exports import ExportLayoutDefinition
from ...domain.calculations.registry.schema_references import SourceReference
from ...domain.contribuyente.renta_codes import modelo100_ccaa_codigo, modelo100_ecivil_export_code
from ...domain.filing.errors import FilingExportError, FilingExportValidationError
from ...domain.filing.schema import ModeloDraft
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

# The two boolean row types (``S_N``'s spelled-out ``SI``/``NO`` and ``LGC``'s
# ``tipo_logico`` pattern ``([0-1]){1}``) and their complete set are the one
# canonical declaration in ``domain.calculations.registry`` (``_export_parse.py``),
# imported above rather than re-declared here. Naming the set positively is what
# makes a boolean on any other row an error by default: a row type added to the
# dictionary later is simply not in it, so it refuses rather than inheriting
# whatever the last branch happened to do.

# The date row type, and the exact form AEAT accepts in it. The pattern is
# copied from the ``tipo_Fecha`` facet the bundled XSD declares -- an
# ``xs:string`` restricted to ``([0-9]{1,2}/[0-9]{1,2}/[0-9]{4})`` -- so day and
# month may be one or two digits and the year must be four. That is exactly what
# rendering a :class:`~datetime.date` below produces, which is why a value that
# arrives already typed never meets this check.
_DATE_DICTIONARY_TYPE = "FEC"
_DATE_DICTIONARY_TEXT = re.compile(r"[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}")

# The dictionary's numeric type codes are self-describing: ``P<width><scale>``
# and ``N<width><scale>`` name the field's integer width and its fractional-digit
# count, so the trailing digit is the scale to render at. Confirmed against every
# code the Modelo 100 dictionary uses across all six revisions by reading the
# ``fractionDigits`` facet of the XSD type each code lands on: ``P010``/``P020``/
# ``P030``/``P040`` resolve to ``xs:integer`` types carrying no fractional digits,
# while ``P012``/``P032``/``P072``/``P102``/``N102`` resolve to ``xs:decimal``
# types declaring ``fractionDigits="2"``. Reading the scale off the code keeps a
# future code correct without this module being edited.
_NUMERIC_DICTIONARY_TYPE = re.compile(r"^[NP]\d{2}(?P<scale>\d)$")


def render_xml_dictionary_layout(
    layout: ExportLayoutDefinition,
    *,
    draft: ModeloDraft,
    headers: Mapping[FilingProducerKey, object],
    dictionary_values: Mapping[str, object] | None = None,
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
        dictionary_values: Values addressed by the dictionary field id AEAT
            declares for them, each still carrying its own Python type. Absent
            (or ``None``) means the caller declares no such values, which is how
            every caller outside the work-unit export service reaches here.
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
    element_order = _xml_dictionary_element_order(
        _xml_dictionary_xsd_source(layout, schema_provider.sources),
        source_root=schema_provider.source_root,
    )
    _append_declaration_aux(root, layout)
    casilla_values: dict[CasillaId, object] = {value.casilla_id: value.value for value in draft.values}
    unfiled_paths: frozenset[str] = (
        _modelo_100_unfiled_comunidad_paths(entries, casilla_values)
        if draft.modelo == Modelo.M100
        else frozenset[str]()
    )
    for entry in entries:
        if entry.path in unfiled_paths:
            continue
        rendered = _xml_dictionary_rendered_value(
            entry,
            draft=draft,
            casilla_values=casilla_values,
            headers=headers,
            dictionary_values=dictionary_values or {},
        )
        if rendered is None or rendered == "":
            continue
        _set_xml_dictionary_path(root, entry.path, rendered, element_order=element_order)
    if draft.modelo == Modelo.M100:
        _stamp_toma_datos_nif(root, draft)
    rendered = ElementTree.tostring(root, encoding=_UTF_8, xml_declaration=True)
    assert isinstance(rendered, bytes)
    return rendered


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
    version = _latest_xml_dictionary_xsd_version(xsd_source, source_root=schema_provider.source_root)
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


def _xml_dictionary_xsd_root(source: SourceReference, *, source_root: Path | None) -> ElementTree.Element[str]:
    """Return the parsed root of the official XSD ``source`` names."""
    if source_root is None:
        raise FilingExportError(f"XML dictionary XSD source {source.id!r} requires source_root")
    try:
        root = DefusedElementTree.parse(source_root / source.corpus_path).getroot()
    except (DefusedElementTree.ParseError, OSError) as exc:
        raise FilingExportValidationError(f"XML dictionary XSD source {source.id!r} could not be parsed") from exc
    if root is None:
        raise FilingExportValidationError(f"XML dictionary XSD source {source.id!r} could not be parsed")
    return root


def _latest_xml_dictionary_xsd_version(source: SourceReference, *, source_root: Path | None) -> str:
    root = _xml_dictionary_xsd_root(source, source_root=source_root)
    versions: list[str] = []
    for simple_type in root.iter(f"{_XSD_NS}simpleType"):
        if simple_type.attrib.get("name") != "tipo_VersionXSD":
            continue
        for enumeration in simple_type.iter(f"{_XSD_NS}enumeration"):
            value = enumeration.attrib.get("value")
            if value:
                versions.append(value)
    if not versions:
        raise FilingExportValidationError(f"XML dictionary XSD source {source.id!r} declares no versionxsd values")
    return sorted(versions, key=lambda item: tuple(int(part) for part in item.split(".")))[-1]


def _append_declaration_aux(root: ElementTree.Element[str], layout: ExportLayoutDefinition) -> None:
    """Write the declaration's ``Aux`` identity block from the layout's declaration.

    The block is mandatory and first in every AEAT Modelo 100 XSD, and no bundled
    dictionary describes a single one of its rows, so it cannot be reached by the
    dictionary-driven walk that writes everything else here.

    Both children are ``minOccurs="1"``, so a block missing either is invalid and
    is not worth writing: when ``aux_version`` is undeclared this writes nothing,
    and :func:`~application.filing._export_parity.assert_xml_declaration_aux_declared` refuses
    the export at the write door rather than letting a partial block reach disk.
    """
    if layout.aux_idioma is None or layout.aux_version is None:
        return
    aux = ElementTree.SubElement(root, _AUX_TAG)
    ElementTree.SubElement(aux, "Idioma").text = layout.aux_idioma.value
    ElementTree.SubElement(aux, "VERSION").text = layout.aux_version


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
        if local_name == "element" and current.get("name"):
            found.append(current)
        elif local_name in _XSD_MODEL_GROUP_TAGS:
            pending = list(current) + pending
    return found


def _xml_dictionary_element_order(
    source: SourceReference,
    *,
    source_root: Path | None,
) -> dict[str, tuple[str, ...]]:
    """Return each element path's declared child order, read from the official XSD.

    AEAT declares the declaration body as ``xs:sequence``, so sibling order is
    part of the schema rather than a presentation choice. The dictionary's row
    order is NOT that order -- it lists ``CalculoImpuestoRes`` first under
    ``Resultados`` where the schema puts it twenty-fifth, and ``SEXO_D`` before
    ``ECIVIL`` under ``Declarante`` where the schema puts it after ``DPFNAC_D``.
    Appending each element as its dictionary row is reached therefore emits a
    document AEAT's own schema rejects, so the writer reads the order from the
    schema instead.

    The map is keyed by absolute path rather than by element name because a name
    is not unique across the document: the same tag recurs under different
    parents carrying different types, and a name-keyed map would silently apply
    one parent's order to another's children.

    Args:
        source: The layout's resolved XSD :class:`SourceReference`.
        source_root: Root the source's ``corpus_path`` resolves against.

    Returns:
        Absolute element path (``""`` for the root's own children) mapped to the
        child element names the schema declares under it, in declared order. A
        path the schema does not describe is absent, and the writer falls back to
        first-encounter order for it.

    Raises:
        FilingExportError: ``source_root`` is absent.
        FilingExportValidationError: The XSD could not be parsed, or declares no
            root ``Declaracion`` element to walk from.
    """
    root = _xml_dictionary_xsd_root(source, source_root=source_root)
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


def _record_xsd_child_order(
    path: str,
    type_node: ElementTree.Element[str] | None,
    *,
    named_types: Mapping[str, ElementTree.Element[str]],
    order: dict[str, tuple[str, ...]],
    seen: frozenset[str],
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
        child_path = f"{path}/{child.get('name')}"
        declared_type = child.get("type")
        if declared_type is None or declared_type not in named_types:
            _record_xsd_child_order(
                child_path,
                child.find(f"{_XSD_NS}complexType"),
                named_types=named_types,
                order=order,
                seen=seen,
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
            )


# The rows whose rendered text is a domain token that AEAT files under a code of
# its own: a comunidad reaches the export as ``andalucia`` where the schema
# enumerates ``01``-``20``, and a marital status as the profile's own value where
# the schema accepts Estado Civil ``1``-``4``.
#
# Applied AFTER :func:`_format_xml_dictionary_value` and never instead of it.
# That function owns how a value is written; this owns which official code the
# written value stands for. Collapsing the two would put a second formatting
# authority beside it, which is the thing this module keeps refusing to grow.
#
# A table rather than a branch per field. One special case reads as a special
# case, but the second starts a list and the third becomes a rule nobody finds by
# reading the function -- so the next such row is an entry here, not another
# ``elif``. Each converter is its own domain's authority for its code set,
# grounded in the same bundled XSD that constrains the attribute, so the mapping
# is declared once and consumed here rather than restated.
_MODELO_100_EXPORT_CODE_CONVERTERS: Mapping[str, Callable[[str], str]] = MappingProxyType(
    {
        "ECIVIL": modelo100_ecivil_export_code,
        "ZCCAD": modelo100_ccaa_codigo,
    },
)


def _xml_dictionary_rendered_value(
    entry: XmlDictionaryEntry,
    *,
    draft: ModeloDraft,
    casilla_values: dict[CasillaId, object],
    headers: Mapping[FilingProducerKey, object],
    dictionary_values: Mapping[str, object],
) -> str | None:
    raw = casilla_values.get(entry.casilla_id) if entry.casilla_id is not None else None
    if raw is None:
        raw = _xml_dictionary_non_casilla_value(entry, headers=headers, dictionary_values=dictionary_values)
    if raw is None:
        return None
    if draft.modelo == Modelo.M100:
        raw = _modelo_100_sign_branch_value(entry, raw)
    rendered = _format_xml_dictionary_value(entry.data_type, raw)
    converter = _MODELO_100_EXPORT_CODE_CONVERTERS.get(entry.field_id) if draft.modelo == Modelo.M100 else None
    if converter is not None:
        try:
            return converter(rendered)
        except ValueError as exc:
            raise FilingExportValidationError(str(exc)) from exc
    return rendered


# AEAT declares the fifteen autonomic-deduction blocks as an ``xs:choice``, so a
# declaration carries the filer's own comunidad and no other -- writing more than
# one is not merely wrong but a document the schema rejects. Each block also
# declares its deduction total against casilla 0564, so rendering every declared
# path for that casilla writes one comunidad's total into all fifteen.
#
# Which comunidad is the filer's is read from the draft rather than threaded in:
# every block owns between twelve and sixty casillas of its own, disjoint from
# 0564, so the block carrying any populated casilla is the one being filed. That
# is how a return is completed -- the filer fills their own anexo B -- rather than
# a proxy for it, and it needs no input the renderer does not already hold.
_MODELO_100_COMUNIDAD_BLOCK_PREFIX = "/DatosEconomicos/Resultados/DeduccionAutonomicaRes/"
_MODELO_100_SHARED_COMUNIDAD_TOTAL_CASILLA = "0564"


def _modelo_100_comunidad_block(path: str) -> str | None:
    """Return the comunidad block ``path`` sits in, or ``None`` when it is elsewhere."""
    if not path.startswith(_MODELO_100_COMUNIDAD_BLOCK_PREFIX):
        return None
    return path[len(_MODELO_100_COMUNIDAD_BLOCK_PREFIX) :].split("/", 1)[0]


def _modelo_100_casilla_is_populated(value: object) -> bool:
    """Return whether a CCAA casilla value selects a comunidad block.

    Calculated drafts carry zero-valued placeholders for every CCAA aggregate,
    sometimes as strings. Those placeholders are absent for the XSD ``choice``
    and must not select a block. A nonempty value that cannot be parsed remains
    populated so the later row formatter raises its typed validation error
    instead of silently suppressing the invalid input as if it were absent.
    """
    if value is None or value == "":
        return False
    amount = coerce_decimal(value)
    return amount is None or not amount.is_zero()


def _modelo_100_unfiled_comunidad_paths(
    entries: tuple[XmlDictionaryEntry, ...],
    casilla_values: Mapping[CasillaId, object],
) -> frozenset[str]:
    """Return the autonomic-deduction paths this draft must not write.

    Args:
        entries: Every dictionary row for the layout being rendered.
        casilla_values: Casilla values the draft carries.

    Returns:
        Paths belonging to a comunidad the draft does not file, plus the shared
        total when no comunidad is filed at all.

    Raises:
        FilingExportValidationError: when the draft populates casillas belonging
            to more than one comunidad. The schema admits only one, so there is
            no correct rendering and picking one would launder the conflict.
    """
    own_casillas_by_block: dict[str, set[CasillaId]] = {}
    for entry in entries:
        block = _modelo_100_comunidad_block(entry.path)
        if block is None or entry.casilla_id is None:
            continue
        if entry.casilla_id != _MODELO_100_SHARED_COMUNIDAD_TOTAL_CASILLA:
            own_casillas_by_block.setdefault(block, set()).add(entry.casilla_id)

    filed = sorted(
        block
        for block, own in own_casillas_by_block.items()
        if any(_modelo_100_casilla_is_populated(casilla_values.get(casilla)) for casilla in own)
    )
    if len(filed) > 1:
        raise FilingExportValidationError(
            "draft populates autonomic deductions for more than one comunidad "
            f"({', '.join(filed)}); a declaration may carry only one",
        )

    resident = filed[0] if filed else None
    unfiled = {
        entry.path
        for entry in entries
        if (block := _modelo_100_comunidad_block(entry.path)) is not None and block != resident
    }
    if resident is None:
        unfiled.update(
            entry.path for entry in entries if entry.casilla_id == _MODELO_100_SHARED_COMUNIDAD_TOTAL_CASILLA
        )
    return frozenset(unfiled)


# Casilla 0695 is declared against two sibling fields that are opposite branches
# of one quantity, not two copies of it:
#
#   TCPP112  "Resto a ingresar ... diferencia positiva o igual a cero"
#   TCNN112  "Resto ... cuya devolucion se solicita: diferencia negativa o igual a cero"
#
# Writing the casilla's value into both declares an amount to pay AND an amount to
# refund. Only the branch matching the value's sign carries it.
#
# Both fields are minOccurs=1 inside a minOccurs=0 parent, so the branch that does
# not apply is written as zero rather than omitted -- omitting it would render a
# CompensacionConyugesRes block the schema rejects. At zero the two rules coincide
# and both branches carry zero, so no tie-break is needed.
#
# Keyed on the field id rather than on the P102/N102 type codes: those do not
# encode a sign domain. Thirty-five P102 rows in the 2024 dictionary carry labels
# reading "negativa" (the perdida-patrimonial rows among them), and the reader
# parses both prefixes identically, so the codes agree with the branches here by
# coincidence rather than by rule.
_MODELO_100_NEGATIVE_SIGN_BRANCH_FIELDS: frozenset[str] = frozenset({"TCNN112"})
_MODELO_100_NON_NEGATIVE_SIGN_BRANCH_FIELDS: frozenset[str] = frozenset({"TCPP112"})


def _modelo_100_sign_branch_value(entry: XmlDictionaryEntry, raw: object) -> object:
    """Return ``raw`` for the sign branch it belongs to, and zero for the other.

    Args:
        entry: Dictionary row being rendered.
        raw: Value resolved for the row's casilla.

    Returns:
        ``raw`` when the row's branch matches its sign, ``Decimal("0")`` when the
        row is the opposite branch, and ``raw`` unchanged for every other row.

        A value that will not coerce carries no sign to route on, so it is read
        as zero for the purpose of choosing a branch. This selects a branch
        rather than validating a value: deciding what an uncoercible amount
        means is :func:`_format_xml_dictionary_value`'s job, and it is the job
        it does for every other casilla. Without the default, ``coerce_decimal``
        answers ``None`` and the comparison below raises ``TypeError`` on the
        export path.
    """
    negative_branch = entry.field_id in _MODELO_100_NEGATIVE_SIGN_BRANCH_FIELDS
    if not negative_branch and entry.field_id not in _MODELO_100_NON_NEGATIVE_SIGN_BRANCH_FIELDS:
        return raw
    amount = coerce_decimal(raw, default=Decimal("0"))
    return raw if (amount < 0) is negative_branch else Decimal("0")


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
    :func:`_format_xml_dictionary_value` can still decide ``SI``/``NO`` and
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


def _format_xml_dictionary_value(data_type: str, value: object) -> str:
    """Render one value in the form the dictionary row's declared type accepts.

    The row's ``data_type`` decides the rendering, not the Python type of the
    value. Deciding from the value alone cannot distinguish rows that happen to
    carry the same Python type but are declared differently by AEAT: every
    boolean rendered as ``"S"``/``"N"`` regardless of whether the row was
    ``tipo_logico`` (which accepts only ``0``/``1``) or ``tipo_SINO_Exclusivo``
    (only ``SI``/``NO``), and every numeric row was rendered with two decimals
    even where the row is an ``xs:integer``.

    Args:
        data_type: The dictionary row's declared type code.
        value: The scalar to render.

    Returns:
        The rendered text for the XML element or attribute.
    """
    normalized_type = data_type.upper()
    if isinstance(value, bool):
        # A boolean renders on exactly the two rows AEAT declares boolean, and is
        # a type error anywhere else. Stated this way round on purpose: asking
        # what the row IS keeps the declared type in charge, which is the rule
        # this whole function exists to enforce, while asking what it is NOT
        # inverts the dependency and leaves every unlisted row inheriting the
        # last branch by accident.
        #
        # The damage that makes this worth refusing rather than rendering is
        # clearest on an amount row: ``True`` on a euro-cent row reads as one
        # euro, the XSD accepts it, nothing on the export path validates anyway,
        # and a taxpayer files a figure they never stated. Same decision the
        # unreadable-amount branch below makes, for the same reason -- a wrong
        # number that satisfies every downstream check is worse than a refusal,
        # because the refusal is the only place the error is still visible.
        #
        # No route delivers a boolean here today: the casilla input door refuses
        # one for every declared family, and no Modelo 100 revision declares a
        # boolean casilla on a non-boolean row. This guards a route added later,
        # so it stays total and cheap rather than trying to interpret the value.
        if normalized_type not in XML_DICTIONARY_BOOLEAN_TYPES:
            raise FilingExportValidationError(
                f"a {data_type} row cannot carry the boolean {value!r}. Only "
                f"{'/'.join(sorted(XML_DICTIONARY_BOOLEAN_TYPES))} rows are declared boolean by AEAT. "
                "The value reaching this row has the wrong type; correct it at the source rather "
                "than rendering it, because a boolean written to an amount row is filed as 1 or 0.",
            )
        if normalized_type == SINO_DICTIONARY_TYPE:
            return "SI" if value else "NO"
        return "1" if value else "0"
    if isinstance(value, date):
        return f"{value.day}/{value.month}/{value.year}"
    numeric = _NUMERIC_DICTIONARY_TYPE.match(normalized_type)
    if numeric is not None:
        scale = int(numeric["scale"])
        # A text amount is read through the canonical grammar, which refuses on
        # two independent grounds and they are easy to confuse.
        #
        # The CAP is precision: at most ``scale`` fractional digits, never below
        # two. Capping an integer row at its own scale of zero would refuse
        # ``1.6``, unambiguous input this renderer has always rounded.
        #
        # The AMBIGUITY guard is separate and the row's scale does not relax it.
        # ``european_thousands_reading_is_ambiguous`` refuses a token that could
        # equally be read as a Spanish thousands group -- a lead of one to three
        # digits with no leading zero, then exactly three fractional digits. The
        # scale disambiguates the FIELD, never the STRING: an operator writing
        # one thousand types the same characters whatever the row declares, so
        # ``1.000`` refuses on a three-decimal row exactly as it does on a
        # euro-cent one. Tokens carrying their own evidence still parse at any
        # scale -- ``0.239`` (a lead of zero was never grouped) and ``1234.239``
        # (a four-digit lead would itself have been grouped).
        #
        # A value that already arrives typed carries no such ambiguity and skips
        # the text grammar entirely.
        amount = (
            try_parse_canonical_decimal(value, max_fraction_digits=max(scale, 2))
            if isinstance(value, str)
            else coerce_decimal(value)
        )
        if amount is None:
            raise FilingExportValidationError(
                f"amount for a {data_type} row could not be read: {value!r}. "
                f"The accepted form is a dot decimal separator with at most {scale} "
                "fractional digit(s) and no thousands grouping, e.g. 1234.56. A value "
                "is also refused when its shape cannot be told from a Spanish thousands "
                "group -- a lead of one to three digits with no leading zero, then "
                "exactly three more, as in 1.000 or 100.000 -- because that text reads "
                "as both one and one thousand and no parser can choose. This row's "
                "declared scale does not settle it: the scale says what the field can "
                "hold, not which reading was meant. Write the amount unambiguously "
                "(1000 or 1.0) at the source.",
            )
        return f"{amount.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)}"
    text = str(value).strip()
    if normalized_type == _DATE_DICTIONARY_TYPE and not _DATE_DICTIONARY_TEXT.fullmatch(text):
        # A date row reached by text rather than by a ``date``. The typed value
        # is rendered above and never arrives here, so this is the case where
        # something upstream held a date as a string -- and an ISO one renders
        # verbatim, which AEAT's own ``tipo_Fecha`` pattern rejects.
        #
        # Checked rather than parsed, deliberately. Reading ``03/04/2024`` would
        # mean choosing between day-month and month-day, and this renderer has
        # no basis for that choice; the numeric branch above refuses an
        # ambiguous amount for the same reason. Text already in AEAT's form
        # passes through untouched, so the check costs a correct caller nothing.
        raise FilingExportValidationError(
            f"date for a {data_type} row is not in the form AEAT accepts: {value!r}. "
            "The accepted form is d/m/yyyy with a four-digit year, e.g. 2/1/1980. "
            "Supply the value as a date rather than as text and it is rendered "
            "correctly without this check.",
        )
    return text


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
    parts = tuple(part for part in absolute_path.strip("/").split("/") if part)
    if not parts:
        raise FilingExportValidationError("XML dictionary entry path must not be empty")
    current = root
    current_path = ""
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
            child = ElementTree.Element(part)
            current.insert(_declared_child_position(current, part, element_order.get(current_path)), child)
        current = child
        current_path = f"{current_path}/{part}"
    current.text = value


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


__all__ = ["render_xml_dictionary_layout"]
