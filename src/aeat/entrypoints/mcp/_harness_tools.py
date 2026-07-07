"""The ``harness.load`` floor tool: the universal operating-layer delivery channel.

ADR R4 decides the operating layer reaches an arbitrary client through four
channels, floor-first. This module owns the FLOOR: a single read-only tool that
returns the shipped operator operating rules plus the active persona document as
text. A tool is the only channel guaranteed to reach a model on a minimal
tools-only client (``prompts`` and ``resources`` are negotiated capabilities a
client may not support), so this tool is the one delivery path that always
works. It is advertised on every session regardless of the active persona - the
floor must never be scoped away - and is annotated ``readOnlyHint`` because it
reads shipped harness data and computes nothing.

Like ``_tools`` and ``_meta_tools``, this module is SDK-independent pure
functions over typed models: :func:`build_harness_floor_payload` and
:func:`render_harness_floor_text` carry no protocol detail and are unit-tested
directly, while :func:`build_harness_floor_tool` lazily adapts the payload
surface onto the MCP SDK's ``Tool`` type so the module still imports (and the
server still refuses gracefully) when the ``aeat-cli[agent]`` extra is absent.

The operating-layer text is read through the ``aeat.agent`` package facade
(:func:`~agent.operator_rules_text` and
:func:`~agent.iter_personas`), never a private submodule, per the
``service-imports-via-top-level-reexports`` discipline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from ...agent import iter_personas, operator_rules_text
from ...core.external_constants import UTF_8_ENCODING as _UTF_8
from ...core.i18n import tr
from ._persona_scope import AgentPersona

if TYPE_CHECKING:
    # Typing-only: the MCP SDK is an optional runtime dependency (``aeat-cli[agent]``);
    # the real import stays deferred to inside the function body below.
    from mcp.types import Tool

#: The floor tool's MCP name, following the per-verb ``aeat_<key>`` naming
#: convention (``_dispatch.tool_name_for_command``): the conceptual
#: ``harness.load`` verb renders as ``aeat_harness_load``.
HARNESS_LOAD_TOOL = "aeat_harness_load"

_MARKDOWN_SUFFIX = ".md"

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

#: The default (English) off-host consent disclosure. Localized through
#: ``mcp.harness.off_host_consent``; carried verbatim here as the ``tr`` default
#: so the disclosure survives even if the locale catalogue is unavailable.
_OFF_HOST_CONSENT_DEFAULT = (
    "Privacy notice — read before continuing. This console is operated by an AI "
    "assistant running on your chosen LLM provider. Your words, and the figures the "
    "assistant works with (amounts, casilla values, obligations), are sent to that "
    "provider to operate the console. Your SOURCE DOCUMENTS — invoices, bank "
    "statements, and any evidence bytes — NEVER leave your machine: they stay in "
    "encrypted local storage and are never transmitted. If you are acting for a "
    "third party (a gestor or professional), confirm this is acceptable before you "
    "proceed."
)


def off_host_consent_text() -> str:
    """Return the localized off-host consent disclosure (ADR R9).

    A standing disclosure carried on every floor load rather than a stateful
    "first-run" flag: the floor is the read-first channel a client loads at the
    start of a session, so surfacing the disclosure here guarantees it reaches
    the operator BEFORE the first off-host-visible interaction, on every session,
    with no fragile first-run state that a returning session could skip.
    """
    return tr("mcp.harness.off_host_consent", default=_OFF_HOST_CONSENT_DEFAULT)


class ActivePersonaDocument(BaseModel):
    """The active persona's shipped document, resolved for the floor payload."""

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    text: str = Field(min_length=1)


class HarnessFloorPayload(BaseModel):
    """The floor tool's structured result: operator rules plus the active persona.

    ``off_host_consent`` is the standing R9 privacy disclosure (the operator's
    words + figures go off-host to the LLM provider; source documents never leave
    the machine), surfaced first so it is read before any off-host-visible
    interaction. ``operator_rules`` is the concatenated shipped operator
    operating-rule text - the always-on operating contract every session carries.
    ``active_persona`` is the persona document resolved from the session's
    ``AEAT_MCP_PERSONA`` scope, or ``None`` for an un-personified session (the
    full, unscoped surface).
    """

    model_config = _STRICT_FROZEN

    off_host_consent: str = Field(min_length=1)
    operator_rules: str = Field(min_length=1)
    active_persona: ActivePersonaDocument | None = None


def _persona_document_text(persona: AgentPersona) -> str | None:
    """Return the shipped persona document text for ``persona``, or ``None``.

    The persona file stems under ``aeat/_data/agent/personas/`` match the
    :class:`AgentPersona` values exactly, so ``persona.value + ".md"`` is the
    document name. Reads through the ``iter_personas`` package facade.
    """
    target = persona.value + _MARKDOWN_SUFFIX
    for document in iter_personas():
        if document.name == target:
            return document.read_text(encoding=_UTF_8)
    return None


def build_harness_floor_payload(*, persona: AgentPersona | None) -> HarnessFloorPayload:
    """Build the floor payload for ``persona`` (``None`` = un-personified session).

    Reads the shipped operator rules verbatim and, when a persona is active,
    its document verbatim. A persona whose document is somehow absent yields a
    ``None`` ``active_persona`` rather than raising: the floor's rules half must
    always deliver even if a persona document is missing.

    Returns:
        The :class:`HarnessFloorPayload` for the session.
    """
    active: ActivePersonaDocument | None = None
    if persona is not None:
        text = _persona_document_text(persona)
        if text is not None:
            active = ActivePersonaDocument(name=persona.value, text=text)
    return HarnessFloorPayload(
        off_host_consent=off_host_consent_text(),
        operator_rules=operator_rules_text(),
        active_persona=active,
    )


def render_harness_floor_text(payload: HarnessFloorPayload) -> str:
    """Render the floor payload as one markdown document for the tool's text content.

    The consent disclosure leads, then the shipped rules and persona texts are
    embedded verbatim under headings, so a tools-only client that reads only the
    text block still receives the disclosure first and the whole operating layer.
    The structured content carries the same texts as discrete fields for a client
    that prefers to parse them.
    """
    parts = [
        "# privacy notice (read first)",
        "",
        payload.off_host_consent,
        "",
        "# aeat operator operating rules",
        "",
        payload.operator_rules,
    ]
    if payload.active_persona is not None:
        parts += ["", f"# active persona: {payload.active_persona.name}", "", payload.active_persona.text]
    return "\n".join(parts)


def build_harness_floor_tool() -> Tool:
    """Build the SDK ``Tool`` object for the ``harness.load`` floor tool.

    Lazily imports the SDK types so the module still imports when the
    ``aeat-cli[agent]`` extra is absent. The tool takes no arguments (the active
    persona is resolved server-side from the session scope) and is annotated
    ``readOnlyHint`` / ``idempotentHint``: it reads shipped data and never
    mutates state.

    Returns:
        The ``harness.load`` :class:`~mcp.types.Tool` object.
    """
    from mcp.types import Tool, ToolAnnotations

    return Tool(
        name=HARNESS_LOAD_TOOL,
        description=(
            "Load the aeat operator operating rules and the active persona document as text - "
            "the universal harness floor that reaches any tools-only MCP client."
        ),
        inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
        annotations=ToolAnnotations(
            title="Load the operator harness",
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
        ),
    )


__all__ = [
    "HARNESS_LOAD_TOOL",
    "ActivePersonaDocument",
    "HarnessFloorPayload",
    "build_harness_floor_payload",
    "build_harness_floor_tool",
    "off_host_consent_text",
    "render_harness_floor_text",
]
