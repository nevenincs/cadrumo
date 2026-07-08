"""Declared per-command risk classification, co-located with the manifest.

The MCP console's tool annotations and its human-in-the-loop confirmation tier
both need to know a command's risk posture: is it destructive, idempotent, a
filing handoff, a forbidden AEAT live-write, and does it reach the outside world
(the AEAT sede)? Before this module those axes were inferred from small leaf-name
frozensets scattered across the MCP layer, and ``openWorldHint`` was never set at
all (research F3) - a new mutating verb outside the lists silently classified as
non-destructive, and the annotation hint and the server gate could drift because
they derived independently.

This module makes the classification ONE declared, typed record keyed by command
key, derived from the manifest mutability plus the closed leaf/prefix sets
declared here (ADR ``mcp-protocol-hardening`` H3). The MCP annotation projection
and the HITL confirmation tier both consume :func:`classify_command`, so the
client hint and the server gate cannot drift, and a parity gate over the manifest
asserts every command classifies coherently.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from ._models import OperatorMutability

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

# Leaf verbs that destroy or irreversibly overwrite local state. A command key
# whose final segment is one of these is destructive regardless of its family.
DESTRUCTIVE_LEAVES: frozenset[str] = frozenset(
    {"remove", "reset", "delete", "discard", "rekey", "recover", "logout", "clear", "merge", "stash"},
)

# Leaf verbs that are safe to repeat with the same effect (pure reads).
IDEMPOTENT_LEAVES: frozenset[str] = frozenset(
    {"list", "show", "view", "status", "describe", "casillas", "history", "calendar", "agenda", "backlog"},
)

# Leaf verbs that hand a filing-grade artefact off (an export, a local file
# marker). Not destructive, but a deliberate output a human should confirm.
HANDOFF_LEAVES: frozenset[str] = frozenset({"export", "file"})

# Leaf verbs that would write to AEAT. None are exposed today (the live tree is
# read-only and live submission is permanently forbidden); this guard blocks one
# defensively if it ever appears. ``declare`` is excluded: it collides with the
# local ledger bien-de-inversion verb, a non-AEAT local write.
LIVE_WRITE_LEAVES: frozenset[str] = frozenset({"submit", "present", "send"})

# The outside-world surface: the ``app.live.*`` subtree talks to the AEAT sede,
# and any ``pull*`` leaf fetches from AEAT (a portal read, often Playwright-
# driven). These carry ``openWorldHint = true`` - the textbook open-world case.
_OPEN_WORLD_PREFIXES: tuple[str, ...] = ("app.live.",)


def _leaf(command_key: str) -> str:
    return command_key.rsplit(".", 1)[-1]


def _is_open_world(command_key: str) -> bool:
    if any(command_key.startswith(prefix) for prefix in _OPEN_WORLD_PREFIXES):
        return True
    return _leaf(command_key).startswith("pull")


class CommandClassification(BaseModel):
    """The declared risk posture of one command, the single classification authority.

    ``read_only`` mirrors the manifest family mutability; ``destructive`` is true
    only for irreversible state-destroying verbs; ``idempotent`` for pure
    repeatable reads; ``handoff`` for filing-grade outputs a human confirms;
    ``live_write`` for a (never-exposed) AEAT-submission verb; ``open_world`` for
    a verb that reaches the outside AEAT sede.
    """

    model_config = _STRICT_FROZEN

    command_key: str
    read_only: bool
    destructive: bool
    idempotent: bool
    handoff: bool
    live_write: bool
    open_world: bool


def classify_command(command_key: str, *, mutability: OperatorMutability) -> CommandClassification:
    """Classify one command from its key and its manifest family mutability.

    The single derivation both the MCP annotation projection and the HITL
    confirmation tier consume, so the client hint and the server gate read one
    authority and cannot drift.

    Returns:
        The command's :class:`CommandClassification`.
    """
    leaf = _leaf(command_key)
    live_write = leaf in LIVE_WRITE_LEAVES
    # A live-write leaf mutates the outside world by definition, so it is never
    # read-only regardless of the family's declared mutability - the stronger
    # per-verb signal wins over the family default.
    read_only = mutability is OperatorMutability.READ_ONLY and not live_write
    destructive = (not read_only) and leaf in DESTRUCTIVE_LEAVES
    idempotent = read_only or leaf in IDEMPOTENT_LEAVES
    return CommandClassification(
        command_key=command_key,
        read_only=read_only,
        destructive=destructive,
        idempotent=idempotent,
        handoff=leaf in HANDOFF_LEAVES,
        live_write=live_write,
        open_world=_is_open_world(command_key),
    )


def classification_is_coherent(classification: CommandClassification) -> bool:
    """Whether one classification's axes are mutually consistent.

    A tool is never both read-only and destructive; a read-only tool is
    idempotent; a live-write is never read-only. This is the invariant the
    parity gate asserts over the whole manifest command set.
    """
    if classification.read_only and classification.destructive:
        return False
    if classification.read_only and not classification.idempotent:
        return False
    return not (classification.read_only and classification.live_write)
