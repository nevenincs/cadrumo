"""Rank currently admitted public operation contracts by lexical relevance."""

from __future__ import annotations

import re
from collections.abc import Sequence

from pydantic import JsonValue

from cadrumo.application.command_search.index import CommandDoc, build_command_index
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1

_IDENTIFIER_SEPARATORS = re.compile(r"[._-]+")


def rank_operations(
    query: str, permitted: Sequence[OperationPublicDefinitionDescriptionV1]
) -> tuple[OperationPublicDefinitionDescriptionV1, ...]:
    """Order already-admitted descriptions by the canonical command-search ranker."""
    if not query.strip():
        return tuple(permitted)
    by_id = {description.contract.definition_id: description for description in permitted}
    index = build_command_index(_operation_search_document(description) for description in permitted)
    try:
        hits = index.search(query, limit=len(permitted))
    finally:
        index.close()
    return tuple(by_id[hit.command_key] for hit in hits)


def _operation_search_document(description: OperationPublicDefinitionDescriptionV1) -> CommandDoc:
    """Project one registered public contract onto the ranker's weighted columns."""
    contract = description.contract
    definition_id = str(contract.definition_id)
    prose, vocabulary = _schema_text(description.request_json_schema)
    action = contract.action_reference
    return CommandDoc(
        command_key=definition_id,
        tool_name="execute",
        key_and_name=f"{definition_id} {_split_identifier(definition_id)}",
        description=" ".join(prose),
        aliases="" if action is None else _split_identifier(str(action.action_id)),
        help=" ".join(vocabulary),
    )


def _schema_text(schema: JsonValue) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Collect a request schema's descriptions and its field and value vocabulary."""
    prose: list[str] = []
    vocabulary: list[str] = []
    pending: list[JsonValue] = [schema]
    while pending:
        node = pending.pop(0)
        if isinstance(node, list):
            pending.extend(node)
            continue
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if key == "description" and isinstance(value, str):
                prose.append(value)
            elif key == "properties" and isinstance(value, dict):
                vocabulary.extend(_split_identifier(name) for name in value)
                pending.extend(value.values())
            elif key in {"enum", "const"}:
                values = value if isinstance(value, list) else [value]
                vocabulary.extend(_split_identifier(item) for item in values if isinstance(item, str))
            else:
                pending.append(value)
    return tuple(prose), tuple(vocabulary)


def _split_identifier(value: str) -> str:
    return _IDENTIFIER_SEPARATORS.sub(" ", value).strip()
