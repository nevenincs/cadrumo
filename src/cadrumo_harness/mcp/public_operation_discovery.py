"""Answer ``search`` and ``describe`` with no session, from the contracts shipped with this package.

Which operations exist and what each one takes is not a profile's data, and it
does not change while one version is installed. The command line shows its
commands and their arguments in its help with no sign-in and no runtime
running, and these two tools answer in the same conditions: the public
contract and request schema of every registered operation ship as data beside
this module and are read from there. A session reads the same contracts from
the runtime, which also holds it to its scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from functools import cache
from types import MappingProxyType
from typing import Any, Final

from cadrumo.adapters.local_runtime.frontend_client_contracts import RuntimeFrontendRefusedError
from cadrumo.application.operations.mcp_surfaces import McpSurface
from cadrumo.application.operations.registry import OperationPublicDefinitionDescriptionV1
from cadrumo.application.user_profile.access_contracts import AccessDenialCode

from .._resources import packaged_data
from .admitted_operations import described_reply
from .operation_discovery import search_public_operations
from .session_acts import NO_SESSION

SESSIONLESS_DISCOVERY_TOOLS: Final = frozenset({"search", "describe"})
"""The tools a connection with no session answers from the shipped contracts."""

CONTRACT_DOCUMENT_DIRECTORY: Final = "operation_contracts"
"""Where the contract document is, under this package's bundled data."""

CONTRACT_PART_SUFFIX: Final = ".jsonl"
"""What every part of the contract document is named with: one description on each line."""

_UTF_8: Final = "utf-8"
_LINE_END: Final = "\n"


def contract_part_name(definition_id: str) -> str:
    """Name the part of the document that holds one operation: its family, the first segment of its id."""
    return definition_id.split(".", 1)[0] + CONTRACT_PART_SUFFIX


def read_contract_part(text: str) -> tuple[OperationPublicDefinitionDescriptionV1, ...]:
    """Read one part back as the descriptions it holds, in the order it holds them."""
    return tuple(
        OperationPublicDefinitionDescriptionV1.model_validate_json(line) for line in text.split(_LINE_END) if line
    )


@cache
def shipped_public_descriptions() -> Mapping[str, OperationPublicDefinitionDescriptionV1]:
    """Return every shipped description by definition id, read on first use and kept.

    Raises:
        ValueError: The document is absent, or two of its lines describe one operation.
    """
    described: dict[str, OperationPublicDefinitionDescriptionV1] = {}
    root = packaged_data(CONTRACT_DOCUMENT_DIRECTORY)
    parts = sorted(
        (part for part in root.iterdir() if part.is_file() and part.name.endswith(CONTRACT_PART_SUFFIX)),
        key=lambda part: part.name,
    )
    for part in parts:
        for description in read_contract_part(part.read_text(encoding=_UTF_8)):
            definition_id = description.contract.definition_id
            if definition_id in described:
                raise ValueError(f"operation contract document describes one operation twice: {definition_id!r}")
            described[definition_id] = description
    if not described:
        raise ValueError("operation contract document is not shipped with this package")
    return MappingProxyType(described)


def discover_public_operations(name: str, args: dict[str, Any], surface: McpSurface) -> dict[str, Any]:
    """Answer ``search`` or ``describe`` for a connection that holds no session.

    The reply is the one a session gets, over every registered operation the
    surface keeps where a session's covers its scope, and it says so with
    ``session`` ``none``. An operation is refused as the runtime refuses it:
    outside the surface it is not this frontend's, and an id that names no
    registered operation is not one that may be described.
    """
    descriptions = shipped_public_descriptions()
    if name == "search":
        reply = search_public_operations(tuple(descriptions.values()), args, surface)
    else:
        definition_id = args["definition_id"]
        if not surface.admits(definition_id):
            raise RuntimeFrontendRefusedError(AccessDenialCode.FRONTEND_DENIED.value)
        description = descriptions.get(definition_id)
        if description is None:
            raise RuntimeFrontendRefusedError(AccessDenialCode.OPERATION_DENIED.value)
        reply = described_reply(description)
    reply["session"] = NO_SESSION
    return reply
