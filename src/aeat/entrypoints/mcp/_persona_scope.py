"""Persona-scoped tool boundary over the operator-surface manifest.

Implements decision D1 of the ``2026-07-01-agent-harness-adr``: a runtime
``PreToolUse``-layer partition that filters the exposed MCP tool set by the
active operator persona's declared ``(family, mutability)`` ceiling. The
per-persona declaration in this module is a typed mapping from
:class:`AgentPersona` to a coarse set of mounted-command-family ``child``
tokens plus an :class:`~aeat.application.operator_surface.OperatorMutability`
ceiling - derived from each persona document's "Tool scope" section under
``src/aeat/_data/agent/personas/``. It is deliberately NOT a per-tool
allowlist: per D1, a second tool-shaped artifact would duplicate the
manifest's own ``(family, mutability)`` data and could itself drift between
builds, contrary to ``aeat-registry-authority-flow``'s single-authority
discipline.

:func:`is_tool_in_persona_scope` reads the live
:func:`~aeat.application.operator_surface.build_operator_surface_manifest`
on every call - never a frozen snapshot - so a manifest change (a family
added, removed, or re-mounted by the in-flight Track-1 ``#1`` manifest-
completeness brief) is picked up automatically. Correctness of the
per-persona declaration against the live manifest is proven separately by
the build-time pinning test in ``tests/test_persona_scope.py``, not by this
module.

This complements the existing global :func:`~aeat.entrypoints.mcp.confirmation_for_tool`
HITL policy: that gate decides *how* a call is approved (auto/confirm/block)
irrespective of persona; this gate decides *whether* a tool is in the active
persona's boundary at all. Both run in the ``PreToolUse`` layer.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from ...application.operator_surface import OperatorMutability, build_operator_surface_manifest
from ...core.json_contract import ENVELOPE_SCHEMA_VERSION

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

# Ordered so a family's actual mutability may be compared against a persona's
# declared ceiling: READ_ONLY is strictly less permissive-requiring than
# LOCAL_STATE_MUTATING, so a family ranks at or below the persona's ceiling.
_MUTABILITY_RANK: dict[OperatorMutability, int] = {
    OperatorMutability.READ_ONLY: 0,
    OperatorMutability.LOCAL_STATE_MUTATING: 1,
}


class AgentPersona(StrEnum):
    """The seven operator-harness personas, named per their persona document stem.

    Mirrors the file stems under ``src/aeat/_data/agent/personas/`` exactly
    (kebab-case), so a persona's runtime identity and its shipped document are
    the same token.
    """

    COORDINATOR = "coordinator"
    ONBOARDING = "onboarding"
    LEDGER_GROOMER = "ledger-groomer"
    CLASSIFIER = "classifier"
    MODELO_PREPARER = "modelo-preparer"
    VERIFIER = "verifier"
    RECONCILER = "reconciler"


class PersonaToolScope(BaseModel):
    """One persona's declared mounted-command-family boundary.

    ``families`` names the mounted-command-family ``child`` tokens (e.g.
    ``"ledger"``, ``"modelo"``) the persona document's Tool-scope section
    grants it; a family absent from this set is out of scope regardless of
    mutability. ``mutability_ceiling`` is the highest
    :class:`~aeat.application.operator_surface.OperatorMutability` the persona
    may invoke within its scoped families - a family whose own manifest-declared
    mutability exceeds the ceiling is refused even when the family child is
    listed, which is defence in depth for a future manifest edit that raises a
    scoped family's mutability without an explicit persona-boundary review.
    """

    model_config = _STRICT_FROZEN

    persona: AgentPersona
    families: frozenset[str] = Field(min_length=1)
    mutability_ceiling: OperatorMutability


# Declared per D1 of `2026-07-01-agent-harness-adr`: one typed persona ->
# (family set, mutability ceiling) mapping, derived from each persona
# document's "Tool scope" section. This stays coarse at the mounted-command-
# family boundary (the manifest's own granularity, per the
# `MountedCommandFamily.commands` docstring: "a contract summary ... not a
# replacement for live command-tree traversal") so a new verb added to an
# already-scoped family never needs this mapping edited - only a new family
# grant does.
#
# coordinator: read-only orchestration only (`aeat app overview status`,
# `aeat app contract`); it delegates every mutating step and issues no
# mutating verb itself (asserted by the pinning test).
#
# onboarding: profile custody + read-only auth configuration + read-only
# overview confirmation. No modelo, no ledger mutation, no live AEAT read.
#
# ledger-groomer / classifier: both scope to the `ledger` family - the
# manifest has no verb-level split between bookkeeping and classification
# verbs, so the distinction between these two personas is prose-level (which
# `ledger` verbs each one issues), not manifest-enforced.
#
# modelo-preparer / verifier / reconciler: all scope to the `modelo` family,
# which already covers work-unit creation/calculation, verification, export,
# the filing-record marker, and the `reconcile` subgroup - no family grant is
# pending on the in-flight `#1` manifest-completeness brief today.
PERSONA_TOOL_SCOPES: tuple[PersonaToolScope, ...] = (
    PersonaToolScope(
        persona=AgentPersona.COORDINATOR,
        families=frozenset({"overview", "contract"}),
        mutability_ceiling=OperatorMutability.READ_ONLY,
    ),
    PersonaToolScope(
        persona=AgentPersona.ONBOARDING,
        families=frozenset({"profile", "auth", "overview"}),
        mutability_ceiling=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    PersonaToolScope(
        persona=AgentPersona.LEDGER_GROOMER,
        families=frozenset({"ledger"}),
        mutability_ceiling=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    PersonaToolScope(
        persona=AgentPersona.CLASSIFIER,
        families=frozenset({"ledger"}),
        mutability_ceiling=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    PersonaToolScope(
        persona=AgentPersona.MODELO_PREPARER,
        families=frozenset({"modelo"}),
        mutability_ceiling=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    PersonaToolScope(
        persona=AgentPersona.VERIFIER,
        families=frozenset({"modelo"}),
        mutability_ceiling=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
    PersonaToolScope(
        persona=AgentPersona.RECONCILER,
        families=frozenset({"modelo"}),
        mutability_ceiling=OperatorMutability.LOCAL_STATE_MUTATING,
    ),
)

_SCOPES_BY_PERSONA: dict[AgentPersona, PersonaToolScope] = {scope.persona: scope for scope in PERSONA_TOOL_SCOPES}


def scope_for_persona(persona: AgentPersona) -> PersonaToolScope:
    """Return the declared :class:`PersonaToolScope` for one persona.

    Every :class:`AgentPersona` member has exactly one declared scope (proven
    by the pinning test), so this never falls back to a default.
    """
    return _SCOPES_BY_PERSONA[persona]


def _family_token_for_command_key(command_key: str) -> str:
    """Project a registry command key onto its mounted-command-family child token.

    Mirrors the root-stripping rule already applied in this package (see
    ``_tools.py``'s ``_mutability_for_key`` and ``_dispatch.py``'s
    ``_cli_path_tokens``): a ``config.``/``app.``-prefixed key's family is its
    second segment; every other key's family is its first segment.
    """
    tokens = command_key.split(".")
    if tokens[0] in {"config", "app"} and len(tokens) > 1:
        return tokens[1]
    return tokens[0]


def live_family_mutability() -> dict[str, OperatorMutability]:
    """Read the live operator-surface manifest and map each family to its mutability.

    Reads :func:`~aeat.application.operator_surface.build_operator_surface_manifest`
    fresh on every call rather than caching a snapshot, so a manifest change
    (a family added, removed, or re-mounted) is observed immediately - the
    single-authority discipline D1 requires.
    """
    contract = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=(),
    ).contract
    return {family.child: family.mutability for family in contract.command_families}


def is_tool_in_persona_scope(*, persona: AgentPersona, command_key: str) -> bool:
    """Return whether ``command_key`` is in ``persona``'s live-manifest-checked scope.

    The ``PreToolUse``-layer partition D1 mandates: a command key is in scope
    only when (1) its projected family child token is one of the persona's
    declared ``families``, and (2) that family's *live* manifest mutability is
    at or below the persona's declared ``mutability_ceiling``. A family absent
    from the live manifest altogether (not yet mounted) fails closed - it is
    never treated as in scope.

    This is independent of, and complements, the global
    :func:`~aeat.entrypoints.mcp.confirmation_for_tool` HITL confirmation tier:
    that gate decides how an in-scope call is approved; this gate decides
    whether the call is in the persona's boundary at all.
    """
    scope = scope_for_persona(persona)
    family_token = _family_token_for_command_key(command_key)
    if family_token not in scope.families:
        return False
    family_mutability = live_family_mutability().get(family_token)
    if family_mutability is None:
        return False
    return _MUTABILITY_RANK[family_mutability] <= _MUTABILITY_RANK[scope.mutability_ceiling]
