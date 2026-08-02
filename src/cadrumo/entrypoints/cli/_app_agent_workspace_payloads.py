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

from ._schemas import OutputSchema, register_schema


class AgentLayout(StrEnum):
    """The materialisation target the ``aeat app agent`` command emits."""

    WORKSPACE = "workspace"
    """The Claude-native project mirror: ``.claude/{rules,agents,skills}``."""
    PLUGIN = "plugin"
    """A one-click Claude plugin: ``.claude-plugin/`` + ``skills/`` + ``agents/``."""


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
            if self.rules_written is None or self.personas_written is None:
                raise ValueError("workspace layout requires rules_written and personas_written")
            unexpected = ("plugin_name", "version", "agents_written", "persona_default")
        else:
            missing = [
                name
                for name in ("plugin_name", "version", "agents_written", "persona_default")
                if getattr(self, name) is None
            ]
            if missing:
                raise ValueError(f"plugin layout requires {missing}")
            unexpected = ("rules_written", "personas_written")
        contaminated = [name for name in unexpected if getattr(self, name) is not None]
        if contaminated:
            raise ValueError(f"{self.layout.value} layout forbids {contaminated}")
        return self
