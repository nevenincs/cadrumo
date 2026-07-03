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

from pydantic import BaseModel, ConfigDict, Field

from ._hitl import ConfirmationPolicy, confirmation_for_tool
from ._persona_scope import AgentPersona, handoff_denial_message, is_handoff_denied, is_tool_in_persona_scope
from ._tools import McpToolDescriptor

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

#: The subprocess runner the server injects into :func:`meta_execute`: it takes a
#: descriptor and the named arguments and returns the CLI envelope plus an error
#: flag, exactly as the direct call path runs it.
ToolRunner = Callable[[McpToolDescriptor, dict[str, object]], tuple[dict[str, object], bool]]


class MetaSearchResult(BaseModel):
    """One command matched by :func:`search_commands`, with its decision hints."""

    model_config = _STRICT_FROZEN

    command_key: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    read_only: bool
    destructive: bool
    score: int = Field(ge=1)


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


def _query_tokens(query: str) -> tuple[str, ...]:
    return tuple(token for token in query.lower().replace("-", " ").replace(".", " ").split() if token)


def _score(descriptor: McpToolDescriptor, tokens: tuple[str, ...]) -> int:
    """Score a descriptor against the query tokens.

    A token in the command key weighs more than one only in the description, so a
    verb named for the query outranks a verb that merely mentions it.
    """
    key = descriptor.command_key.lower()
    description = descriptor.description.lower()
    total = 0
    for token in tokens:
        if token in key:
            total += 2
        elif token in description:
            total += 1
    return total


def search_commands(
    query: str,
    *,
    descriptors: tuple[McpToolDescriptor, ...],
    limit: int = 20,
) -> tuple[MetaSearchResult, ...]:
    """Rank the command surface against ``query`` for the ``search`` meta-tool.

    Every descriptor with a non-zero token overlap is returned, ordered by score
    then command key, capped at ``limit``. The result carries the read-only and
    destructive hints so the caller sees a verb's mutability before executing it.

    Returns:
        The matched commands, highest score first.

    Returns:
        A :class:`MetaSearchResult`.
    """
    tokens = _query_tokens(query)
    if not tokens:
        return ()
    scored = ((score, descriptor) for descriptor in descriptors if (score := _score(descriptor, tokens)) > 0)
    ordered = sorted(scored, key=lambda pair: (-pair[0], pair[1].command_key))
    return tuple(
        MetaSearchResult(
            command_key=descriptor.command_key,
            tool_name=descriptor.name,
            description=descriptor.description,
            read_only=descriptor.annotations.read_only_hint,
            destructive=descriptor.annotations.destructive_hint,
            score=score,
        )
        for score, descriptor in ordered[:limit]
    )


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
