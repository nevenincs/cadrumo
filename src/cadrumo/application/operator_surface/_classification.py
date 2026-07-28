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
key. The destructive / handoff / live-write axes - the genuinely-judgment ones -
are DECLARED per command in :mod:`~application.operator_surface._risk_table`;
read_only and idempotent are derived from the manifest family mutability, and
open_world is derived from the ``app.live.``/``pull`` facts. The MCP annotation
projection and the HITL confirmation tier both consume
:func:`command_classification`, so the client hint and the server gate read one
authority and cannot drift, and the no-silent-default parity gate asserts every
mutating-family command carries an explicit declaration.

This replaces the earlier leaf-NAME frozensets, which matched on the command key's
trailing word and so let a new mutating verb named ``purge``/``wipe``/``finalize``
fall through, classify non-destructive, and auto-approve.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import BaseModel, ConfigDict

from ...core.json_contract import ENVELOPE_SCHEMA_VERSION
from ._manifest import build_operator_surface_manifest
from ._models import OperatorMutability
from ._risk_table import CommandRiskDeclaration, declared_risk

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

# The outside-world surface: the ``app.live.*`` subtree talks to the AEAT sede,
# and any ``pull*`` leaf fetches from AEAT (a portal read, often Playwright-
# driven). These carry ``openWorldHint = true`` - the textbook open-world case,
# and a factual property of the command path, so it stays derived (not declared).
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
    """Classify one command from its key, its manifest mutability, and its risk row.

    The destructive / handoff / live-write axes come from the declared risk row
    (:func:`~application.operator_surface._risk_table.declared_risk`); a read-only
    command has no row and all three are False. read_only and idempotent derive
    from the family mutability (a live-write is never read-only - the stronger
    per-command declaration wins); open_world derives from the command path. This
    is the single derivation the annotation projection and the HITL tier consume.

    Returns:
        The command's :class:`CommandClassification`.
    """
    risk: CommandRiskDeclaration = declared_risk(command_key) or CommandRiskDeclaration()
    read_only = mutability is OperatorMutability.READ_ONLY and not risk.live_write
    return CommandClassification(
        command_key=command_key,
        read_only=read_only,
        destructive=(not read_only) and risk.destructive,
        idempotent=read_only,
        handoff=risk.handoff,
        live_write=risk.live_write,
        open_world=_is_open_world(command_key),
    )


@lru_cache(maxsize=1)
def _family_mutability_map() -> dict[str, OperatorMutability]:
    """Map each normalized command-family child token to its manifest mutability (cached)."""
    contract = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=(),
    ).contract
    return {family.child.replace("-", "_"): family.mutability for family in contract.command_families}


def _mutability_for(command_key: str) -> OperatorMutability:
    """Resolve a command's mutability from its family, defaulting to mutating.

    The ``LOCAL_STATE_MUTATING`` default for a family token this map does not
    know is DELIBERATE and fail-CLOSED, and it MUST NOT be removed. Every
    read-only-gated consumer relies on it: the MCP identity gate returns early
    only for a read-only command, so an unknown or retired key -- not read-only --
    makes the gate enforce; the risk-table no-silent-default parity gate uses it
    to make an undeclared mutating verb classify non-read-only and so be caught.
    Raising on an unknown family instead would turn the identity gate's
    retired-key refusal into a crash and defeat the parity gate's stricter read.

    The cost of the default is that it cannot distinguish an ABSENT key from a
    live write verb -- both classify non-read-only -- so a consumer that needs
    that distinction MUST ground its key against the live surface first. The
    write-guard catalogue gate binds to the materialised command tree, the
    risk-table parity gate screens the exposed descriptor set, and the HITL
    confirmation gate grounds its auto-approve path against the descriptor set,
    exactly so this permissive default cannot silently auto-approve an
    unclassified command. A new consumer of :func:`command_classification` must
    ground its key the same way.
    """
    tokens = command_key.split(".")
    family_token = tokens[1] if tokens[0] in {"config", "app"} and len(tokens) > 1 else tokens[0]
    return _family_mutability_map().get(family_token, OperatorMutability.LOCAL_STATE_MUTATING)


def command_classification(command_key: str) -> CommandClassification:
    """Classify a command by key alone, resolving its family mutability from the manifest.

    The by-key accessor the HITL confirmation tier and the persona handoff-deny
    rules consume when they hold only a command key (not the mutability the
    annotation builder already has). Reads the same declared risk table, so all
    three consumers share one authority.

    Returns:
        The command's :class:`CommandClassification`.
    """
    return classify_command(command_key, mutability=_mutability_for(command_key))


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
