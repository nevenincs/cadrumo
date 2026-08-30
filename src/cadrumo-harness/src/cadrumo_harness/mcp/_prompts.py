"""Guided-workflow prompts: the user-controlled entry points of the console.

MCP prompts are the slash-command surface a client renders for the USER to
pick: invoking one drops the matching shipped skill — verbatim, as an
embedded resource — plus a short operating brief into the conversation, so the
model enters the workflow already carrying the playbook and its rules of
engagement. The catalogue is DERIVED from the shipped skill documents and
their structured ``applies_when`` metadata, never hand-listed, so a new skill
ships as a new prompt with zero registration and the surface cannot drift from
the data.

Like ``_tools`` and ``_dispatch``, this module is SDK-independent pure
functions over typed models; ``_server`` adapts :class:`PromptDocument` to the
MCP SDK's prompt types, mirroring how ``build_sdk_tools`` adapts descriptors.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from cadrumo.core.period import accepted_filing_period_patterns
from cadrumo.core.external_constants import UTF_8_ENCODING as _UTF_8

from .. import iter_skill_documents, operator_rules_text, parse_skill_metadata
from ._resources import HarnessResourceKind, resource_uri

_STRICT_FROZEN = ConfigDict(frozen=True, strict=True, validate_assignment=True, extra="forbid")

_MARKDOWN = "text/markdown"

ORIENTATION_PROMPT_NAME = "cadrumo-empezar"

#: The prompt argument names a period the operator FILES in, so the description
#: advertises the filing-scoped set, not the wider registry-coordinate union.
_PERIOD_ARGUMENT_DESCRIPTION = (
    "The AEAT period code. Accepted forms: " + "; ".join(accepted_filing_period_patterns()) + "."
)


class PromptNotFoundError(LookupError):
    """Raised when a prompt name does not resolve to a shipped guided workflow."""


class PromptArgumentSpec(BaseModel):
    """One declared argument a guided-workflow prompt accepts.

    SDK-independent; ``_server`` adapts it to the MCP ``PromptArgument`` type.
    All workflow arguments are optional - a workflow can start without a period
    and resolve it conversationally - so ``required`` defaults False.
    """

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    required: bool = False


#: The scoping arguments every guided workflow accepts. A workflow orchestrates a
#: filing over a period, so filing year and period parameterise it (the modelo is
#: implied by the workflow's own skill). Completions serve the accepted values.
_WORKFLOW_ARGUMENTS: tuple[PromptArgumentSpec, ...] = (
    PromptArgumentSpec(name="filing_year", description="The filing year, e.g. 2026."),
    PromptArgumentSpec(name="period", description=_PERIOD_ARGUMENT_DESCRIPTION),
)


class GuidedPrompt(BaseModel):
    """One entry in the prompt catalogue (the ``prompts/list`` row)."""

    model_config = _STRICT_FROZEN

    name: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str = Field(min_length=1)
    skill_name: str = ""
    arguments: tuple[PromptArgumentSpec, ...] = ()


class EmbeddedDocument(BaseModel):
    """A document embedded into the prompt's returned messages as a resource."""

    model_config = _STRICT_FROZEN

    uri: str = Field(min_length=1)
    mime_type: str = _MARKDOWN
    text: str = Field(min_length=1)


class PromptDocument(BaseModel):
    """The materialised ``prompts/get`` payload for one guided workflow.

    ``brief_text`` is the operating brief that precedes the embedded documents
    in the returned user message; ``embedded`` carries the skill (and, for the
    orientation prompt, the operator rules) verbatim so the client needs no
    follow-up resource read for the workflow to be fully loaded.
    """

    model_config = _STRICT_FROZEN

    prompt: GuidedPrompt
    brief_text: str = Field(min_length=1)
    embedded: tuple[EmbeddedDocument, ...] = Field(min_length=1)


def _skill_texts() -> dict[str, str]:
    texts: dict[str, str] = {}
    for skill in iter_skill_documents():
        parts = str(skill).replace("\\", "/").split("/")
        # skills/<name>/SKILL.md — the owning directory is the skill name.
        name = parts[-2] if len(parts) >= 2 else parts[-1]
        texts[name] = skill.read_text(encoding=_UTF_8)
    return texts


def _title_from(name: str) -> str:
    return name.replace("-", " ").capitalize()


def _workflow_brief(name: str, description: str) -> str:
    return (
        f"You are entering the guided workflow '{name}' on behalf of the taxpayer: "
        f"{description.strip()}\n\n"
        "Operating brief:\n"
        "- Follow the embedded skill playbook step by step; it is the shipped, "
        "reviewed procedure for this situation.\n"
        "- If the operating rules are not already loaded in this session, load "
        "them first with the harness rules tool.\n"
        "- The deterministic CLI computes every tax value; you orchestrate, "
        "relay, and explain in simple language. Never compute, estimate, or "
        "restate a figure from memory — quote tool results verbatim with their "
        "legal references.\n"
        "- Confirm which taxpayer profile is active before the first command "
        "that reads or writes taxpayer data.\n"
        "- The taxpayer files with AEAT themselves; nothing here submits "
        "anything, and you never describe a local artefact as filed or "
        "accepted."
    )


def _orientation_brief() -> str:
    return (
        "You are an assistant helping a taxpayer operate Cadrumo — a "
        "deterministic Spanish tax CLI exposed as tools. The embedded operator "
        "rules are your binding operating contract for the whole session; read "
        "them before acting.\n\n"
        "First moves:\n"
        "- Read the capability contract tool to learn what the console can do.\n"
        "- Confirm the active taxpayer profile before any data is touched.\n"
        "- Derive what the taxpayer owes from the overview surface; never "
        "assume an obligation from memory.\n"
        "- Then pick the guided workflow (prompt) that matches the taxpayer's "
        "situation, or proceed with the skill resources directly."
    )


def build_prompt_catalogue() -> tuple[GuidedPrompt, ...]:
    """Return the prompt catalogue: one guided workflow per shipped skill, plus orientation.

    Sorted by name for deterministic ``prompts/list`` output. Every skill's
    frontmatter is validated on the way through (a malformed skill fails
    loudly here rather than shipping a broken prompt).

    Returns:
        A :class:`GuidedPrompt`.
    """
    rows: list[GuidedPrompt] = [
        GuidedPrompt(
            name=ORIENTATION_PROMPT_NAME,
            title="Empezar con el asistente Cadrumo",
            description=(
                "Load the operator rules and orient the session: capability "
                "contract, active profile, and the taxpayer's derived "
                "obligations, before any workflow starts."
            ),
        ),
    ]
    for name, text in sorted(_skill_texts().items()):
        metadata = parse_skill_metadata(text)
        rows.append(
            GuidedPrompt(
                name=metadata.name,
                title=_title_from(metadata.name),
                description=metadata.description.strip(),
                skill_name=name,
                arguments=_WORKFLOW_ARGUMENTS,
            ),
        )
    return tuple(rows)


def _argument_scope_line(arguments: dict[str, str] | None) -> str:
    """Render the client-supplied prompt arguments as a scoping line for the brief."""
    if not arguments:
        return ""
    year = arguments.get("filing_year", "").strip()
    period = arguments.get("period", "").strip()
    parts = [part for part in (f"filing year {year}" if year else "", f"period {period}" if period else "") if part]
    if not parts:
        return ""
    return "\n\nScope for this run: " + ", ".join(parts) + "."


def prompt_document(name: str, arguments: dict[str, str] | None = None) -> PromptDocument:
    """Materialise one guided workflow's ``prompts/get`` payload.

    ``arguments`` are the client-supplied prompt arguments (filing year, period);
    when present they are appended to the operating brief as an explicit scope so
    the model enters the workflow already knowing the period it targets.

    Raises:
        PromptNotFoundError: When ``name`` is neither the orientation prompt
            nor a shipped skill's workflow.

    Returns:
        A :class:`PromptDocument`.
    """
    if name == ORIENTATION_PROMPT_NAME:
        catalogue = {row.name: row for row in build_prompt_catalogue()}
        return PromptDocument(
            prompt=catalogue[ORIENTATION_PROMPT_NAME],
            brief_text=_orientation_brief(),
            embedded=(
                EmbeddedDocument(
                    uri=resource_uri(HarnessResourceKind.RULE, "cadrumo-operating-rules"),
                    text=operator_rules_text(),
                ),
            ),
        )
    texts = _skill_texts()
    if name not in texts:
        raise PromptNotFoundError(
            f"unknown guided workflow '{name}'; prompts are derived from the shipped skills",
        )
    text = texts[name]
    metadata = parse_skill_metadata(text)
    prompt = GuidedPrompt(
        name=metadata.name,
        title=_title_from(metadata.name),
        description=metadata.description.strip(),
        skill_name=name,
        arguments=_WORKFLOW_ARGUMENTS,
    )
    return PromptDocument(
        prompt=prompt,
        brief_text=_workflow_brief(metadata.name, metadata.description) + _argument_scope_line(arguments),
        embedded=(EmbeddedDocument(uri=resource_uri(HarnessResourceKind.SKILL, name), text=text),),
    )


__all__ = [
    "ORIENTATION_PROMPT_NAME",
    "EmbeddedDocument",
    "GuidedPrompt",
    "PromptArgumentSpec",
    "PromptDocument",
    "PromptNotFoundError",
    "build_prompt_catalogue",
    "prompt_document",
]
