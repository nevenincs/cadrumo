"""Hold every value of an XML declaration to what its official XSD declares.

The dictionary says where a value goes; only the XSD says how long it may be, which
amounts its type admits and which characters it accepts. Every limit here is read
from that XSD for the edition being exported, so an edition that moves a limit moves
this check with it, and a facet this module cannot apply refuses rather than passes.

The check walks the finished document, not the values on their way in. Zero-only
optional branches have been pruned by then, so a retained calculation placeholder no
file will carry is not refused, and whatever reached the document by any route is
held to the same limits. Export and verification share this one walk.

The XSD is also what decides letter case. Every free-text type in the official
schemas spells its alphabet in capitals, while an operator types ordinary text, so
:func:`canonical_xml_text` capitalizes a value only when its declared type refuses it
as written and admits it capitalized. Nothing else is rewritten: a character the type
does not admit in either case is refused, never dropped or replaced.

A filer's export is also held to each element's declared content, by a walk of its own:
a required child or attribute the document lacks refuses by its box, because padding
cannot supply a fact and a block without its required content is a file AEAT's own
schema rejects. It is separate because only a work-unit export states a whole return;
a bare draft render and a file read back are judged on their values alone.

Refusals name the box and the limit and never carry the value, which may be private.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from xml.etree.ElementTree import Element

from ...core.type_guards import is_object_mapping
from ...domain.calculations.registry.export_xml_dictionary import XmlDictionaryEntry
from .errors import ModeloApplicationError

XSD_NS = "{http://www.w3.org/2001/XMLSchema}"

_MODEL_GROUP_TAGS = frozenset({"complexType", "complexContent", "sequence", "choice", "all"})

_VALUE_REFUSAL_PREFIX = "application.filing.export.errors.xml_value_"
_REQUIRED_MISSING = "application.filing.export.errors.xml_value_required_missing"

_CONTENT_GROUP_TAGS = frozenset({"sequence", "choice", "all"})

# The negative token of the schemas' ``tipo_SINO_Exclusivo``.
_SCHEMA_NEGATIVE_ANSWER = "NO"

#: The facets this check applies. Any other refuses the type, so a limit a later
#: edition adds in a form this module does not know is never silently passed.
_KNOWN_FACETS = frozenset(
    {
        "whiteSpace",
        "length",
        "maxLength",
        "minInclusive",
        "maxInclusive",
        "fractionDigits",
        "enumeration",
        "pattern",
    }
)

_XSD_STRING = "xs:string"
_XSD_INTEGER = "xs:integer"
_XSD_DECIMAL = "xs:decimal"
_XSD_NUMERIC_BASES = frozenset({_XSD_INTEGER, _XSD_DECIMAL})
_XSD_BASES = frozenset({_XSD_STRING, *_XSD_NUMERIC_BASES})

# The lexical spaces XML Schema Part 2 gives its two numeric primitives.
_LEXICAL_NUMBERS = {
    _XSD_INTEGER: re.compile(r"[+-]?[0-9]+"),
    _XSD_DECIMAL: re.compile(r"[+-]?([0-9]+(\.[0-9]*)?|\.[0-9]+)"),
}
# The XML 1.0 ``Char`` production. Nothing outside it can be carried by the file at
# all, whatever a type's own facets say.
_NOT_XML_CHAR = re.compile("[^\t\n\r\x20-퟿-�\U00010000-\U0010ffff]")


@dataclass(frozen=True, slots=True)
class _SimpleType:
    """The facets of one restriction, already parsed."""

    base: str
    white_space: str | None = None
    length: int | None = None
    max_length: int | None = None
    min_inclusive: Decimal | None = None
    max_inclusive: Decimal | None = None
    fraction_digits: int | None = None
    enumeration: frozenset[str] = frozenset()
    patterns: tuple[re.Pattern[str], ...] = ()


@dataclass(frozen=True, slots=True)
class _Violation:
    """One value outside its type, addressed by the absolute path that holds it."""

    path: str
    translated_message: str
    limit: str | None = None
    observed: int | None = None


@dataclass(slots=True)
class XmlValueSchema:
    """Named types of one XSD, with each simple type parsed the first time it is met."""

    source_id: str
    root_tag: str
    declaration: Element[str]
    complex_types: Mapping[str, Element[str]]
    simple_type_nodes: Mapping[str, Element[str]]
    simple_types: dict[str, _SimpleType] = field(default_factory=dict)

    def simple_type(self, name: str) -> _SimpleType:
        """Return the facets of the type called ``name``, a named type or an XSD primitive."""
        known = self.simple_types.get(name)
        if known is not None:
            return known
        if name in _XSD_BASES:
            parsed = _SimpleType(base=name)
        else:
            node = self.simple_type_nodes.get(name)
            if node is None:
                raise _schema_unreadable(self.source_id, name)
            parsed = _parse_simple_type(node, source_id=self.source_id, name=name)
        self.simple_types[name] = parsed
        return parsed


def is_xml_value_refusal(error: BaseException) -> bool:
    """Say whether ``error`` refuses one box, which the modelo export boundary shows as it is.

    Its generic write failure would misreport a value the schema refuses as a disk problem.
    """
    translated_message = getattr(error, "translated_message", None)
    return isinstance(translated_message, str) and translated_message.startswith(_VALUE_REFUSAL_PREFIX)


def is_xml_required_content_refusal(error: BaseException) -> bool:
    """Say whether ``error`` refuses a declaration for lacking content its schema requires."""
    translated_message = getattr(error, "translated_message", None)
    return isinstance(translated_message, str) and translated_message == _REQUIRED_MISSING


def refused_xml_boxes(error: BaseException) -> tuple[str, ...]:
    """Return every box a value or required-content refusal names, in the order it lists them.

    Verification reads a refusal through this rather than walking the document again,
    so the two cannot come to different answers about the same declaration.
    """
    context = getattr(error, "context", None)
    if not is_object_mapping(context):
        return ()
    listed = context.get("refused_boxes", context.get("box"))
    return tuple(str(listed).split(", ")) if listed is not None else ()


def xsd_declared_children(node: Element[str]) -> list[Element[str]]:
    """Return ``node``'s child element declarations in the order the schema writes them.

    Descends through the model-group wrappers (``sequence``, ``choice``, ``all``)
    that carry no ordering meaning of their own here, so a declaration nested one
    or more groups deep is still found at its true sibling position. Descent stops
    at the first ``element`` on each branch: that element's own children belong to
    its path, not to ``node``'s.
    """
    found: list[Element[str]] = []
    pending = list(node)
    while pending:
        current = pending.pop(0)
        # A comment or processing instruction carries a callable tag rather than
        # a name; rendering it to text simply matches nothing below.
        local_name = str(current.tag).rpartition("}")[2]
        if local_name == "element" and bool(current.get("name")):
            found.append(current)
        elif local_name in _MODEL_GROUP_TAGS:
            pending = list(current) + pending
    return found


def xml_value_schema(schema: Element[str], *, source_id: str, root_tag: str) -> XmlValueSchema:
    """Read one official XSD for checking and normalizing the values of ``root_tag``.

    Args:
        schema: The parsed XSD of the edition being exported.
        source_id: Registry id of that XSD, named when it cannot be applied.
        root_tag: The document element the XSD must declare.

    Returns:
        The parsed :class:`XmlValueSchema`.

    Raises:
        ModeloApplicationError: The XSD declares no such document element.
    """
    declaration = next(
        (node for node in schema if node.tag == f"{XSD_NS}element" and node.get("name") == root_tag),
        None,
    )
    if declaration is None:
        raise _schema_unreadable(source_id, root_tag)
    return XmlValueSchema(
        source_id=source_id,
        root_tag=root_tag,
        declaration=declaration,
        complex_types={
            name: node for node in schema.iter(f"{XSD_NS}complexType") if (name := node.get("name")) is not None
        },
        simple_type_nodes={
            name: node for node in schema.iter(f"{XSD_NS}simpleType") if (name := node.get("name")) is not None
        },
    )


def canonical_xml_text(schema: XmlValueSchema, path: str, text: str) -> str:
    """Return ``text`` in the case the type declared at ``path`` admits.

    Export and verification both call this, so a capitalized file still matches the
    draft holding the text as the operator typed it.

    Args:
        schema: The edition's :class:`XmlValueSchema`.
        path: The dictionary path of the value.
        text: The rendered value.

    Returns:
        The capitalized text when only that form is admitted; otherwise ``text``
        unchanged, for the check over the finished document to judge.
    """
    capitalized = text.upper()
    if capitalized == text or _capitalizes_into_ascii(text):
        return text
    declared = _simple_type_at(schema, path)
    if declared is None or _alphabet_admits(declared, text) or not _alphabet_admits(declared, capitalized):
        return text
    return capitalized


def _capitalizes_into_ascii(text: str) -> bool:
    """Whether a non-ASCII character capitalizes into one plain letter, as dotless i into I and long s into S.

    That letter could then pass a code type as a different code, and the XSD patterns do not tell a code from a name.
    The text stays as typed, so the check over the finished document refuses it.
    """
    return any(
        not character.isascii() and len(capital := character.upper()) == 1 and capital.isascii() for character in text
    )


def _simple_type_at(schema: XmlValueSchema, path: str) -> _SimpleType | None:
    current = schema.declaration
    for part in _document_path(path, root_tag=schema.root_tag).strip("/").split("/"):
        complex_type = _declared_complex_type(current, schema)
        if complex_type is None:
            return None
        declared = (
            {item.get("name"): item for item in complex_type.findall(f"{XSD_NS}attribute")}.get(part[1:])
            if part.startswith("@")
            else {item.get("name"): item for item in xsd_declared_children(complex_type)}.get(part)
        )
        if declared is None:
            return None
        current = declared
    return None if _declared_complex_type(current, schema) is not None else _declared_simple_type(current, schema)


def _alphabet_admits(declared: _SimpleType, text: str) -> bool:
    if declared.enumeration:
        return text in declared.enumeration
    return not declared.patterns or any(pattern.fullmatch(text) for pattern in declared.patterns)


def refuse_xml_values_outside_schema(
    document: Element[str],
    *,
    schema: Element[str],
    source_id: str,
    entries: Iterable[XmlDictionaryEntry],
) -> None:
    """Refuse a declaration holding any value its official XSD does not admit.

    Args:
        document: The finished ``Declaracion`` element, as rendered or as read back.
        schema: The parsed XSD of the edition being exported.
        source_id: Registry id of that XSD, named when it cannot be applied.
        entries: The edition's dictionary rows, which give each path its box.

    Raises:
        ModeloApplicationError: A value breaks a facet, or sits where the XSD
            declares nothing. The first one sets the message and every box refused
            is listed, so one export names all there is to correct. Also raised
            when the XSD uses a construct this check cannot apply.
    """
    parsed = xml_value_schema(schema, source_id=source_id, root_tag=document.tag)
    violations = tuple(_element_violations(document, parsed.declaration, path="", schema=parsed))
    if violations:
        raise _refusal(violations, entries=entries, root_tag=document.tag)


def _element_violations(
    node: Element[str], declaration: Element[str], *, path: str, schema: XmlValueSchema
) -> Iterator[_Violation]:
    complex_type = _declared_complex_type(declaration, schema)
    if complex_type is None:
        yield from _undeclared_children(node, path)
        simple = _declared_simple_type(declaration, schema)
        if simple is not None:
            yield from _value_violations(node.text or "", simple, path=path)
        return
    yield from _attribute_violations(node, complex_type, path=path, schema=schema)
    children = {item.get("name"): item for item in xsd_declared_children(complex_type)}
    for child in node:
        child_path = f"{path}/{child.tag}"
        child_declaration = children.get(child.tag)
        if child_declaration is None:
            yield _Violation(
                path=child_path, translated_message="application.filing.export.errors.xml_value_undeclared"
            )
        else:
            yield from _element_violations(child, child_declaration, path=child_path, schema=schema)


def _attribute_violations(
    node: Element[str], complex_type: Element[str], *, path: str, schema: XmlValueSchema
) -> Iterator[_Violation]:
    """Validate the attributes declared on this complex type in document order."""
    attributes = {item.get("name"): item for item in complex_type.findall(f"{XSD_NS}attribute")}
    for name, value in node.attrib.items():
        # A namespaced attribute such as ``xsi:noNamespaceSchemaLocation`` belongs to
        # XML Schema itself, not to the type.
        if name.startswith("{"):
            continue
        attribute = attributes.get(name)
        attribute_path = f"{path}/@{name}"
        if attribute is None:
            yield _Violation(
                path=attribute_path, translated_message="application.filing.export.errors.xml_value_undeclared"
            )
            continue
        simple = _declared_simple_type(attribute, schema)
        if simple is not None:
            yield from _value_violations(value, simple, path=attribute_path)


def refuse_xml_missing_required_content(
    document: Element[str],
    *,
    schema: Element[str],
    source_id: str,
    entries: Iterable[XmlDictionaryEntry],
) -> None:
    """Refuse a finished declaration lacking a child or attribute its official XSD requires.

    Args:
        document: The finished ``Declaracion`` element.
        schema: The parsed XSD of the edition being exported.
        source_id: Registry id of that XSD, named when it cannot be applied.
        entries: The edition's dictionary rows, which give each path its box.

    Raises:
        ModeloApplicationError: Required content is absent. The first sets the message
            and every box refused is listed.
    """
    parsed = xml_value_schema(schema, source_id=source_id, root_tag=document.tag)
    violations = tuple(_content_violations(document, parsed.declaration, path="", schema=parsed))
    if violations:
        raise _refusal(violations, entries=entries, root_tag=document.tag)


def _content_violations(
    node: Element[str], declaration: Element[str], *, path: str, schema: XmlValueSchema
) -> Iterator[_Violation]:
    complex_type = _declared_complex_type(declaration, schema)
    if complex_type is None:
        return
    yield from _missing_content_violations(node, complex_type, path=path)
    declared = {item.get("name"): item for item in xsd_declared_children(complex_type)}
    for child in node:
        child_declaration = declared.get(child.tag)
        if child_declaration is not None:
            yield from _content_violations(child, child_declaration, path=f"{path}/{child.tag}", schema=schema)


def _missing_content_violations(node: Element[str], complex_type: Element[str], *, path: str) -> Iterator[_Violation]:
    """Report the required attributes and child elements ``node`` does not hold."""
    for attribute in complex_type.findall(f"{XSD_NS}attribute"):
        name = attribute.get("name")
        if attribute.get("use") == "required" and name is not None and name not in node.attrib:
            yield _Violation(path=f"{path}/@{name}", translated_message=_REQUIRED_MISSING)
    for name in _missing_required_children(complex_type, frozenset(str(child.tag) for child in node)):
        yield _Violation(path=f"{path}/{name}", translated_message=_REQUIRED_MISSING)


def _missing_required_children(complex_type: Element[str], present: frozenset[str]) -> tuple[str, ...]:
    """Return the child elements the content model of ``complex_type`` still requires."""
    return tuple(
        name
        for particle in complex_type
        if _local_name(particle) in _CONTENT_GROUP_TAGS
        for name in _particle_missing(particle, present)
    )


def _particle_missing(particle: Element[str], present: frozenset[str]) -> Iterator[str]:
    """Walk one particle; an optional group or a choice requires only what it has begun."""
    local_name = _local_name(particle)
    if local_name == "element":
        if _element_missing(particle, present):
            yield str(particle.get("name"))
        return
    if not _particle_touched(particle, present) and particle.get("minOccurs", "1") == "0":
        return
    for member in _walked_members(particle, present):
        yield from _particle_missing(member, present)


def _walked_members(particle: Element[str], present: frozenset[str]) -> tuple[Element[str], ...]:
    """Return the members a group requires: all of a sequence, only the begun branch of a choice.

    A choice with no begun branch is satisfied when any branch requires nothing, so
    it then requires nothing; otherwise it is reported through its first branch.
    """
    members = tuple(item for item in particle if _local_name(item) in {"element", *_CONTENT_GROUP_TAGS})
    if _local_name(particle) == "choice":
        touched = tuple(item for item in members if _particle_touched(item, present))
        if touched:
            return touched[:1]
        if any(next(_particle_missing(item, present), None) is None for item in members):
            return ()
        return members[:1]
    return members


def _element_missing(particle: Element[str], present: frozenset[str]) -> bool:
    name = particle.get("name")
    return name is not None and name not in present and particle.get("minOccurs", "1") != "0"


def _particle_touched(particle: Element[str], present: frozenset[str]) -> bool:
    if _local_name(particle) == "element":
        return particle.get("name") in present
    return any(
        _particle_touched(item, present) for item in particle if _local_name(item) in {"element", *_CONTENT_GROUP_TAGS}
    )


def _local_name(node: Element[str]) -> str:
    return str(node.tag).rpartition("}")[2]


def prune_childless_negative_blocks(document: Element[str], *, schema: XmlValueSchema) -> None:
    """Remove an optional block holding only ``NO`` answers and lacking its required content.

    Such a block states an absence the schema can only express by leaving the block
    out: ``Hijos`` admits its flag only alongside the ``Hijo`` occurrences it requires.
    A block answering ``SI`` is a stated fact and stays, for the check to refuse.

    Args:
        document: The ``Declaracion`` element, after zero-only pruning.
        schema: The edition's :class:`XmlValueSchema`.
    """
    _prune_negative_children(document, schema.declaration, schema=schema)


def _prune_negative_children(node: Element[str], declaration: Element[str], *, schema: XmlValueSchema) -> None:
    complex_type = _declared_complex_type(declaration, schema)
    if complex_type is None:
        return
    declared = {item.get("name"): item for item in xsd_declared_children(complex_type)}
    for child in tuple(node):
        child_declaration = declared.get(child.tag)
        if child_declaration is None:
            continue
        _prune_negative_children(child, child_declaration, schema=schema)
        if child_declaration.get("minOccurs", "1") == "0" and _is_unfillable_negative(child, child_declaration, schema):
            node.remove(child)


def _is_unfillable_negative(node: Element[str], declaration: Element[str], schema: XmlValueSchema) -> bool:
    complex_type = _declared_complex_type(declaration, schema)
    return (
        complex_type is not None
        and len(node) == 0
        and bool(node.attrib)
        and all(value == _SCHEMA_NEGATIVE_ANSWER for value in node.attrib.values())
        and bool(_missing_required_children(complex_type, frozenset()))
    )


def _undeclared_children(node: Element[str], path: str) -> Iterator[_Violation]:
    for child in node:
        yield _Violation(
            path=f"{path}/{child.tag}", translated_message="application.filing.export.errors.xml_value_undeclared"
        )
    for name in node.attrib:
        if not name.startswith("{"):
            yield _Violation(
                path=f"{path}/@{name}", translated_message="application.filing.export.errors.xml_value_undeclared"
            )


def _declared_complex_type(declaration: Element[str], schema: XmlValueSchema) -> Element[str] | None:
    declared = declaration.get("type")
    if declared is not None:
        return schema.complex_types.get(declared)
    return declaration.find(f"{XSD_NS}complexType")


def _declared_simple_type(declaration: Element[str], schema: XmlValueSchema) -> _SimpleType | None:
    """Return the facets on a declaration, or ``None`` for one that declares no type at all."""
    declared = declaration.get("type")
    if declared is not None:
        return schema.simple_type(declared)
    inline = declaration.find(f"{XSD_NS}simpleType")
    if inline is None:
        return None
    return _parse_simple_type(inline, source_id=schema.source_id, name=str(declaration.get("name")))


def _parse_simple_type(node: Element[str], *, source_id: str, name: str) -> _SimpleType:
    restrictions = node.findall(f"{XSD_NS}restriction")
    base = restrictions[0].get("base") if len(restrictions) == 1 else None
    if base is None or base not in _XSD_BASES:
        raise _schema_unreadable(source_id, name)
    facets = [item for item in restrictions[0] if not str(item.tag).endswith("annotation")]
    if any(str(item.tag).removeprefix(XSD_NS) not in _KNOWN_FACETS for item in facets):
        raise _schema_unreadable(source_id, name)
    try:
        return _SimpleType(
            base=base,
            white_space=_single_facet(facets, "whiteSpace"),
            length=_optional(_single_facet(facets, "length"), int),
            max_length=_optional(_single_facet(facets, "maxLength"), int),
            min_inclusive=_optional(_single_facet(facets, "minInclusive"), Decimal),
            max_inclusive=_optional(_single_facet(facets, "maxInclusive"), Decimal),
            fraction_digits=_optional(_single_facet(facets, "fractionDigits"), int),
            enumeration=frozenset(_facet_values(facets, "enumeration")),
            # ASCII because XML Schema's whitespace class is four characters, not Unicode's.
            patterns=tuple(re.compile(value, re.ASCII) for value in _facet_values(facets, "pattern")),
        )
    except (ArithmeticError, ValueError, re.error) as exc:
        raise _schema_unreadable(source_id, name) from exc


def _facet_values(facets: Iterable[Element[str]], name: str) -> Iterator[str]:
    tag = f"{XSD_NS}{name}"
    return (str(item.get("value", "")) for item in facets if item.tag == tag)


def _single_facet(facets: Iterable[Element[str]], name: str) -> str | None:
    return next(_facet_values(facets, name), None)


def _optional[T](value: str | None, parse: Callable[[str], T]) -> T | None:
    return None if value is None else parse(value)


def _value_violations(raw: str, declared: _SimpleType, *, path: str) -> Iterator[_Violation]:
    text = " ".join(raw.split()) if declared.base in _XSD_NUMERIC_BASES or declared.white_space == "collapse" else raw
    if _NOT_XML_CHAR.search(text) is not None:
        yield _Violation(path=path, translated_message="application.filing.export.errors.xml_value_illegal_characters")
        return
    if declared.base in _XSD_NUMERIC_BASES:
        yield from _numeric_violations(text, declared, path=path)
    else:
        yield from _length_violations(text, declared, path=path)
    if not _alphabet_admits(declared, text):
        if declared.enumeration:
            yield _Violation(path=path, translated_message="application.filing.export.errors.xml_value_not_listed")
        else:
            yield _Violation(
                path=path, translated_message="application.filing.export.errors.xml_value_illegal_characters"
            )


def _length_violations(text: str, declared: _SimpleType, *, path: str) -> Iterator[_Violation]:
    if declared.length is not None and len(text) != declared.length:
        yield _Violation(
            path=path,
            translated_message="application.filing.export.errors.xml_value_wrong_length",
            limit=str(declared.length),
            observed=len(text),
        )
    if declared.max_length is not None and len(text) > declared.max_length:
        yield _Violation(
            path=path,
            translated_message="application.filing.export.errors.xml_value_too_long",
            limit=str(declared.max_length),
            observed=len(text),
        )


def _numeric_violations(text: str, declared: _SimpleType, *, path: str) -> Iterator[_Violation]:
    if _LEXICAL_NUMBERS[declared.base].fullmatch(text) is None:
        yield _Violation(path=path, translated_message="application.filing.export.errors.xml_value_not_a_number")
        return
    amount = Decimal(text)
    if declared.max_inclusive is not None and amount > declared.max_inclusive:
        yield _Violation(
            path=path,
            translated_message="application.filing.export.errors.xml_value_above_maximum",
            limit=str(declared.max_inclusive),
        )
    if declared.min_inclusive is not None and amount < declared.min_inclusive:
        yield _Violation(
            path=path,
            translated_message="application.filing.export.errors.xml_value_below_minimum",
            limit=str(declared.min_inclusive),
        )
    # Trailing zeros are not digits of the value: XML Schema reads 1.500 as 1.5.
    decimals = len(text.partition(".")[2].rstrip("0"))
    if declared.fraction_digits is not None and decimals > declared.fraction_digits:
        yield _Violation(
            path=path,
            translated_message="application.filing.export.errors.xml_value_too_many_decimals",
            limit=str(declared.fraction_digits),
            observed=decimals,
        )


def _refusal(
    violations: tuple[_Violation, ...], *, entries: Iterable[XmlDictionaryEntry], root_tag: str
) -> ModeloApplicationError:
    entries_by_path: dict[str, XmlDictionaryEntry] = {}
    for entry in entries:
        path = _document_path(entry.path, root_tag=root_tag)
        held = entries_by_path.get(path)
        if held is None or (held.casilla_id is None and entry.casilla_id is not None):
            entries_by_path[path] = entry
    boxes = tuple(dict.fromkeys(_box(item.path, entries_by_path) for item in violations))
    first = violations[0]
    context: dict[str, object] = {"box": _box(first.path, entries_by_path)}
    entry = entries_by_path.get(first.path)
    if entry is not None:
        context["field_id"] = entry.field_id
    if first.limit is not None:
        context["limit"] = first.limit
    if first.observed is not None:
        context["observed"] = first.observed
    if len(boxes) > 1:
        context["refused_boxes"] = ", ".join(boxes)
    return ModeloApplicationError(translated_message=first.translated_message, context=context)


def _box(path: str, entries_by_path: Mapping[str, XmlDictionaryEntry]) -> str:
    """Name a path by its casilla; a row with none goes by AEAT's field id, and an unlisted one by its path."""
    entry = entries_by_path.get(path)
    if entry is None:
        return path
    return str(entry.casilla_id) if entry.casilla_id is not None else entry.field_id


def _document_path(path: str, *, root_tag: str) -> str:
    parts = [part for part in path.split("/") if part]
    if parts and parts[0] == root_tag:
        parts = parts[1:]
    return "".join(f"/{part}" for part in parts)


def _schema_unreadable(source_id: str, type_name: str) -> ModeloApplicationError:
    return ModeloApplicationError(
        translated_message="application.filing.export.errors.xml_schema_unreadable",
        context={"source_id": source_id, "type_name": type_name},
    )


__all__ = [
    "XSD_NS",
    "XmlValueSchema",
    "canonical_xml_text",
    "is_xml_required_content_refusal",
    "is_xml_value_refusal",
    "prune_childless_negative_blocks",
    "refuse_xml_missing_required_content",
    "refuse_xml_values_outside_schema",
    "refused_xml_boxes",
    "xml_value_schema",
    "xsd_declared_children",
]
