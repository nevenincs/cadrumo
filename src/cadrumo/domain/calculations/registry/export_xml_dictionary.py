"""Parse official XML dictionaries and resolve their declared payload values."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from xml.etree.ElementTree import Element

from defusedxml import ElementTree

from ....core.casilla_id import CasillaId, validated_casilla_id
from ....core.decimal.coercion import normalize_decimal_separators
from .errors import RegistryValidationError
from .export_parse_models import ParsedExportFieldValue, ParsedExportPayload
from .schema_exports import ExportLayoutDefinition
from .schema_references import SourceReference

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
_DICTIONARY_LINE_RE = re.compile(
    r"^(?P<field>[^=#]+)=\[(?P<path>[^\]]*)\]\[(?P<type>[^\]]*)\]\[(?P<casilla>[^\]]*)\]\[(?P<label>.*)\]$",
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


def parse_xml_dictionary_payload(
    layout: ExportLayoutDefinition,
    payload: bytes,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
) -> ParsedExportPayload:
    """Parse the payload values named by the official dictionary and published overrides."""
    entries = xml_dictionary_entries(layout, sources=sources, source_payloads=source_payloads)
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
    casillas = tuple(value for value in parsed if value.casilla_id is not None)
    return ParsedExportPayload(layout_id=layout.id, fields=tuple(parsed), casillas=casillas)


def _xml_dictionary_source(
    layout: ExportLayoutDefinition,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
) -> tuple[SourceReference, bytes]:
    if layout.dictionary_source_ref is None:
        raise RegistryValidationError(f"XML export layout {layout.id!r} has no dictionary source")
    if sources is None or source_payloads is None:
        raise RegistryValidationError(f"XML export layout {layout.id!r} requires published sources and source payloads")
    source = sources.get(layout.dictionary_source_ref)
    if source is None:
        raise RegistryValidationError(
            f"XML export layout {layout.id!r} has unresolved dictionary source {layout.dictionary_source_ref!r}",
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
    )


def xml_dictionary_entries(
    layout: ExportLayoutDefinition,
    *,
    sources: Mapping[str, SourceReference] | None,
    source_payloads: Mapping[str, bytes] | None,
) -> tuple[XmlDictionaryEntry, ...]:
    """Resolve official AEAT XML dictionary :class:`XmlDictionaryEntry` rows for ``layout``."""
    source, dictionary_payload = _xml_dictionary_source(layout, sources=sources, source_payloads=source_payloads)
    # Applied here rather than at either consumer: the renderer and
    # :func:`parse_export_payload` both resolve their rows from this call, so a
    # correction reaching only one of them would make an exported artefact
    # verify as drift against itself.
    overrides = {override.field_id: override.path for override in layout.dictionary_path_overrides}
    entries: list[XmlDictionaryEntry] = []
    for line in decode_dictionary_text(dictionary_payload).splitlines():
        entry = _parse_xml_dictionary_line(line, source=source, overrides=overrides)
        if entry is not None:
            entries.append(entry)
    if not entries:
        raise RegistryValidationError(f"XML export layout {layout.id!r} dictionary has no parseable entries")
    _assert_every_override_was_applied(layout, entries)
    return tuple(entries)


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
