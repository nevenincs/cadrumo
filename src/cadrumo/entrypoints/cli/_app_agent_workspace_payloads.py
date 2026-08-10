"""Typed ``--json`` payload for ``aeat app agent``.

The ``agent`` command materialises the shipped operator harness into an
operator-chosen directory in one of two layout targets: the Claude-native
``workspace`` mirror (``.claude/{rules,agents,skills}`` + ``CLAUDE.md``) or a
one-click Claude ``plugin`` (``.claude-plugin/plugin.json`` + ``skills/`` +
``agents/`` + ``.mcp.json``). Both layouts ride the SAME ``agent`` envelope
(one registered schema per command leaf), so the result is a single strict
:class:`OutputSchema` whose ``layout`` field discriminates which layout-specific
counts are populated.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import Field, model_validator

from ...core.json_contract import OutputSchema, register_schema


class AgentLayout(StrEnum):
    """The materialisation target the ``aeat app agent`` command emits."""

    WORKSPACE = "workspace"
    """The Claude-native project mirror: ``.claude/{rules,agents,skills}``."""
    PLUGIN = "plugin"
    """A one-click Claude plugin: ``.claude-plugin/`` + ``skills/`` + ``agents/``."""


_WORKSPACE_LAYOUT_FIELDS = ("rules_written", "personas_written")
_PLUGIN_LAYOUT_FIELDS = ("plugin_name", "version", "agents_written", "persona_default")


def _absent_field_names(result: AgentWorkspaceResult, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if getattr(result, name) is None]


def _present_field_names(result: AgentWorkspaceResult, names: tuple[str, ...]) -> list[str]:
    return [name for name in names if getattr(result, name) is not None]


@register_schema("agent")
class AgentWorkspaceResult(OutputSchema):
    """JSON result of materialising the operator harness.

    ``layout`` discriminates the two targets. The ``workspace`` layout populates
    ``rules_written`` / ``personas_written`` (mirroring the application
    ``WorkspaceManifest``); the ``plugin`` layout populates the plugin
    ``plugin_name`` / ``version`` / ``agents_written`` / ``persona_default``
    summary (mirroring ``PluginManifest``). ``output_path`` and ``skills_written``
    are common to both.
    """

    layout: AgentLayout = AgentLayout.WORKSPACE
    output_path: str = Field(min_length=1)
    skills_written: int = Field(ge=0)
    # Workspace layout summary.
    rules_written: int | None = Field(default=None, ge=0)
    personas_written: int | None = Field(default=None, ge=0)
    # Plugin layout summary.
    plugin_name: str | None = Field(default=None, min_length=1)
    version: str | None = Field(default=None, min_length=1)
    agents_written: int | None = Field(default=None, ge=0)
    persona_default: str | None = None

    @model_validator(mode="after")
    def _require_layout_fields(self) -> AgentWorkspaceResult:
        """Enforce that the fields the declared layout produces are populated."""
        if self.layout is AgentLayout.WORKSPACE:
            if _absent_field_names(self, _WORKSPACE_LAYOUT_FIELDS):
                raise ValueError("workspace layout requires rules_written and personas_written")
            unexpected = _PLUGIN_LAYOUT_FIELDS
        else:
            missing = _absent_field_names(self, _PLUGIN_LAYOUT_FIELDS)
            if missing:
                raise ValueError(f"plugin layout requires {missing}")
            unexpected = _WORKSPACE_LAYOUT_FIELDS
        contaminated = _present_field_names(self, unexpected)
        if contaminated:
            raise ValueError(f"{self.layout.value} layout forbids {contaminated}")
        return self
