"""Write the window's TypeScript wire types from the JSON schema of the Python models that own them.

The desktop's contract producers render each schema definition as one TypeScript type with this
module: field names, nullity and closed vocabularies as the application serialises them, a field
optional only where the model's own ``exclude_if`` leaves it out of the wire or, for what the
window sends, where the model gives it a default. Each producer chooses its roots and lays the
written types out in modules of its own.
"""

from __future__ import annotations

import json
import re
import textwrap
from collections.abc import Iterable, Iterator, Mapping
from typing import Annotated, Any, TypeAliasType, cast, get_args, get_origin

from pydantic import BaseModel


def models_in(annotation: object) -> Iterator[type[BaseModel]]:
    """The Pydantic models an annotation names, through unions, containers, ``Annotated`` and ``type`` aliases."""
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        yield annotation
        return
    if isinstance(annotation, TypeAliasType):
        yield from models_in(annotation.__value__)
        return
    origin = get_origin(annotation)
    if isinstance(origin, TypeAliasType):
        yield from models_in(origin.__value__)
    if get_origin(annotation) is Annotated:
        yield from models_in(get_args(annotation)[0])
        return
    for argument in get_args(annotation):
        yield from models_in(argument)


def omittable_fields(roots: Iterable[type[BaseModel]], defs: Mapping[str, Any]) -> dict[str, frozenset[str]]:
    """Each definition's fields the wire can leave out, from the models' own serialisation config.

    A field with an ``exclude_if`` predicate is left out of the serialised record whenever the predicate
    holds, so its generated property is optional whatever its default. The definition is named as the
    JSON schema names it: the class name, with a parametrised generic's brackets read as underscores. A model
    carrying such a field that the schema does not define is refused rather than left required.
    """
    seen: dict[str, type[BaseModel]] = {}
    pending = list(roots)
    while pending:
        model = pending.pop()
        name = re.sub(r"[^A-Za-z0-9_]", "_", model.__name__)
        if name in seen:
            if seen[name] is not model:
                raise SystemExit(f"two models are both named {name}")
            continue
        seen[name] = model
        for found in model.model_fields.values():
            pending.extend(models_in(found.annotation))
    omittable: dict[str, frozenset[str]] = {}
    for name, model in seen.items():
        fields = frozenset(key for key, found in model.model_fields.items() if found.exclude_if is not None)
        if not fields:
            continue
        if name not in defs:
            raise SystemExit(f"{name} leaves out {sorted(fields)} but the schema does not define it")
        omittable[name] = fields
    return omittable


def ts_name(name: str) -> str:
    """A schema definition's TypeScript name: the class name without a private underscore."""
    return name.lstrip("_")


def refs(node: object) -> Iterator[str]:
    """The definition names a schema node refers to, at any depth."""
    if isinstance(node, dict):
        mapping = cast(dict[str, object], node)
        ref = mapping.get("$ref")
        if isinstance(ref, str):
            yield ref.rsplit("/", 1)[-1]
        for value in mapping.values():
            yield from refs(value)
    elif isinstance(node, list):
        for value in cast(list[object], node):
            yield from refs(value)


def reach(defs: Mapping[str, Any], start: Iterable[str]) -> set[str]:
    """The definitions reachable from ``start``, ``start`` included."""
    seen: set[str] = set()
    pending = list(start)
    while pending:
        name = pending.pop()
        if name in seen:
            continue
        seen.add(name)
        pending.extend(refs(defs[name]))
    return seen


def literal(value: object) -> str:
    """A JSON value as a TypeScript literal."""
    return json.dumps(value, ensure_ascii=False)


_SCALAR_TYPES = {"string": "string", "integer": "number", "number": "number", "boolean": "boolean", "null": "null"}


class TypeScriptWriter:
    """Render JSON-schema definitions as TypeScript types, one per definition."""

    def __init__(
        self, defs: Mapping[str, Any], *, sent_only: set[str], omittable: Mapping[str, frozenset[str]]
    ) -> None:
        """Write ``defs``, leaving out of each type the fields the wire may omit.

        A definition in ``sent_only`` is only sent, so its fields with defaults may be left out;
        ``omittable`` names each definition's fields the model's own ``exclude_if`` leaves out.
        """
        self._defs = defs
        self._sent_only = sent_only
        self._omittable = omittable
        #: The definitions named by what was written since the last ``definition`` call began.
        self.named: set[str] = set()

    def inlined(self, name: str) -> bool:
        """A private constrained scalar is written where it is used."""
        node = self._defs[name]
        return name.startswith("_") and "properties" not in node and "enum" not in node

    def type_of(self, node: Mapping[str, Any]) -> str:
        """The TypeScript type of one schema node."""
        if "$ref" in node:
            return self._reference_type(node["$ref"])
        if "const" in node:
            return literal(node["const"])
        if "enum" in node:
            return " | ".join(literal(value) for value in node["enum"])
        for key in ("anyOf", "oneOf"):
            if key in node:
                return self._union_type(node[key])
        kind = node.get("type")
        if kind == "array":
            return self._array_type(node)
        if kind == "object":
            return self._map_type(node)
        return self._scalar_type(kind)

    def _scalar_type(self, kind: object) -> str:
        """A scalar ``type``, or the union of a list of types each written as its own node."""
        if isinstance(kind, list):
            return " | ".join(self.type_of({"type": each}) for each in cast(list[str], kind))
        return _SCALAR_TYPES.get(cast(str, kind), "unknown")

    def _reference_type(self, reference: str) -> str:
        """A ``$ref``: the referenced scalar written in place, else the definition's name."""
        name = reference.rsplit("/", 1)[-1]
        if self.inlined(name):
            return self.type_of(self._defs[name])
        self.named.add(name)
        return ts_name(name)

    def _union_type(self, alternatives: Iterable[Mapping[str, Any]]) -> str:
        """The members of an ``anyOf``/``oneOf``, each written once, in schema order."""
        members: list[str] = []
        for member in alternatives:
            rendered = self.type_of(member)
            if rendered not in members:
                members.append(rendered)
        return " | ".join(members)

    def _array_type(self, node: Mapping[str, Any]) -> str:
        """A tuple for ``prefixItems``, else an array of the item type, parenthesised when it is a union."""
        if "prefixItems" in node:
            return "[" + ", ".join(self.type_of(item) for item in node["prefixItems"]) + "]"
        item = self.type_of(node.get("items", {}))
        return f"({item})[]" if " | " in item else f"{item}[]"

    def _map_type(self, node: Mapping[str, Any]) -> str:
        """A string-keyed record of the ``additionalProperties`` type, ``unknown`` when it is not a schema."""
        values = node.get("additionalProperties")
        value = self.type_of(values) if isinstance(values, dict) else "unknown"
        return f"{{ [key: string]: {value} }}"

    def definition(self, name: str) -> str:
        """The exported TypeScript type of definition ``name``, with its docstring as JSDoc."""
        self.named = set()
        node = self._defs[name]
        lines = jsdoc(node.get("description"), indent="")
        if "properties" not in node:
            lines.append(f"export type {ts_name(name)} = {self.type_of(node)};")
            return "\n".join(lines)
        required = set(node.get("required", ()))
        optional_absent = name in self._sent_only
        lines.append(f"export type {ts_name(name)} = {{")
        for prop, schema in node["properties"].items():
            lines.extend(jsdoc(schema.get("description"), indent="  "))
            absent = (optional_absent and prop not in required) or prop in self._omittable.get(name, ())
            mark = "?" if absent else ""
            lines.append(f"  {prop}{mark}: {self.type_of(schema)};")
        lines.append("};")
        return "\n".join(lines)


_ROLE = re.compile(r":[a-z]+:`~?\.?([^`]+)`")


def jsdoc(text: object, *, indent: str) -> list[str]:
    """A Python docstring as a JSDoc block: roles and double backticks read as plain code spans."""
    if not isinstance(text, str) or not text.strip():
        return []
    plain = _ROLE.sub(lambda found: "`" + found.group(1).rsplit(".", 1)[-1] + "`", text).replace("``", "`")
    plain = plain.replace("*/", "*\\/")
    paragraphs = [" ".join(part.split()) for part in plain.strip().split("\n\n") if part.strip()]
    body: list[str] = []
    for index, paragraph in enumerate(paragraphs):
        if index:
            body.append("")
        body.extend(textwrap.wrap(paragraph, width=76 - len(indent)))
    return [f"{indent}/**", *(f"{indent} * {line}".rstrip() for line in body), f"{indent} */"]


__all__ = [
    "TypeScriptWriter",
    "jsdoc",
    "literal",
    "models_in",
    "omittable_fields",
    "reach",
    "refs",
    "ts_name",
]
