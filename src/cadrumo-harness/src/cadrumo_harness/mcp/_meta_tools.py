"""The ``contract`` + ``search`` + ``execute`` meta-tools for the verb surface.

The curated domain toolsets (``_toolsets``) cover the common path; the rest of
the operator-callable verb tree is reached through meta-tools, the Cloudflare
precedent for a large API surface: ``contract`` emits the whole capability
manifest the operator rules mandate reading first, ``search`` maps a natural
query onto matching command keys with their intent and mutability, and
``execute`` runs one command key with typed arguments.

``contract`` is MCP-native: it composes the application layer's
:func:`~application.operator_surface.build_operator_surface_manifest` with the
CLI's registered result-schema references directly, so the manifest is served
without spawning the CLI and without a command family of its own.

The load-bearing guarantee is that ``execute`` is NOT a side door. It routes
through the exact same gates a direct tool call runs - :func:`gate_refusal`
applies the persona-scope boundary and the permanent live-write block before any
dispatch, producing byte-identical refusals - so a verb an active persona may not
call directly cannot be reached by naming it to ``execute`` either. The dispatch
itself is injected (:func:`meta_execute` takes the server's subprocess runner) so
this module stays SDK-independent and unit-tested.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.application.command_search import CommandDoc, CommandIndex, build_command_index
from cadrumo.application.operator_surface import (
    OperatorSurfaceManifest,
    build_operator_surface_manifest,
)
from cadrumo.core.json_contract import ENVELOPE_SCHEMA_VERSION

from ._hitl import ConfirmationPolicy, confirmation_for_policy
from ._persona_scope import AgentPersona, handoff_denial_message, is_handoff_denied, is_tool_in_persona_scope
from ._tools import McpToolDescriptor
from ._toolsets import MAX_ACTIVE_TOOLSETS, Toolset, _family_domain_map, build_toolsets, toolset_for_command

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")


@dataclass(frozen=True)
class ToolRunOutcome:
    """The common result contract shared by direct and meta-tool dispatch."""

    envelope: dict[str, object]
    is_error: bool


#: The subprocess runner the server injects into :func:`meta_execute`: it takes a
#: descriptor and the named arguments and returns the same typed outcome the
#: direct call path uses.
ToolRunner = Callable[[McpToolDescriptor, dict[str, object]], ToolRunOutcome]


class MetaSearchResult(BaseModel):
    """One command matched by :func:`search_commands`, with its decision hints.

    The result is self-sufficient: besides
    the mutability hints it carries the per-verb ``input_schema``, so a model that
    finds a verb through ``search`` can call it through ``execute`` in ONE more
    round-trip without a separate schema lookup.
    """

    model_config = _STRICT_FROZEN

    command_key: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    read_only: bool
    destructive: bool
    score: float
    input_schema: dict[str, Any] = Field(default_factory=dict)


class MetaExecuteResult(BaseModel):
    """The outcome of a :func:`meta_execute` call.

    Exactly one of ``refused`` or ``envelope`` is populated: a gated or unknown
    command carries the refusal message and no envelope; an allowed command
    carries the CLI envelope and its error flag.
    """

    model_config = _STRICT_FROZEN

    command_key: str = Field(min_length=1)
    refused: str | None = None
    envelope: dict[str, object] | None = None
    is_error: bool = False


#: Curated outcome-vocabulary aliases folded into a command's search document.
#: This is INDEX text only, never the
#: model-facing tool description (the English-boundary): it lets an outcome-phrased
#: query ("file my quarterly IVA", "do my taxes") reach the composite ``quickfile``
#: chain that literal-verb tokens miss. English plus the Spanish outcome nouns the
#: CLI help uses (``presentar``, ``declaración``, ``trimestral``, ``autoliquidación``).
def _command_doc(descriptor: McpToolDescriptor) -> CommandDoc:
    """Build the weighted searchable document for one command.

    The document splits into BM25-weighted tiers: ``key_and_name`` (the command
    key's dotted tokens - ``calculate``, ``export``, ``iva_wallet`` - plus the
    tool name) ranks highest, curated outcome ``aliases`` next, then the
    English ``description``, then the command's own per-verb CLI ``help``. The
    help is the CLI's Spanish domain vocabulary, so folding it into the index -
    NOT into the English model-facing description - lets a Spanish concept
    query recall the right verb; the aliases surface the
    composite verbs on outcome-phrased queries without touching the model surface.
    """
    key_tokens = descriptor.command_key.replace(".", " ").replace("_", " ")
    key_and_name = f"{descriptor.command_key} {key_tokens} {descriptor.name}"
    from cadrumo.entrypoints.cli import command_search_terms

    return CommandDoc(
        command_key=descriptor.command_key,
        tool_name=descriptor.name,
        key_and_name=key_and_name,
        description=descriptor.description,
        aliases=" ".join(command_search_terms(descriptor.command_key)),
        help=descriptor.verb_schema.help,
    )


def build_command_search_index(descriptors: tuple[McpToolDescriptor, ...]) -> CommandIndex:
    """Build the lexical command-search index over the descriptor set.

    Built once per server from the full descriptor set so ``search`` reaches the
    whole verb universe, not just the advertised surface. The index is fully
    offline: it loads no model and reaches no network.
    """
    return build_command_index(_command_doc(descriptor) for descriptor in descriptors)


def search_commands(
    query: str,
    *,
    descriptors: tuple[McpToolDescriptor, ...],
    index: CommandIndex | None = None,
    limit: int = 20,
) -> tuple[MetaSearchResult, ...]:
    """Rank the command surface against ``query`` for the ``search`` meta-tool.

    Backed by the lexical command index (per-column FTS5 BM25 + Spanish
    stemming + diacritics folding, degrading to token overlap on a minimal
    install), so a concept query bridges the operator's vocabulary to the
    command's own tokens where a bare substring match would miss it. Each result carries the
    mutability hints AND the per-verb input schema so
    it is actionable in one further ``execute`` round-trip. ``index`` may be a
    prebuilt index (the server builds it once); when omitted it is built from
    ``descriptors``.

    Returns:
        The matched commands, highest score first, capped at ``limit``.
    """
    if not query.strip():
        return ()
    search_index = index if index is not None else build_command_search_index(descriptors)
    by_key = {descriptor.command_key: descriptor for descriptor in descriptors}
    results: list[MetaSearchResult] = []
    for hit in search_index.search(query, limit=limit):
        descriptor = by_key.get(hit.command_key)
        if descriptor is None:
            continue
        results.append(
            MetaSearchResult(
                command_key=descriptor.command_key,
                tool_name=descriptor.name,
                description=descriptor.description,
                read_only=descriptor.annotations.read_only_hint,
                destructive=descriptor.annotations.destructive_hint,
                score=hit.score,
                input_schema=descriptor.input_schema,
            )
        )
    return tuple(results)


class MetaSearchResponse(BaseModel):
    """The ``search`` meta-tool result with its overflow signal.

    Wraps the capped :class:`MetaSearchResult` page with how much the corpus
    actually matched: ``total_matches``
    is the full count over the whole verb surface, ``truncated`` is true when the
    page dropped some of them, and ``hint`` names the next moves - ``describe`` for
    one command's full schema, ``toolsets`` to widen the advertised surface - so a
    model that overflowed the page knows it did and how to recover.
    """

    model_config = _STRICT_FROZEN

    results: tuple[MetaSearchResult, ...] = ()
    total_matches: int = Field(ge=0)
    truncated: bool
    hint: str = ""


def search_commands_response(
    query: str,
    *,
    descriptors: tuple[McpToolDescriptor, ...],
    index: CommandIndex | None = None,
    limit: int = 20,
) -> MetaSearchResponse:
    """Rank the command surface and report how much of it overflowed the page.

    Returns the same capped page as :func:`search_commands` alongside the full
    match count over the whole verb corpus, so the client sees whether the page
    truncated the result set. ``total_matches`` counts every command key the index
    matches, capped internally at the corpus size; ``truncated`` and the recovery
    ``hint`` follow from it. A blank query returns the empty response.

    Returns:
        The :class:`MetaSearchResponse` for ``query``.
    """
    if not query.strip():
        return MetaSearchResponse(results=(), total_matches=0, truncated=False, hint="")
    search_index = index if index is not None else build_command_search_index(descriptors)
    results = search_commands(query, descriptors=descriptors, index=search_index, limit=limit)
    known_keys = {descriptor.command_key for descriptor in descriptors}
    all_hits = search_index.search(query, limit=len(descriptors))
    total_matches = sum(1 for hit in all_hits if hit.command_key in known_keys)
    truncated = total_matches > len(results)
    hint = (
        "More commands matched than were returned; narrow the query, call `describe` with a "
        "command_key for one command's full schema, or activate a domain toolset through `toolsets` "
        "to widen the advertised surface."
        if truncated
        else ""
    )
    return MetaSearchResponse(results=results, total_matches=total_matches, truncated=truncated, hint=hint)


class MetaDescribeResult(BaseModel):
    """One command's full descriptor for the ``describe`` meta-tool.

    The self-sufficient counterpart to a :class:`MetaSearchResult` hit: where
    ``search`` returns a ranked page
    of decision hints, ``describe`` returns ONE command's whole shape by key - its
    per-verb ``input_schema``, its mutability annotations, its confirmation tier,
    its CommandSpec-owned execution posture, its owning curated toolset, and exactly which
    personas may call it - so a model can inspect a verb fully before spending an
    ``execute`` round-trip on it.
    """

    model_config = _STRICT_FROZEN

    command_key: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    read_only: bool
    destructive: bool
    idempotent: bool
    open_world: bool
    confirmation_tier: str = Field(min_length=1)
    handoff: bool
    live_write: bool
    owning_toolset: str | None = None
    reachable_personas: tuple[str, ...] = ()


def describe_command(
    command_key: str,
    *,
    descriptors: tuple[McpToolDescriptor, ...],
) -> MetaDescribeResult | None:
    """Return one command's full descriptor by key, or ``None`` when unexposed.

    Resolves everything from the live descriptor set and the real classifiers -
    the annotation hints and CommandSpec-owned execution policy from the
    descriptor, the confirmation tier from the same policy, the owning toolset from
    :func:`~cadrumo_harness.mcp._toolsets.toolset_for_command`, and the reachable
    personas from the same scope + handoff-deny gates the call path enforces. A
    key that names no exposed descriptor returns ``None``.

    Returns:
        The :class:`MetaDescribeResult` for ``command_key``, or ``None``.
    """
    descriptor = next((candidate for candidate in descriptors if candidate.command_key == command_key), None)
    if descriptor is None:
        return None
    policy = descriptor.execution_policy
    toolset = toolset_for_command(command_key, family_map=_family_domain_map())
    reachable = tuple(
        sorted(
            persona.value
            for persona in AgentPersona
            if is_tool_in_persona_scope(persona=persona, command_key=command_key)
            and not is_handoff_denied(
                persona=persona,
                command_key=command_key,
                execution_policy=descriptor.execution_policy,
            )
        )
    )
    return MetaDescribeResult(
        command_key=descriptor.command_key,
        tool_name=descriptor.name,
        description=descriptor.description,
        input_schema=descriptor.input_schema,
        read_only=descriptor.annotations.read_only_hint,
        destructive=descriptor.annotations.destructive_hint,
        idempotent=descriptor.annotations.idempotent_hint,
        open_world=descriptor.annotations.open_world_hint,
        confirmation_tier=confirmation_for_policy(descriptor.execution_policy).value,
        handoff=policy.handoff,
        live_write=policy.live_write,
        owning_toolset=toolset.value if toolset is not None else None,
        reachable_personas=reachable,
    )


def build_capability_manifest() -> OperatorSurfaceManifest:
    """Build the operator-surface capability manifest served by ``contract``.

    The orientation surface the operator rules mandate reading first: the
    accepted roots, every mounted command family with its ``operator_question``
    intent and mutability, the lifecycle ordering, and the registered per-command
    result-schema references. Composed here from the application layer's
    :func:`~application.operator_surface.build_operator_surface_manifest` and the
    CLI's own :func:`~entrypoints.cli.command_schema_refs`, so the manifest is a
    first-class MCP tool rather than a projection of any one CLI verb.

    Returns:
        The validated :class:`~application.operator_surface.OperatorSurfaceManifest`.
    """
    from cadrumo.entrypoints.cli.command_api import command_schema_refs

    return build_operator_surface_manifest(
        envelope_schema_version=ENVELOPE_SCHEMA_VERSION,
        command_schemas=command_schema_refs(),
    )


def gate_refusal(*, persona: AgentPersona | None, descriptor: McpToolDescriptor) -> str | None:
    """Return the refusal a tool call incurs, or ``None`` when it may proceed.

    The single gate sequence run by BOTH the direct call path and ``execute``: an
    out-of-scope call is refused, then a persona's handoff-denied verb, then the
    permanent live-write block. The messages are byte-identical to the direct
    path's refusals, so the two entry points cannot diverge — the per-verb
    handoff deny (verifier-only export/record-marker) is enforced
    here STRUCTURALLY, not left to the sync path's incidental no-elicitation
    fallback.

    Returns:
        The refusal message, or ``None`` when the call is allowed.
    """
    if persona is not None and not is_tool_in_persona_scope(persona=persona, command_key=descriptor.command_key):
        return f"refused: {descriptor.command_key!r} is outside the active persona {persona.value!r}'s tool scope"
    if persona is not None and is_handoff_denied(
        persona=persona,
        command_key=descriptor.command_key,
        execution_policy=descriptor.execution_policy,
    ):
        return handoff_denial_message(persona=persona, command_key=descriptor.command_key)
    if confirmation_for_policy(descriptor.execution_policy) is ConfirmationPolicy.BLOCK:
        return "refused: AEAT live-write is permanently forbidden"
    return None


class ToolsetAction(StrEnum):
    """The three verbs the ``toolsets`` management meta-tool accepts."""

    LIST = "list"
    ACTIVATE = "activate"
    DEACTIVATE = "deactivate"


class ToolsetManageResult(BaseModel):
    """The outcome of a :func:`manage_toolsets` call.

    ``changed`` is true only when the active set actually moved (so the caller
    knows whether to emit ``tools/list_changed``). ``groups`` lists every toolset
    with its member count and current active state; ``refused`` carries an
    instructive message when an action could not be applied (unknown name, cap
    reached).
    """

    model_config = _STRICT_FROZEN

    action: str
    changed: bool
    active: tuple[str, ...]
    groups: tuple[dict[str, object], ...]
    refused: str | None = None


def manage_toolsets(
    action: str,
    name: str | None,
    *,
    active: set[Toolset],
) -> ToolsetManageResult:
    """Apply a ``toolsets`` action, mutating ``active`` in place.

    ``list`` reports the groups and current state without change. ``activate``
    adds a toolset (refused past :data:`~cadrumo_harness.mcp._toolsets.MAX_ACTIVE_TOOLSETS`
    or on an unknown name); ``deactivate`` removes one. Activation widens the
    advertised surface within the active persona's scope (the server applies the
    scope filter when it rebuilds the tool list), so this function owns only the
    set membership and the cap.

    Returns:
        A :class:`ToolsetManageResult`; ``changed`` drives the list-changed
        notification.
    """
    groups = build_toolsets()
    member_counts = {group.toolset: len(group.command_keys) for group in groups}
    changed = False
    refused: str | None = None

    try:
        parsed_action = ToolsetAction(action)
    except ValueError:
        accepted = ", ".join(a.value for a in ToolsetAction)
        parsed_action = ToolsetAction.LIST
        refused = f"unknown toolsets action {action!r}; accepted: {accepted}"

    if refused is None and parsed_action in (ToolsetAction.ACTIVATE, ToolsetAction.DEACTIVATE):
        try:
            toolset = Toolset(str(name or ""))
        except ValueError:
            accepted = ", ".join(t.value for t in Toolset)
            refused = f"unknown toolset {name!r}; accepted: {accepted}"
        else:
            if parsed_action is ToolsetAction.ACTIVATE:
                if toolset in active:
                    pass
                elif len(active) >= MAX_ACTIVE_TOOLSETS:
                    refused = f"at most {MAX_ACTIVE_TOOLSETS} toolsets may be active; deactivate one first"
                else:
                    active.add(toolset)
                    changed = True
            elif toolset in active:
                active.discard(toolset)
                changed = True

    group_payload: tuple[dict[str, object], ...] = tuple(
        {
            "toolset": group.toolset.value,
            "member_count": member_counts[group.toolset],
            "active": group.toolset in active,
        }
        for group in groups
    )
    return ToolsetManageResult(
        action=parsed_action.value,
        changed=changed,
        active=tuple(sorted(t.value for t in active)),
        groups=group_payload,
        refused=refused,
    )


def meta_execute(
    command_key: str,
    arguments: dict[str, object],
    *,
    descriptors: tuple[McpToolDescriptor, ...],
    persona: AgentPersona | None,
    run: ToolRunner,
) -> MetaExecuteResult:
    """Execute one command key through the same gates as a direct tool call.

    Resolves the descriptor, applies :func:`gate_refusal`, and only on a clear
    gate invokes the injected ``run`` dispatcher. An unknown command key is
    refused; a gated one carries its refusal and never reaches ``run``.

    Returns:
        The :class:`MetaExecuteResult` for the call.
    """
    descriptor = next((candidate for candidate in descriptors if candidate.command_key == command_key), None)
    if descriptor is None:
        return MetaExecuteResult(command_key=command_key, refused=f"unknown command: {command_key}")
    refusal = gate_refusal(persona=persona, descriptor=descriptor)
    if refusal is not None:
        return MetaExecuteResult(command_key=command_key, refused=refusal)
    outcome = run(descriptor, arguments)
    return MetaExecuteResult(command_key=command_key, envelope=outcome.envelope, is_error=outcome.is_error)
