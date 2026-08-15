"""The ``harness.load`` floor tool: the universal operating-layer delivery channel.

The operating layer reaches an arbitrary client through four
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
server still refuses gracefully) when the ``cadrumo[agent]`` extra is absent.

The operating-layer text is read through the ``cadrumo_harness`` package facade
(:func:`~agent.operator_rules_text` and
:func:`~agent.iter_personas`), never a private submodule, per the
``aeat-architecture-boundaries`` discipline.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Final

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.application.wizard import ensure_profile_keys_registered
from cadrumo.application.workflow import ProfileHealthStatus, assess_active_profile_health
from cadrumo.core.external_constants import UTF_8_ENCODING as _UTF_8
from cadrumo.core.i18n import tr
from cadrumo.core.json_contract import ResolvedPreconditionAction

from .. import iter_personas, operator_rules_text
from ._persona_scope import AgentPersona

if TYPE_CHECKING:
    # Typing-only: the MCP SDK is an optional runtime dependency (``cadrumo[agent]``);
    # the real import stays deferred to inside the function body below.
    from mcp.types import Tool

#: The floor tool's MCP name, following the per-verb ``cadrumo_<key>`` naming
#: convention (``_dispatch.tool_name_for_command``): the conceptual
#: ``harness.load`` verb renders as ``cadrumo_harness_load``.
HARNESS_LOAD_TOOL = "cadrumo_harness_load"

#: The identity-assertion tool's MCP name. Like the floor and
#: grounding tools it is a read-only console tool carrying the ``cadrumo_``
#: prefix; unlike the per-verb surface it is always advertised and never
#: persona-scoped away, so an agent can always confirm the active taxpayer.
WHOAMI_TOOL = "cadrumo_whoami"

_MARKDOWN_SUFFIX = ".md"
_TAX_ID_FACT_PATH: Final[str] = "identity.tax_id"

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
    """Return the localized off-host consent disclosure.

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


class WhoamiIdentity(BaseModel):
    """The active taxpayer identity block returned by the ``whoami`` tool.

    The identity anchor the agent reconciles before a mutating command: a
    filing must never run under the wrong profile (Erika must not file while
    Erik is the active profile). ``active_profile`` is the operator-chosen
    display LABEL (the plaintext manifest name, never the redacted
    profile/bucket UUID — the same label semantics the envelope-spine
    ``active_profile`` carries), or ``None`` when no profile is active.
    ``tax_id_present`` states whether the active profile carries a tax id
    (its legal identity). ``readiness`` is the active-profile health status
    (``ready`` / ``incomplete`` / ``none`` / a degraded-pointer status), and
    ``precondition_action`` is the strict recovery verdict from that same
    assessment, or ``None`` when the profile is ready.

    ``readiness`` carries the canonical
    :data:`~application.workflow.ProfileHealthStatus` taxonomy rather than a
    bare non-empty string. The projection always copies the health verdict, but
    an identity block built directly or rebuilt from a client's JSON could
    otherwise admit a value outside the taxonomy — and this block is what an
    agent reconciles before a mutating command, so an unrecognised readiness
    is a value the recovery logic has no branch for.
    """

    model_config = _STRICT_FROZEN

    active_profile: str | None = None
    tax_id_present: bool = False
    readiness: ProfileHealthStatus
    precondition_action: ResolvedPreconditionAction | None = None


class HarnessFloorPayload(BaseModel):
    """The floor tool's structured result: operator rules plus the active persona.

    ``off_host_consent`` is the standing R9 privacy disclosure (the operator's
    words + figures go off-host to the LLM provider; source documents never leave
    the machine), surfaced first so it is read before any off-host-visible
    interaction. ``operator_rules`` is the concatenated shipped operator
    operating-rule text - the always-on operating contract every session carries.
    ``active_persona`` is the persona document resolved from the session's
    ``CADRUMO_MCP_PERSONA`` scope, or ``None`` for an un-personified session (the
    full, unscoped surface). ``identity`` is the same active-taxpayer block the
    ``whoami`` tool returns, so session orientation (this floor tool's job)
    carries WHO is active; it is ``None`` when the caller does not inject it (the
    SDK-independent unit surface), resolved and passed in at the server boundary.
    """

    model_config = _STRICT_FROZEN

    off_host_consent: str = Field(min_length=1)
    operator_rules: str = Field(min_length=1)
    active_persona: ActivePersonaDocument | None = None
    identity: WhoamiIdentity | None = None


def _persona_document_text(persona: AgentPersona) -> str | None:
    """Return the shipped persona document text for ``persona``, or ``None``.

    The persona file stems under ``cadrumo/_data/agent/personas/`` match the
    :class:`AgentPersona` values exactly, so ``persona.value + ".md"`` is the
    document name. Reads through the ``iter_personas`` package facade.
    """
    target = persona.value + _MARKDOWN_SUFFIX
    for document in iter_personas():
        if document.name == target:
            return document.read_text(encoding=_UTF_8)
    return None


def build_harness_floor_payload(
    *,
    persona: AgentPersona | None,
    identity: WhoamiIdentity | None = None,
) -> HarnessFloorPayload:
    """Build the floor payload for ``persona`` (``None`` = un-personified session).

    Reads the shipped operator rules verbatim and, when a persona is active,
    its document verbatim. A persona whose document is somehow absent yields a
    ``None`` ``active_persona`` rather than raising: the floor's rules half must
    always deliver even if a persona document is missing.

    ``identity`` is the active-taxpayer block surfaced on the floor response so
    session orientation carries WHO is active. It stays a caller-injected
    parameter (defaulting ``None``) rather than being resolved here so this
    builder stays a pure function over shipped data: the server boundary
    resolves the runtime identity (which reads storage) and passes it in, the
    same resolve-at-the-boundary / inject-into-the-payload shape the envelope
    spine uses.

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
        identity=identity,
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
    if payload.identity is not None:
        parts += ["", "# active taxpayer identity", "", render_whoami_identity_text(payload.identity)]
    if payload.active_persona is not None:
        parts += ["", f"# active persona: {payload.active_persona.name}", "", payload.active_persona.text]
    return "\n".join(parts)


def build_harness_floor_tool() -> Tool:
    """Build the SDK ``Tool`` object for the ``harness.load`` floor tool.

    Lazily imports the SDK types so the module still imports when the
    ``cadrumo[agent]`` extra is absent. The tool takes no arguments (the active
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
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        annotations=ToolAnnotations(
            title="Load the operator harness",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
        ),
    )


def build_whoami_identity() -> WhoamiIdentity:
    """Resolve the active taxpayer identity block, best-effort.

    Wraps the active-profile health assessment
    (:func:`~application.workflow.assess_active_profile_health`): its
    ``status`` is the ``readiness`` and its typed precondition verdict is
    projected through the canonical CLI action resolver. The display LABEL is
    captured by the same health assessment - the
    same non-secret name the envelope-spine ``active_profile`` carries, never
    the redacted bucket/profile UUID the health projection's
    ``active_profile`` field holds. Reusing that captured value prevents a
    committed-capsule change between health assessment and identity rendering from
    mixing two profile snapshots. ``tax_id_present`` is derived from the health projection: a
    tax id is on file when the profile record is present and the canonical
    ``identity.tax_id`` fact path (:data:`_TAX_ID_FACT_PATH`)
    is not among the missing required fields, so it reports correctly even for
    an otherwise-incomplete profile. The health assessment never raises for an
    absent or unreadable profile (it returns a degraded status), and label
    resolution is guarded, so this read-only identity probe is safe to call on
    every session and before every mutation.

    The health assessment counts the process-global profile-key registry, which
    the domain layer cannot seed for itself, so this function seeds it through
    :func:`~application.wizard.ensure_profile_keys_registered` before reading.
    The call is idempotent and deliberately made here rather than left to the
    caller: this probe is reached both through the server handlers and directly,
    so depending on an initialisation order the caller must remember is what
    made a real server answer every identity call with a registration error.
    """
    ensure_profile_keys_registered()
    health = assess_active_profile_health()
    tax_id_present = health.profile_record_present and _TAX_ID_FACT_PATH not in health.missing_required
    from cadrumo.entrypoints.cli import resolve_cli_precondition_action

    return WhoamiIdentity(
        active_profile=health.active_profile_label,
        tax_id_present=tax_id_present,
        readiness=health.status,
        precondition_action=(
            resolve_cli_precondition_action(health.precondition_verdict)
            if health.precondition_verdict is not None
            else None
        ),
    )


def render_whoami_identity_text(identity: WhoamiIdentity) -> str:
    """Render the identity block as plain text for a tools-only MCP client."""
    label = identity.active_profile if identity.active_profile is not None else "(no active profile)"
    lines = [
        f"active profile: {label}",
        f"tax id on file: {'yes' if identity.tax_id_present else 'no'}",
        f"readiness: {identity.readiness}",
    ]
    if identity.precondition_action is not None:
        action = identity.precondition_action.model_dump(mode="json")
        lines.extend(
            f"precondition_action.{field_name}: "
            f"{json.dumps(action[field_name], ensure_ascii=False, sort_keys=True, separators=(',', ':'))}"
            for field_name in (
                "failed_condition_id",
                "evidence",
                "action",
                "argument_bindings",
                "missing_argument_names",
                "conditionality",
                "no_recovery_outcome",
            )
        )
    return "\n".join(lines)


def build_whoami_tool() -> Tool:
    """Build the SDK ``Tool`` object for the ``whoami`` identity tool.

    Lazily imports the SDK types so the module still imports when the
    ``cadrumo[agent]`` extra is absent. The tool takes no arguments and is
    annotated ``readOnlyHint`` / ``idempotentHint``: it reads the active-profile
    health projection and never mutates state. Its description states its
    identity-safety job so an agent calls it to confirm WHO is active before a
    mutation and again after a profile switch.

    Returns:
        The ``whoami`` :class:`~mcp.types.Tool` object.
    """
    from mcp.types import Tool, ToolAnnotations

    return Tool(
        name=WHOAMI_TOOL,
        description=(
            "Report which taxpayer profile is active right now: its display name (label), whether a "
            "tax id is on file, filing readiness, and any typed recovery verdict. Call this before any command that "
            "writes, files, or exports to confirm WHO you are acting for, and again after switching "
            "profiles - a filing must never run under the wrong identity (Erika must not file while "
            "Erik is the active profile)."
        ),
        input_schema={"type": "object", "properties": {}, "additionalProperties": False},
        annotations=ToolAnnotations(
            title="Confirm the active taxpayer identity",
            read_only_hint=True,
            destructive_hint=False,
            idempotent_hint=True,
        ),
    )


__all__ = [
    "HARNESS_LOAD_TOOL",
    "WHOAMI_TOOL",
    "ActivePersonaDocument",
    "HarnessFloorPayload",
    "WhoamiIdentity",
    "build_harness_floor_payload",
    "build_harness_floor_tool",
    "build_whoami_identity",
    "build_whoami_tool",
    "off_host_consent_text",
    "render_harness_floor_text",
    "render_whoami_identity_text",
]
