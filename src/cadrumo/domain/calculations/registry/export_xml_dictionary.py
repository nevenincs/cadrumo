"""Parse official XML dictionaries and resolve their declared payload values."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.decimal.coercion import normalize_decimal_separators
from .errors import RegistryValidationError
from .export_parse_models import ParsedExportFieldValue, ParsedExportPayload
from .schema_exports import ExportLayoutDefinition, XmlDictionaryRowTarget
from .schema_references import SourceReference
from .schema_surfaces import CasillaDefinition

# The dictionary's two boolean row types. ``LGC`` resolves to the XSD's
# ``tipo_logico`` (``0``/``1``) and ``S_N`` to ``tipo_SINO_Exclusivo``
# (``NO``/``SI``); the tokens differ but both rows carry a boolean. Public: this
# is the one canonical declaration of the vocabulary. The application-layer XML
# dictionary renderer (``_export_xml_dictionary.py``) shares the exact same two
# type codes for the write direction and imports them from this defining module
# rather than re-declaring its own copy.
LOGICAL_DICTIONARY_TYPE = "LGC"
SINO_DICTIONARY_TYPE = "S_N"
# Named as a set rather than matched by prefix so a future type code beginning
# with the same letter is not silently read as a boolean.
XML_DICTIONARY_BOOLEAN_TYPES = frozenset({LOGICAL_DICTIONARY_TYPE, SINO_DICTIONARY_TYPE})
# The input dictionaries print an optional ``{group}`` heading between the casilla
# and the label; no declaration dictionary carries one.
_DICTIONARY_LINE_RE = re.compile(
    r"^(?P<field>[^=#]+)=\[(?P<path>[^\]]*)\]\[(?P<type>[^\]]*)\]\[(?P<casilla>[^\]]*)\]"
    r"(?:\{[^}]*\})?\[(?P<label>.*)\]$",
)
_DICTIONARY_NUMERIC_CASILLA_ID_RE = re.compile(r"^\d+$")
_DICTIONARY_LETTER_CASILLA_ID_RE = re.compile(r"^[A-Z]$")


@dataclass(frozen=True, slots=True)
class XmlDictionaryEntry:
    """One field mapping from an official AEAT XML dictionary source."""

    field_id: str
    path: str
    data_type: str
    casilla_id: CasillaId | None
    """The casilla this row reads: the one the edition's registry declares for the row.

    It is the printed number only when the registry holds no casilla under that
    number; see :func:`xml_dictionary_entries` for how the rest are resolved.
    """

    printed_number: CasillaId | None = None
    """The box number the dictionary prints on this row, unresolved."""


def parse_xml_dictionary_payload(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
    casillas: Iterable[CasillaDefinition],
    admitted_entries: tuple[XmlDictionaryEntry, ...] = (),
) -> ParsedExportPayload:
    """Parse the payload values named by the official dictionary and published overrides.

    ``admitted_entries`` are the input-dictionary rows the caller admitted for the
    layout's repeated records; they are read beside the declaration dictionary's
    rows and never in place of one.
    """
    entries = (
        *xml_dictionary_entries(layout, sources=sources, source_payloads=source_payloads, casillas=casillas),
        *admitted_entries,
    )
    try:
        root = ElementTree.fromstring(payload)
    except ElementTree.ParseError as exc:
        raise RegistryValidationError(f"XML export layout {layout.id!r} could not parse payload") from exc

    parsed: list[ParsedExportFieldValue] = []
    for entry in entries:
        for index, text in enumerate(_xml_dictionary_path_values(root, entry.path), start=1):
            raw = text.strip()
            if not raw:
                continue
            parsed.append(
                ParsedExportFieldValue(
                    record_id="xml",
                    field_id=entry.field_id,
                    casilla_id=entry.casilla_id,
                    raw=raw,
                    value=_parse_xml_dictionary_value(entry.data_type, raw),
                    source_locator=f"{layout.id}:{entry.path}:{index}",
                ),
            )
    casilla_values = tuple(value for value in parsed if value.casilla_id is not None)
    return ParsedExportPayload(layout_id=layout.id, fields=tuple(parsed), casillas=casilla_values)


def _xml_dictionary_source(
    layout: ExportLayoutDefinition,
    reference: str | None,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
) -> tuple[SourceReference, bytes]:
    if reference is None:
        raise RegistryValidationError(f"XML export layout {layout.id!r} has no dictionary source")
    if sources is None or source_payloads is None:
        raise RegistryValidationError(f"XML export layout {layout.id!r} requires published sources and source payloads")
    source = sources.get(reference)
    if source is None:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} has unresolved dictionary source {reference!r}",
        )
    try:
        return source, source_payloads[source.id]
    except KeyError as exc:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} has no published payload for dictionary source {source.id!r}"
        ) from exc


def _parse_xml_dictionary_line(
    line: str,
    *,
    source: SourceReference,
    overrides: Mapping[str, str],
) -> XmlDictionaryEntry | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    match = _DICTIONARY_LINE_RE.match(stripped)
    if match is None:
        return None
    casilla_id = _parse_dictionary_casilla_id(
        match["casilla"],
        allow_letter_id=source.supports_single_uppercase_letter_casilla_ids,
    )
    field_id = match["field"].strip()
    return XmlDictionaryEntry(
        field_id=field_id,
        path=overrides.get(field_id, match["path"].strip()),
        data_type=match["type"].strip(),
        casilla_id=casilla_id,
        printed_number=casilla_id,
    )


def xml_dictionary_entries(
    layout: ExportLayoutDefinition,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
    casillas: Iterable[CasillaDefinition],
) -> tuple[XmlDictionaryEntry, ...]:
    """Resolve official AEAT XML dictionary :class:`XmlDictionaryEntry` rows for ``layout``.

    Each row reads the one casilla of ``casillas`` whose ``number`` equals the
    number the dictionary prints, with ``segmento`` unset. A declared
    :class:`XmlDictionaryRowTarget` overrides that lookup for its row. A printed
    number the registry holds under more than one casilla, on a row with no
    target, is refused rather than resolved by order or by id. A number the
    registry holds under no casilla is kept as printed.
    """
    source, dictionary_payload = _xml_dictionary_source(
        layout, layout.dictionary_source_ref, sources=sources, source_payloads=source_payloads
    )
    # Applied here rather than at either consumer: the renderer and
    # :func:`parse_export_payload` both resolve their rows from this call, so a
    # correction reaching only one of them would make an exported artefact
    # verify as drift against itself.
    overrides = {override.field_id: override.path for override in layout.dictionary_path_overrides}
    targets = {target.field_id: target for target in layout.dictionary_row_targets}
    declared = tuple(casillas)
    casilla_ids_by_number = _casilla_ids_by_printed_number(declared)
    entries: list[XmlDictionaryEntry] = []
    line_fields: dict[int, str] = {}
    for line_number, line in enumerate(decode_dictionary_text(dictionary_payload).splitlines(), start=1):
        row = _parse_xml_dictionary_line(line, source=source, overrides=overrides)
        if row is None:
            continue
        line_fields[line_number] = row.field_id
        entries.append(
            _resolve_row_casilla(
                layout,
                row,
                target=targets.get(row.field_id),
                casilla_ids_by_number=casilla_ids_by_number,
            ),
        )
    if not entries:
        raise RegistryValidationError(f"XML export layout {layout.id!r} dictionary has no parseable entries")
    _assert_every_override_was_applied(layout, entries)
    _assert_every_row_target_is_grounded(
        layout,
        entries,
        line_fields=line_fields,
        declared_casillas={casilla.id: casilla for casilla in declared},
        sources=sources,
        source_payloads=source_payloads,
    )
    return tuple(entries)


def _casilla_ids_by_printed_number(casillas: Iterable[CasillaDefinition]) -> Mapping[str, tuple[CasillaId, ...]]:
    """Index the ids of segment-less casillas by the number the dictionary prints for them."""
    by_number: dict[str, list[CasillaId]] = {}
    for casilla in casillas:
        if casilla.segmento is None:
            by_number.setdefault(casilla.number, []).append(casilla.id)
    return {number: tuple(ids) for number, ids in by_number.items()}


def _resolve_row_casilla(
    layout: ExportLayoutDefinition,
    row: XmlDictionaryEntry,
    *,
    target: XmlDictionaryRowTarget | None,
    casilla_ids_by_number: Mapping[str, tuple[CasillaId, ...]],
) -> XmlDictionaryEntry:
    """Return ``row`` reading the casilla its target or its printed number names."""
    printed = row.printed_number
    if target is not None:
        resolved: CasillaId | None = target.casilla_id
    elif printed is None:
        resolved = None
    else:
        holders = casilla_ids_by_number.get(printed, ())
        if len(holders) > 1:
            raise RegistryValidationError(
                f"XML export layout {layout.id!r} dictionary row {row.field_id!r} prints box {printed!r}, "
                f"which the registry holds under {sorted(holders)!r}; declare the casilla the row reads "
                "as a dictionary row target",
            )
        resolved = holders[0] if holders else printed
    return XmlDictionaryEntry(
        field_id=row.field_id,
        path=row.path,
        data_type=row.data_type,
        casilla_id=resolved,
        printed_number=printed,
    )


def _assert_every_row_target_is_grounded(
    layout: ExportLayoutDefinition,
    entries: list[XmlDictionaryEntry],
    *,
    line_fields: Mapping[int, str],
    declared_casillas: Mapping[CasillaId, CasillaDefinition],
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
) -> None:
    """Refuse a row target its dictionary, its casilla or its XSD does not bear out.

    A target is a claim that a specific published row reads a specific casilla.
    It is held to the row it names: the row must exist at the cited line, print
    the number of the casilla it targets, and its XSD element must exist.
    """
    rows = {entry.field_id: entry for entry in entries}
    for target in layout.dictionary_row_targets:
        row = rows.get(target.field_id)
        if row is None:
            raise RegistryValidationError(
                f"XML export layout {layout.id!r} declares a dictionary row target for {target.field_id!r}, "
                "which the official dictionary does not declare, so the target would apply to nothing",
            )
        if line_fields.get(target.dictionary_line) != target.field_id:
            raise RegistryValidationError(
                f"XML export layout {layout.id!r} row target {target.field_id!r} cites dictionary line "
                f"{target.dictionary_line}, which does not hold that row",
            )
        casilla = declared_casillas.get(target.casilla_id)
        if casilla is None:
            raise RegistryValidationError(
                f"XML export layout {layout.id!r} row target {target.field_id!r} names casilla "
                f"{target.casilla_id!r}, which the edition does not declare",
            )
        if casilla.segmento is not None or casilla.number != row.printed_number:
            raise RegistryValidationError(
                f"XML export layout {layout.id!r} row target {target.field_id!r} prints box "
                f"{row.printed_number!r}, which is not the number of casilla {target.casilla_id!r} "
                f"({casilla.number!r})",
            )
        _assert_xsd_declares_element(layout, target, sources=sources, source_payloads=source_payloads)


def _assert_xsd_declares_element(
    layout: ExportLayoutDefinition,
    target: XmlDictionaryRowTarget,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
) -> None:
    """Refuse a target whose cited XSD declares no such element.

    A reader holding only the dictionary (the form-layout generator) cannot
    judge the XSD, so the element is checked wherever the XSD payload is
    supplied, which every export and verification path does.
    """
    if sources is None or source_payloads is None:
        return
    source = sources.get(target.xsd_source_ref)
    payload = source_payloads.get(source.id) if source is not None else None
    if payload is None:
        return
    declaration = f'name="{target.xsd_element}"'.encode()
    if declaration not in payload:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} row target {target.field_id!r} cites XSD element "
            f"{target.xsd_element!r}, which {target.xsd_source_ref!r} does not declare",
        )


def xml_input_dictionary_entries(
    layout: ExportLayoutDefinition,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
) -> tuple[XmlDictionaryEntry, ...]:
    """Read every :class:`XmlDictionaryEntry` row of the layout's input dictionary; none when it names none.

    These rows are an offer, not a layout: the caller admits only those a
    repeated record needs, after checking them against the edition's XSD and the
    declaration dictionary. The declaration dictionary's path overrides do not
    apply here, because they correct rows of that dictionary only.
    """
    if layout.input_dictionary_source_ref is None:
        return ()
    source, dictionary_payload = _xml_dictionary_source(
        layout, layout.input_dictionary_source_ref, sources=sources, source_payloads=source_payloads
    )
    entries = tuple(
        entry
        for line in decode_dictionary_text(dictionary_payload).splitlines()
        if (entry := _parse_xml_dictionary_line(line, source=source, overrides={})) is not None
    )
    if not entries:
        raise RegistryValidationError(f"XML export layout {layout.id!r} input dictionary has no parseable entries")
    return entries


def _assert_every_override_was_applied(
    layout: ExportLayoutDefinition,
    entries: list[XmlDictionaryEntry],
) -> None:
    """Refuse an override naming a field this dictionary does not carry.

    An override is a claim that a specific published row is wrong. If the row is
    absent -- a typo, or a revision where AEAT never declared the field -- the
    correction silently applies to nothing and the defect it was written for goes
    on shipping, with a declaration in the registry that reads as if it were
    fixed. Refusing at read time makes that impossible to leave in place.
    """
    declared = {entry.field_id for entry in entries}
    unmatched = sorted(
        override.field_id for override in layout.dictionary_path_overrides if override.field_id not in declared
    )
    if unmatched:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} declares dictionary path overrides for {unmatched!r}, "
            "which the official dictionary does not declare, so the correction would apply to nothing",
        )


def decode_dictionary_text(body: bytes) -> str:
    """Decode publisher-projected dictionary bytes without a filesystem read."""
    try:
        return body.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return body.decode("cp1252")
        except UnicodeDecodeError as exc:
            raise RegistryValidationError("XML dictionary is neither UTF-8 nor CP1252") from exc


def _parse_dictionary_casilla_id(value: str, *, allow_letter_id: bool = False) -> CasillaId | None:
    """Return the exact official casilla identifier a dictionary row declares.

    Official dictionaries print decimal box numbers, and some reviewed sources
    additionally publish one-uppercase-letter annex boxes. ``###`` and ``*``
    rows are explicit non-casilla placeholders. The source's typed grammar
    capability, declared alongside its digest-pinned corpus identity and
    temporal applicability, is the one authority that admits the extension; a
    numeric-only source cannot smuggle an unevidenced identifier in.

    The parser preserves the published spelling: it does not fold case,
    normalize arbitrary alphanumeric labels, or manufacture an identifier from a
    source-row placeholder.
    """
    text = value.strip()
    if not text or text.startswith("*"):
        return None
    is_numeric = _DICTIONARY_NUMERIC_CASILLA_ID_RE.fullmatch(text) is not None
    is_grounded_letter = allow_letter_id and _DICTIONARY_LETTER_CASILLA_ID_RE.fullmatch(text) is not None
    if not is_numeric and not is_grounded_letter:
        return None
    return validated_casilla_id(text, surface="XML dictionary casilla id")


def _find_xml_path(root: Element[str], absolute_path: str) -> tuple[Element[str], ...]:
    parts = _xml_path_parts(absolute_path)
    if not parts:
        return ()
    current: tuple[Element[str], ...] = (root,)
    for index, part in enumerate(parts):
        current = _advance_xml_path(current, part, is_root_segment=index == 0)
        if not current:
            return ()
    return current


def _xml_dictionary_path_values(root: Element[str], absolute_path: str) -> tuple[str, ...]:
    """Read element text or the final attribute explicitly named by a dictionary row."""
    parts = _xml_path_parts(absolute_path)
    if parts and parts[-1].startswith("@"):
        attribute = parts[-1][1:]
        parents = _find_xml_path(root, "/".join(parts[:-1]))
        return tuple(element.attrib[attribute] for element in parents if attribute in element.attrib)
    return tuple(element.text or "" for element in _find_xml_path(root, absolute_path))


def _xml_path_parts(absolute_path: str) -> tuple[str, ...]:
    """Return non-empty local-name segments from an absolute XML path."""
    return tuple(part for part in absolute_path.strip("/").split("/") if part)


def _advance_xml_path(
    current: tuple[Element[str], ...],
    part: str,
    *,
    is_root_segment: bool,
) -> tuple[Element[str], ...]:
    """Advance one XML path segment, retaining the root-name shortcut."""
    if is_root_segment and len(current) == 1 and _local_name(current[0].tag) == part:
        return current
    next_elements: list[Element[str]] = []
    for element in current:
        next_elements.extend(child for child in element if _local_name(child.tag) == part)
    return tuple(next_elements)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _parse_xml_dictionary_value(data_type: str, raw: str) -> Decimal | str | bool | None:
    """Read one dictionary value back as the type its row declares.

    Both boolean row types are read as booleans. They differ only in the tokens
    AEAT spells them with -- ``LGC`` rows carry ``0``/``1`` and ``S_N`` rows carry
    ``NO``/``SI`` -- which is a spelling difference, not a difference in what the
    row means. Reading one as a boolean and the other as text made the two halves
    of this boundary disagree about an ``S_N`` row: the writer emitted a marker
    for a boolean casilla and the reader handed back a string, so a comparison
    against the draft saw ``True`` on one side and ``"SI"`` on the other and
    reported drift on a file that matched.
    """
    normalized = data_type.upper()
    if normalized.startswith(("N", "P")):
        return _parse_xml_decimal(raw)
    if normalized in XML_DICTIONARY_BOOLEAN_TYPES:
        return _parse_xml_boolean(normalized, raw)
    return raw


def _parse_xml_decimal(raw: str) -> Decimal:
    text = normalize_decimal_separators(raw.strip(), strip_thousands=False)
    if not text:
        return Decimal("0")
    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise RegistryValidationError("XML dictionary numeric value contains invalid decimal data") from exc


_XML_BOOLEAN_TOKENS = {
    LOGICAL_DICTIONARY_TYPE: {"1": True, "0": False},
    SINO_DICTIONARY_TYPE: {"si": True, "no": False},
}


def _parse_xml_boolean(data_type: str, raw: str) -> bool | None:
    """Parse the official XML-dictionary boolean vocabulary only."""
    if not raw or not raw.strip():
        return None
    normalized = data_type.upper()
    tokens = _XML_BOOLEAN_TOKENS.get(normalized)
    if tokens is None:
        raise RegistryValidationError(f"unsupported XML dictionary boolean data type {data_type!r}")
    token = raw.strip().lower()
    try:
        return tokens[token]
    except KeyError as exc:
        raise RegistryValidationError(
            f"XML dictionary boolean field {normalized!r} contains invalid data",
        ) from exc
