"""Persona-scoped tool boundary over the operator-surface manifest.

A runtime ``PreToolUse``-layer partition that filters the exposed MCP tool set
by the active operator persona's declared ``(family, mutability)`` ceiling. The
per-persona declaration in this module is a typed mapping from
:class:`AgentPersona` to a coarse set of mounted-command-family ``child``
tokens plus an :class:`~application.operator_surface.OperatorMutability`
ceiling - derived from each persona document's "Tool scope" section under
``src/cadrumo-harness/src/cadrumo_harness/_data/agent/personas/``. It is deliberately NOT a per-tool
allowlist: a second tool-shaped artifact would duplicate the
manifest's own ``(family, mutability)`` data and could itself drift between
builds, contrary to ``aeat-registry-authority-flow``'s single-authority
discipline.

:func:`is_tool_in_persona_scope` reads the live
:func:`~application.operator_surface.build_operator_surface_manifest`
on every call - never a frozen snapshot - so a manifest change (a family
added, removed, or re-mounted) is picked up automatically. Correctness of the
per-persona declaration against the live manifest is proven separately by
the build-time pinning test in ``tests/test_persona_scope.py``, not by this
module.

This complements the existing global :func:`~cadrumo_harness.mcp.confirmation_for_tool`
HITL policy: that gate decides *how* a call is approved (auto/confirm/block)
irrespective of persona; this gate decides *whether* a tool is in the active
persona's boundary at all. Both run in the ``PreToolUse`` layer.

:func:`active_persona` resolves the runtime session's persona from the
``CADRUMO_MCP_PERSONA`` environment variable; ``_server.py`` calls it once at
``serve()`` startup and threads the result through ``_list_tools`` (filters
the advertised tool set) and ``_call_tool`` (refuses an out-of-scope call
before the global HITL gate runs).

Family granularity and the handoff deny rules: the manifest's own boundary is
the mounted-command-family ``child`` token, not the individual verb, and the
scope filter stays at that granularity (three personas - ``cadrumo-modelo-preparer``,
``cadrumo-verifier``, and ``cadrumo-reconciler`` - all declare ``families={"modelo"}``).
What IS verb-granular is the irreversible boundary:
:data:`PERSONA_HANDOFF_DENIALS` structurally denies the filing-handoff leaves
(``export``, the record marker ``file``) to every modelo-lifecycle persona
except the ``verifier``, which is the sole owner of the
irreversible artefact. The preparer/verifier split for NON-handoff verbs
(e.g. the verifier calling ``modelo.work.create``) remains prose-level
persona discipline; the deny rules close exactly the boundary whose breach
is irreversible.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.application.operator_surface import (
    OperatorMutability,
    build_operator_surface_manifest,
)
from cadrumo.core.json_contract import ENVELOPE_SCHEMA_VERSION

from ._command_policy import CommandPolicyProjection, command_policy

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

#: The environment variable that selects the active MCP session persona. Absent
#: or empty means the session is un-personified and keeps the full, unscoped
#: tool surface, preserved for any caller that does
#: not opt into a persona boundary.
PERSONA_ENV_VAR = "CADRUMO_MCP_PERSONA"

# Ordered so a family's actual mutability may be compared against a persona's
# declared ceiling: READ_ONLY is strictly less permissive-requiring than
# LOCAL_STATE_MUTATING, so a family ranks at or below the persona's ceiling.
_MUTABILITY_RANK: dict[OperatorMutability, int] = {
    OperatorMutability.READ_ONLY: 0,
    OperatorMutability.LOCAL_STATE_MUTATING: 1,
}


class AgentPersona(StrEnum):
    """The seven operator-harness personas, named per their persona document stem.

    Mirrors the file stems under ``src/cadrumo-harness/src/cadrumo_harness/_data/agent/personas/`` exactly
    (kebab-case), so a persona's runtime identity and its shipped document are
    the same token.
    """

    COORDINATOR = "cadrumo-coordinator"
    ONBOARDING = "cadrumo-onboarding"
    LEDGER_GROOMER = "cadrumo-ledger-groomer"
    CLASSIFIER = "cadrumo-classifier"
    MODELO_PREPARER = "cadrumo-modelo-preparer"
    VERIFIER = "cadrumo-verifier"
    RECONCILER = "cadrumo-reconciler"


class PersonaToolScope(BaseModel):
    """One persona's declared mounted-command-family boundary.

    ``families`` names the mounted-command-family ``child`` tokens (e.g.
    ``"ledger"``, ``"modelo"``) the persona document's Tool-scope section
    grants it; a family absent from this set is out of scope regardless of
    mutability. ``mutability_ceiling`` is the highest
    :class:`~application.operator_surface.OperatorMutability` the persona
    may invoke within its scoped families - a family whose own manifest-declared
    mutability exceeds the ceiling is refused even when the family child is
    listed, which is defence in depth for a future manifest edit that raises a
    scoped family's mutability without an explicit persona-boundary review.
    """

    model_config = _STRICT_FROZEN

    persona: AgentPersona
    families: frozenset[str] = Field(min_length=1)
    mutability_ceiling: OperatorMutability


# One typed persona -> (family set, mutability ceiling) mapping, derived from
# each persona document's "Tool scope" section. This stays coarse at the
# mounted-command-family boundary (the manifest's own granularity, per the
# `MountedCommandFamily.commands` docstring: "a contract summary ... not a
# replacement for live command-tree traversal") so a new verb added to an
# already-scoped family never needs this mapping edited - only a new family
# grant does.
#
# coordinator: read-only orchestration only (`aeat app overview status`); it
# delegates every mutating step and issues no mutating verb itself (asserted by
# the pinning test). The capability manifest it orients from is the MCP-native
# `contract` meta-tool, which carries no command family and is therefore not a
# family grant.
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
# the filing-record marker, and the `reconcile` subgroup - no further family
# grant is pending.
PERSONA_TOOL_SCOPES: tuple[PersonaToolScope, ...] = (
    PersonaToolScope(
        persona=AgentPersona.COORDINATOR,
        families=frozenset({"overview"}),
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

    Reads :func:`~application.operator_surface.build_operator_surface_manifest`
    fresh on every call rather than caching a snapshot, so a manifest change
    (a family added, removed, or re-mounted) is observed immediately - the
    single-authority discipline this module requires.

    Returns:
        A mapping of family child token to its :class:`OperatorMutability`.
    """
    contract = build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=(),
    ).contract
    return {family.child: family.mutability for family in contract.command_families}


def is_tool_in_persona_scope(*, persona: AgentPersona, command_key: str) -> bool:
    """Return whether ``command_key`` is in ``persona``'s live-manifest-checked scope.

    The ``PreToolUse``-layer partition: a command key is in scope
    only when (1) its projected family child token is one of the persona's
    declared ``families``, and (2) that family's *live* manifest mutability is
    at or below the persona's declared ``mutability_ceiling``. A family absent
    from the live manifest altogether (not yet mounted) fails closed - it is
    never treated as in scope.

    This is independent of, and complements, the global
    :func:`~cadrumo_harness.mcp.confirmation_for_tool` HITL confirmation tier:
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


# Per-verb handoff deny rules: within the shared `modelo` family,
# only the VERIFIER may produce the irreversible filing artefacts - the export
# and the record marker. The preparer builds, the reconciler acts after the
# human files; neither owns the handoff. Personas outside the modelo family
# never reach these verbs through the family scope, so they need no row.
PERSONA_HANDOFF_DENIALS: frozenset[AgentPersona] = frozenset(
    {AgentPersona.MODELO_PREPARER, AgentPersona.RECONCILER},
)


#: The mounted-command family that owns the irreversible filing handoff. The
#: denial is specifically the *modelo* filing boundary (its ``export``
#: and record-marker ``file`` leaves), so the deny check is scoped to this
#: family. Without the family guard the bare leaf-name match would also fire on
#: an unrelated ``<family>.export`` / ``<family>.file`` verb (e.g. a future
#: ledger-exporting persona's ``ledger.export``) - fail-safe and masked by the
#: current persona scopes, but a spurious refusal waiting to surface.
_HANDOFF_FAMILY = "modelo"


def is_handoff_denied(
    *, persona: AgentPersona, command_key: str, execution_policy: CommandPolicyProjection | None = None
) -> bool:
    """True when ``command_key`` is a handoff leaf this persona is structurally denied.

    The denial is the irreversible *modelo* filing handoff, so it fires only for
    a command in the ``modelo`` family whose leaf is a denied handoff verb - a
    same-named ``export`` / ``file`` leaf in another family is never caught by
    this rule (it is out of a modelo persona's scope anyway; the family guard
    keeps the rule precise rather than relying on scope to mask it).

    Runs in the same ``PreToolUse`` layer as :func:`is_tool_in_persona_scope`
    and is checked by both ``_list_tools`` (the denied tool is not even
    advertised to the persona) and ``_call_tool`` (a direct call refuses).
    """
    if persona not in PERSONA_HANDOFF_DENIALS:
        return False
    if _family_token_for_command_key(command_key) != _HANDOFF_FAMILY:
        return False
    attached_policy = execution_policy or command_policy(command_key)
    return attached_policy.handoff


def handoff_denial_message(*, persona: AgentPersona, command_key: str) -> str:
    """The instructive refusal for a denied handoff call, naming the owning persona (client-relayed, localized)."""
    from cadrumo.core.i18n import tr

    return tr(
        "mcp.persona.handoff_denied",
        command=command_key,
        persona=persona.value,
        owner=AgentPersona.VERIFIER.value,
        default=(
            "'{command}' is the irreversible filing-handoff boundary, owned by "
            "the '{owner}' persona; the '{persona}' persona is structurally "
            "denied it. Hand the verified work unit to the verifier session to "
            "produce the export or record marker."
        ),
    )


def active_persona(env: Mapping[str, str] | None = None) -> AgentPersona | None:
    """Resolve the active MCP session persona from :data:`PERSONA_ENV_VAR`.

    Reads ``env`` (an injectable mapping so the resolution is unit-tested
    against real dict inputs without touching process environment state;
    defaults to ``os.environ`` for the live server). An absent or blank value
    returns ``None``, which callers MUST treat as "unscoped" - the full tool
    surface, so an un-personified session (a
    direct developer connection, a session that predates the persona
    boundary) is never accidentally narrowed.

    Raises:
        ValueError: the environment value does not name a declared
            :class:`AgentPersona` member. The message enumerates the accepted
            set per ``aeat-architecture-boundaries``'s CLI-boundary
            instructive-refusal discipline.
    """
    raw = (env if env is not None else os.environ).get(PERSONA_ENV_VAR, "").strip()
    if not raw:
        return None
    try:
        return AgentPersona(raw)
    except ValueError as exc:
        accepted = ", ".join(sorted(member.value for member in AgentPersona))
        message = f"{PERSONA_ENV_VAR}={raw!r} is not a recognised persona; accepted values: {accepted}"
        raise ValueError(message) from exc
