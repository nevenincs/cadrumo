"""Project operator mutability onto MCP tool annotations.

The capability manifest annotates each command family ``READ_ONLY`` or
``LOCAL_STATE_MUTATING``. MCP clients use ``ToolAnnotations`` hints
(``readOnlyHint`` / ``destructiveHint`` / ``idempotentHint``) to decide when to
ask a human before a tool runs. This module is the single mapping from the
backend mutability contract to those hints, plus the small, explicit set of verb
families that are destructive or naturally idempotent.

It also owns the annotation-coverage contract: :func:`annotations_are_covered`
defines when a descriptor's read-only / destructive hints are present and
mutually consistent, :func:`annotation_coverage_gaps` sweeps a descriptor set for
violations, and :func:`annotations_for_command` enforces the same guard at
construction, so the server build and the tests inherit full coverage from one
place.
"""

from __future__ import annotations

from collections.abc import Iterable

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
    annotations = McpAnnotations(
        title=title,
        read_only_hint=read_only,
        destructive_hint=destructive,
        idempotent_hint=idempotent,
    )
    # Close the coverage gap at construction: every emitted annotation must carry
    # consistent read-only / destructive hints, so the server build and the tests
    # inherit the guarantee from one place rather than re-deriving it.
    if not annotations_are_covered(annotations):
        raise ValueError(f"inconsistent MCP annotation hints for command {command_key!r}")
    return annotations


def annotations_are_covered(annotations: McpAnnotations) -> bool:
    """Return whether one annotation's read-only / destructive hints are coherent.

    Coverage means the two decision hints a client acts on are present (they are
    non-optional booleans) and mutually consistent: a tool is never both read-only
    and destructive, a read-only tool is idempotent, and a destructive tool
    mutates state. A descriptor that fails this is an annotation gap.
    """
    if annotations.read_only_hint and annotations.destructive_hint:
        return False
    return not (annotations.read_only_hint and not annotations.idempotent_hint)


def annotation_coverage_gaps(annotated: Iterable[tuple[str, McpAnnotations]]) -> tuple[str, ...]:
    """Return the command keys whose annotations fail :func:`annotations_are_covered`.

    The shared coverage function the server build and the tests both run over the
    full descriptor set; an empty result is full annotation coverage.

    Returns:
        The command keys with an annotation coverage gap, in input order.
    """
    return tuple(command_key for command_key, annotations in annotated if not annotations_are_covered(annotations))
