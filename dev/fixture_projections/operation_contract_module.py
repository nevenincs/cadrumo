"""Write one TypeScript module of the registered request and result types of a set of operations.

A desktop contract producer names the operation definitions a family of the window reads. Each
definition's request and public result model, as the production operation registry binds them,
are rendered with ``dev.fixture_projections.typescript_wire_types`` into one module, and a type
map keyed by definition id closes it, so the window derives the type it needs from the operation
and not from a class name. A request is rendered as it is validated, so a field the model gives a
default may be left out of what the window sends. A property the window types with a name of its own,
such as a branded file token the host exchanges for a path, is named once in ``field_types`` and written
with that name in place of the wire's ``string``.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol, cast, override

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from .typescript_wire_types import TypeScriptWriter, literal, omittable_fields, reach, ts_name

_WINDOW_TYPE = "x-window-type"


@dataclass(frozen=True)
class WindowType:
    """A type the window defines and the generated module imports from ``module``."""

    name: str
    module: str


class _WindowTypeWriter(TypeScriptWriter):
    """A writer that gives a property marked with a window type that name in place of its ``string``."""

    @override
    def type_of(self, node: Mapping[str, Any]) -> str:
        """The TypeScript type of one schema node, with a marked node's ``string`` member renamed."""
        written = super().type_of(node)
        marked = node.get(_WINDOW_TYPE)
        if marked is None:
            return written
        members = written.split(" | ")
        if "string" not in members:
            raise SystemExit(f"{marked} stands for a string but the schema writes {written}")
        return " | ".join(marked if member == "string" else member for member in members)


def mark_window_types(defs: Mapping[str, Any], field_types: Mapping[tuple[str, str], WindowType]) -> None:
    """Mark each ``(definition, property)`` of ``field_types`` in ``defs``; one the schema lacks is refused."""
    for (definition, name), window_type in field_types.items():
        schema = defs.get(definition, {}).get("properties", {}).get(name)
        if schema is None:
            raise SystemExit(f"{window_type.name} is named for {definition}.{name}, which the schema does not define")
        schema[_WINDOW_TYPE] = window_type.name


def type_imports(field_types: Mapping[tuple[str, str], WindowType]) -> str:
    """The type-only import line of each module the window types come from, in module order."""
    named: dict[str, set[str]] = {}
    for window_type in field_types.values():
        named.setdefault(window_type.module, set()).add(window_type.name)
    return "".join(
        f"import type {{ {', '.join(sorted(names))} }} from {literal(module)};\n"
        for module, names in sorted(named.items())
    )


class PublicOperationRegistry(Protocol):
    """The two lookups of the production operation registry that bind an operation to its public models."""

    def lookup_public_contract(self, definition_id: str, /) -> Any:
        """The public contract registered under ``definition_id``."""
        ...

    def lookup_public_schema_binding(self, schema: Any, /) -> Any:
        """The binding of a public schema name to its model type."""
        ...


def contract_roots(
    registry: PublicOperationRegistry, definitions: Sequence[str]
) -> list[tuple[str, str, type[BaseModel]]]:
    """Each definition's registered request and public result model, as ``(definition, role, model)``."""
    roots: list[tuple[str, str, type[BaseModel]]] = []
    for definition_id in definitions:
        contract = registry.lookup_public_contract(definition_id)
        roots.append(
            (definition_id, "request", registry.lookup_public_schema_binding(contract.request_schema).model_type)
        )
        if contract.result_schema is None:
            raise SystemExit(f"{definition_id} registers no public result")
        roots.append(
            (definition_id, "result", registry.lookup_public_schema_binding(contract.result_schema).model_type)
        )
    return roots


def _schema_definitions(roots: list[tuple[str, str, type[BaseModel]]]) -> dict[str, Any]:
    """The JSON-schema definitions of every root model, as sent (validation) and as received (serialization)."""
    sent = [model for _, role, model in roots if role == "request"]
    models = [(model, "serialization") for _, _, model in roots] + [(model, "validation") for model in sent]
    _, schema = models_json_schema(cast(Any, list(dict.fromkeys(models))), ref_template="#/$defs/{model}")
    return schema["$defs"]


def _writer_for(
    roots: list[tuple[str, str, type[BaseModel]]], window_types: Mapping[tuple[str, str], WindowType]
) -> tuple[TypeScriptWriter, list[str]]:
    """The writer of the schema definitions the ``roots`` reach, and the names of those it writes."""
    defs = _schema_definitions(roots)
    sent = reach(defs, (model.__name__ for _, role, model in roots if role == "request"))
    mark_window_types(defs, window_types)
    received = reach(defs, (model.__name__ for _, role, model in roots if role != "request"))
    writer = _WindowTypeWriter(
        defs, sent_only=sent - received, omittable=omittable_fields([model for _, _, model in roots], defs)
    )
    return writer, sorted((name for name in defs if not writer.inlined(name)), key=ts_name)


def _contracts_type(roots: list[tuple[str, str, type[BaseModel]]], *, contracts_name: str, subject: str) -> str:
    """The exported type map from each definition id to the types of its ``request`` and ``result``."""
    by_definition: dict[str, list[tuple[str, str]]] = {}
    for definition_id, role, model in roots:
        by_definition.setdefault(definition_id, []).append((role, model.__name__))
    return (
        f"/** Each {subject} definition's registered request and result, as the runtime's\n"
        " * contract names them; a request names the profile the host fills. */\n"
        f"export type {contracts_name} = {{\n"
        + "\n".join(
            f"  {literal(definition_id)}: {{ "
            + " ".join(f"{role}: {ts_name(model_name)};" for role, model_name in parts)
            + " };"
            for definition_id, parts in sorted(by_definition.items())
        )
        + "\n};"
    )


def render_contract_module(
    registry: PublicOperationRegistry,
    *,
    header: str,
    definitions: Sequence[str],
    contracts_name: str,
    subject: str,
    field_types: Mapping[tuple[str, str], WindowType] | None = None,
) -> str:
    """The module of ``definitions``: ``header``, one type per schema definition, then ``contracts_name``.

    ``contracts_name`` is the exported type map from each definition id to its ``request`` and ``result``
    types; ``subject`` names the family in that map's documentation. ``field_types`` names, by schema
    definition and property, each string the window types with a name of its own.
    """
    window_types = field_types or {}
    roots = contract_roots(registry, definitions)
    writer, names = _writer_for(roots, window_types)
    blocks = [writer.definition(name) for name in names]
    blocks.append(_contracts_type(roots, contracts_name=contracts_name, subject=subject))
    return header + type_imports(window_types) + "\n" + "\n\n".join(blocks) + "\n"
