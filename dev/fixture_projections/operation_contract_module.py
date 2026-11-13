"""Write one TypeScript module of the registered request and result types of a set of operations.

A desktop contract producer names the operation definitions a family of the window reads. Each
definition's request and public result model, as the production operation registry binds them,
are rendered with ``dev.fixture_projections.typescript_wire_types`` into one module, and a type
map keyed by definition id closes it, so the window derives the type it needs from the operation
and not from a class name. A request is rendered as it is validated, so a field the model gives a
default may be left out of what the window sends.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Protocol, cast

from pydantic import BaseModel
from pydantic.json_schema import models_json_schema

from .typescript_wire_types import TypeScriptWriter, literal, omittable_fields, reach, ts_name


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


def render_contract_module(
    registry: PublicOperationRegistry, *, header: str, definitions: Sequence[str], contracts_name: str, subject: str
) -> str:
    """The module of ``definitions``: ``header``, one type per schema definition, then ``contracts_name``.

    ``contracts_name`` is the exported type map from each definition id to its ``request`` and ``result``
    types; ``subject`` names the family in that map's documentation.
    """
    roots = contract_roots(registry, definitions)
    sent = [model for _, role, model in roots if role == "request"]
    models = [(model, "serialization") for _, _, model in roots] + [(model, "validation") for model in sent]
    _, schema = models_json_schema(cast(Any, list(dict.fromkeys(models))), ref_template="#/$defs/{model}")
    defs: dict[str, Any] = schema["$defs"]
    received = reach(defs, (model.__name__ for _, role, model in roots if role != "request"))
    writer = TypeScriptWriter(
        defs,
        sent_only=reach(defs, (model.__name__ for model in sent)) - received,
        omittable=omittable_fields([model for _, _, model in roots], defs),
    )
    names = sorted((name for name in defs if not writer.inlined(name)), key=ts_name)
    blocks = [writer.definition(name) for name in names]
    by_definition: dict[str, list[tuple[str, str]]] = {}
    for definition_id, role, model in roots:
        by_definition.setdefault(definition_id, []).append((role, model.__name__))
    blocks.append(
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
    return header + "\n" + "\n\n".join(blocks) + "\n"
