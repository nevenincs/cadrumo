"""Project operator mutability onto MCP tool annotations.

The capability manifest annotates each command family ``READ_ONLY`` or
``LOCAL_STATE_MUTATING``. MCP clients use ``ToolAnnotations`` hints
(``readOnlyHint`` / ``destructiveHint`` / ``idempotentHint``) to decide when to
ask a human before a tool runs. This module is the single mapping from the
backend mutability contract to those hints, plus the small, explicit set of verb
families that are destructive or naturally idempotent.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ...application.operator_surface import OperatorMutability

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

# Leaf verbs that destroy or irreversibly overwrite local state. A command key
# whose final segment is one of these is destructive regardless of its family.
_DESTRUCTIVE_LEAVES: frozenset[str] = frozenset(
    {"remove", "reset", "delete", "discard", "rekey", "recover", "logout", "clear", "merge", "stash"},
)
# Leaf verbs that are safe to repeat with the same effect (pure reads).
_IDEMPOTENT_LEAVES: frozenset[str] = frozenset(
    {"list", "show", "view", "status", "describe", "casillas", "history", "calendar", "agenda", "backlog"},
)


class McpAnnotations(BaseModel):
    """SDK-independent MCP tool annotations for one command.

    Maps to the MCP ``ToolAnnotations`` hint fields. ``read_only_hint`` mirrors the
    family mutability; ``destructive_hint`` is true only for irreversible
    state-destroying verbs; ``idempotent_hint`` is true for pure repeatable reads.
    """

    model_config = _STRICT_FROZEN

    title: str
    read_only_hint: bool
    destructive_hint: bool
    idempotent_hint: bool


def annotations_for_command(*, command_key: str, mutability: OperatorMutability, title: str) -> McpAnnotations:
    """Build the MCP annotations for one command key.

    Args:
        command_key: The registry command key (e.g. ``"ledger.remove"``).
        mutability: The owning family's mutability from the manifest.
        title: A human-readable tool title.

    Returns:
        :class:`McpAnnotations` for the command's MCP descriptor.
    """
    leaf = command_key.rsplit(".", 1)[-1]
    read_only = mutability is OperatorMutability.READ_ONLY
    destructive = (not read_only) and leaf in _DESTRUCTIVE_LEAVES
    idempotent = read_only or leaf in _IDEMPOTENT_LEAVES
    return McpAnnotations(
        title=title,
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
    )
