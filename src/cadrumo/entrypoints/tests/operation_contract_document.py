"""Render the registered operations' public contracts as the document the MCP harness ships.

The harness answers ``search`` and ``describe`` for a connection with no
session and with no runtime running, as the command line's help lists its
commands. It answers from this document: the public contract and request
schema of every registered operation, as the production registry describes
them. One description is one line, and the operations of one family are one
part, so a contract that changes is one changed line of one small file.

The registry is the authority and the document is its copy. Run this module to
write the document again after an operation is added, removed, or its contract
or request changes::

    python -m cadrumo.entrypoints.tests.operation_contract_document
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Final

from cadrumo_harness.mcp.public_operation_discovery import (
    CONTRACT_DOCUMENT_DIRECTORY,
    CONTRACT_PART_SUFFIX,
    contract_part_name,
)

from ...application.operations.registry import OperationPublicDefinitionDescriptionV1, OperationRegistry
from ...tests.inventory import SRC_CADRUMO
from ..operation_composition import build_production_operation_registry

DOCUMENT_ROOT: Final[Path] = SRC_CADRUMO.parent / "cadrumo_harness" / "_data" / CONTRACT_DOCUMENT_DIRECTORY

_UTF_8: Final = "utf-8"
_LINE_END: Final = "\n"


def registered_descriptions(registry: OperationRegistry) -> tuple[OperationPublicDefinitionDescriptionV1, ...]:
    """Describe every operation of the registry's public contract set, in definition id order."""
    return tuple(
        registry.describe_public_definition(definition_id)
        for definition_id in sorted(contract.definition_id for contract in registry.public_contract_set.definitions)
    )


def _sorted_text(value: object) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _with_sets_in_order(wire: object, held: object) -> object:
    """Return a serialized value with every member its model holds as a set put in one order.

    A set is serialized in the order it happens to be walked, which differs
    from one process to the next. ``held`` is the same value as the model holds
    it, and is read only to tell a set from a sequence whose order means
    something.
    """
    if isinstance(wire, list) and isinstance(held, (set, frozenset)):
        return sorted(wire, key=_sorted_text)
    if isinstance(wire, dict) and isinstance(held, Mapping):
        return {
            key: _with_sets_in_order(value, held_value)
            for (key, value), held_value in zip(wire.items(), held.values(), strict=True)
        }
    if isinstance(wire, list) and isinstance(held, (list, tuple)):
        return [_with_sets_in_order(value, held_value) for value, held_value in zip(wire, held, strict=True)]
    return wire


def description_line(description: OperationPublicDefinitionDescriptionV1) -> str:
    """Render one description as its line: compact JSON in the model's own member order."""
    wire = _with_sets_in_order(description.model_dump(mode="json"), description.model_dump(mode="python"))
    return json.dumps(wire, separators=(",", ":"), ensure_ascii=False)


def render_contract_document(descriptions: Sequence[OperationPublicDefinitionDescriptionV1]) -> dict[str, str]:
    """Render the descriptions as the document: each part's file name and its text.

    Raises:
        ValueError: Two descriptions are of one operation.
    """
    ordered = sorted(descriptions, key=lambda description: description.contract.definition_id)
    definition_ids = [description.contract.definition_id for description in ordered]
    if len(set(definition_ids)) != len(definition_ids):
        raise ValueError("an operation is described once in the contract document")
    parts: dict[str, list[str]] = {}
    for description in ordered:
        parts.setdefault(contract_part_name(description.contract.definition_id), []).append(
            description_line(description)
        )
    return {name: "".join(line + _LINE_END for line in lines) for name, lines in sorted(parts.items())}


def shipped_contract_document() -> dict[str, str]:
    """Read every file the document's directory holds, by name, whether or not it is a part."""
    return {path.name: path.read_text(encoding=_UTF_8) for path in sorted(DOCUMENT_ROOT.iterdir()) if path.is_file()}


def main() -> int:
    """Write the document from the production registry, and drop the part of a family that is gone."""
    document = render_contract_document(registered_descriptions(build_production_operation_registry()))
    DOCUMENT_ROOT.mkdir(parents=True, exist_ok=True)
    for stale in sorted(DOCUMENT_ROOT.glob(f"*{CONTRACT_PART_SUFFIX}")):
        if stale.name not in document and stale.is_file():
            stale.unlink()
    for name, text in document.items():
        (DOCUMENT_ROOT / name).write_text(text, encoding=_UTF_8, newline=_LINE_END)
    operations = sum(text.count(_LINE_END) for text in document.values())
    print(f"wrote {DOCUMENT_ROOT} ({operations} operations in {len(document)} parts)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
