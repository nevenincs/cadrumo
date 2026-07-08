"""The ``search`` + ``execute`` meta-tool pair for the long-tail verb surface.

The curated domain toolsets (``_toolsets``) cover the common path; the rest of
the operator-callable verb tree is reached through two meta-tools, the Cloudflare
precedent for a large API surface (ADR decision R2): ``search`` maps a natural
query onto matching command keys with their intent and mutability, and
``execute`` runs one command key with typed arguments.

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
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ...application.command_search import CommandDoc, CommandIndex, build_command_index
from ._hitl import ConfirmationPolicy, confirmation_for_tool
from ._persona_scope import AgentPersona, handoff_denial_message, is_handoff_denied, is_tool_in_persona_scope
from ._tools import McpToolDescriptor

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

#: The subprocess runner the server injects into :func:`meta_execute`: it takes a
#: descriptor and the named arguments and returns the CLI envelope plus an error
#: flag, exactly as the direct call path runs it.
ToolRunner = Callable[[McpToolDescriptor, dict[str, object]], tuple[dict[str, object], bool]]


class MetaSearchResult(BaseModel):
    """One command matched by :func:`search_commands`, with its decision hints.

    The result is self-sufficient (ADR ``mcp-progressive-discovery`` P2): besides
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


def _command_doc(descriptor: McpToolDescriptor) -> CommandDoc:
    """Build the searchable document for one command.

    The doc text unions the command key (its dotted tokens carry the verb-level
    vocabulary - ``calculate``, ``export``, ``iva_wallet``), the tool name, and
    the human description, so a concept query matches whichever field carries it.
    """
    key_tokens = descriptor.command_key.replace(".", " ").replace("_", " ")
    text = f"{descriptor.command_key} {key_tokens} {descriptor.name} {descriptor.description}"
    return CommandDoc(command_key=descriptor.command_key, tool_name=descriptor.name, text=text)


def build_command_search_index(descriptors: tuple[McpToolDescriptor, ...]) -> CommandIndex:
    """Build the hybrid command-search index over the descriptor set.

    Built once per server from the full descriptor set so ``search`` reaches the
    whole verb universe, not just the advertised surface.
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

    Backed by the hybrid command index (FTS5 lexical + Spanish stemming +
    diacritics folding, degrading to token overlap on a minimal install), so a
    concept query bridges the operator's vocabulary to the command's own tokens
    where a bare substring match would miss it (ADR ``mcp-progressive-discovery``
    P2). Each result carries the mutability hints AND the per-verb input schema so
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


def gate_refusal(*, persona: AgentPersona | None, descriptor: McpToolDescriptor) -> str | None:
    """Return the refusal a tool call incurs, or ``None`` when it may proceed.

    The single gate sequence run by BOTH the direct call path and ``execute``: an
    out-of-scope call is refused, then a persona's handoff-denied verb, then the
    permanent live-write block. The messages are byte-identical to the direct
    path's refusals, so the two entry points cannot diverge — the per-verb
    handoff deny (verifier-only export/record-marker, ADR R6(iii)) is enforced
    here STRUCTURALLY, not left to the sync path's incidental no-elicitation
    fallback.

    Returns:
        The refusal message, or ``None`` when the call is allowed.
    """
    if persona is not None and not is_tool_in_persona_scope(persona=persona, command_key=descriptor.command_key):
        return f"refused: {descriptor.command_key!r} is outside the active persona {persona.value!r}'s tool scope"
    if persona is not None and is_handoff_denied(persona=persona, command_key=descriptor.command_key):
        return handoff_denial_message(persona=persona, command_key=descriptor.command_key)
    if (
        confirmation_for_tool(command_key=descriptor.command_key, annotations=descriptor.annotations)
        is ConfirmationPolicy.BLOCK
    ):
        return "refused: AEAT live-write is permanently forbidden"
    return None


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
    envelope, is_error = run(descriptor, arguments)
    return MetaExecuteResult(command_key=command_key, envelope=envelope, is_error=is_error)
