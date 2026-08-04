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
from collections.abc import Mapping
from datetime import date
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path
from xml.etree import ElementTree

from defusedxml import ElementTree as DefusedElementTree

from ...core import Modelo
from ...core.decimal import coerce_decimal
from ...core.external_constants import UTF_8_ENCODING as _UTF_8
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

_XSD_NS = "{http://www.w3.org/2001/XMLSchema}"

# The declaration's identity block. Mandatory and first in the ``Declaracion``
# sequence of every bundled AEAT Modelo 100 XSD, and absent from every bundled
# dictionary, so it is written from the layout rather than from a dictionary row.
_AUX_TAG = "Aux"

# Model groups carry no sibling position of their own when reading declared
# order: a declaration nested inside one sits at the position the group occupies
# in its parent, so the walk descends through them rather than treating them as
# elements.
_XSD_MODEL_GROUP_TAGS = frozenset({"complexType", "complexContent", "sequence", "choice", "all"})

# The one dictionary type whose boolean states are spelled out. Every other
# boolean-bearing row is ``tipo_logico``, whose pattern is ``([0-1]){1}``.
_SINO_DICTIONARY_TYPE = "S_N"

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
    headers: dict[str, str],
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
    normalized_headers = {key.lower(): value for key, value in headers.items()}
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
            headers=normalized_headers,
            dictionary_values=dictionary_values or {},
        )
        if rendered is None or rendered == "":
            continue
        _set_xml_dictionary_path(root, entry.path, rendered, element_order=element_order)
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
    and :func:`~application.filing.assert_xml_declaration_aux_declared` refuses
    the export at the write door rather than letting a partial block reach disk.
    """
    if layout.aux_idioma is None or layout.aux_version is None:
        return
    aux = ElementTree.SubElement(root, _AUX_TAG)
    ElementTree.SubElement(aux, "Idioma").text = layout.aux_idioma.value
    ElementTree.SubElement(aux, "VERSION").text = layout.aux_version


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
    named_types = {
        node.get("name"): node for node in root.iter(f"{_XSD_NS}complexType") if node.get("name") is not None
    }
    order: dict[str, tuple[str, ...]] = {}

    def walk(path: str, type_node: ElementTree.Element[str] | None, seen: frozenset[str]) -> None:
        if type_node is None or path in order:
            return
        children = _xsd_declared_children(type_node)
        if not children:
            return
        order[path] = tuple(str(child.get("name")) for child in children)
        for child in children:
            child_path = f"{path}/{child.get('name')}"
            declared_type = child.get("type")
            if declared_type is not None and declared_type in named_types:
                # A type that reaches itself would recurse without end; its
                # order is already recorded at the shallower path.
                if declared_type in seen:
                    continue
                walk(child_path, named_types[declared_type], seen | {declared_type})
            else:
                walk(child_path, child.find(f"{_XSD_NS}complexType"), seen)

    declaration = next(
        (node for node in root if node.tag == f"{_XSD_NS}element" and node.get("name") == _XML_DICTIONARY_ROOT_TAG),
        None,
    )
    if declaration is None:
        raise FilingExportValidationError(
            f"XML dictionary XSD source {source.id!r} declares no {_XML_DICTIONARY_ROOT_TAG!r} root element",
        )
    walk("", declaration.find(f"{_XSD_NS}complexType"), frozenset())
    return order


def _xml_dictionary_rendered_value(
    entry: XmlDictionaryEntry,
    *,
    draft: ModeloDraft,
    casilla_values: dict[CasillaId, object],
    headers: dict[str, str],
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
    if draft.modelo == Modelo.M100 and entry.field_id == "ECIVIL":
        try:
            return modelo100_ecivil_export_code(rendered)
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
        if any(casilla_values.get(casilla) is not None for casilla in own)
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
    headers: dict[str, str],
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
    declared = dictionary_values.get(entry.field_id)
    if declared is not None:
        return declared
    path_tail = entry.path.rsplit("/", 1)[-1].lstrip("@").lower()
    for key in (entry.field_id.lower(), path_tail):
        value = headers.get(key)
        if value is not None:
            return value
    return None


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
        if normalized_type == _SINO_DICTIONARY_TYPE:
            return "SI" if value else "NO"
        return "1" if value else "0"
    if isinstance(value, date):
        return f"{value.day}/{value.month}/{value.year}"
    numeric = _NUMERIC_DICTIONARY_TYPE.match(normalized_type)
    if numeric is not None:
        amount = coerce_decimal(value, default=Decimal("0")) or Decimal("0")
        scale = int(numeric["scale"])
        return f"{amount.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)}"
    return str(value).strip()


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
