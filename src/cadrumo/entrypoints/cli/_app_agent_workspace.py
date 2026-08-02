"""CLI command for ``aeat app agent``.

Materialises the shipped operator harness into an operator-chosen directory in
the Claude-native layout: ``.claude/skills/<name>/SKILL.md``,
``.claude/agents/<persona>.md``, ``.claude/rules/<rule>.md``, and a root
``CLAUDE.md`` importing every rule. This is the optional Claude-native mirror of
the operating layer - the MCP console is the primary, client-agnostic channel.
The written tree is the operator's own end-user workspace, never the
repository's own developer ``.claude/`` tree. It writes only reviewed harness
markdown - no secrets, no tax data - and computes no value.

A child of ``app`` (the CLI root surface stays pinned to ``config`` and ``app``).
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...agent import materialise_plugin, materialise_workspace
from ...core.i18n import tr
from ...core.logging import get_logger
from ._app_agent_workspace_payloads import AgentLayout, AgentWorkspaceResult
from ._common import _emit_envelope

logger = get_logger(__name__)

app = typer.Typer(
    name="agent",
    help=tr("cli.agent.app_help"),
    no_args_is_help=False,
    invoke_without_command=True,
)


@app.callback()
def materialise(
    ctx: typer.Context,
    output: Path = typer.Option(
        ...,
        "--output",
        "-o",
        help=tr("cli.agent.materialise.output_help"),
    ),
    layout: AgentLayout = typer.Option(
        AgentLayout.WORKSPACE,
        "--layout",
        help=tr("cli.agent.materialise.layout_help"),
    ),
) -> None:
    """Write the shipped operator harness into ``--output`` for an agent runtime.

    ``--layout workspace`` (default) writes the Claude-native project mirror
    (``.claude/{rules,agents,skills}`` + ``CLAUDE.md``); ``--layout plugin``
    writes a one-click Claude plugin (``.claude-plugin/plugin.json`` + ``skills/``
    + ``agents/`` + ``.mcp.json``). A group-callback (like ``aeat app contract``)
    so it never enters the bucket session: the materialiser is profile-independent
    - it reads shipped harness data and writes it to an operator directory,
    needing no active profile or secret store.
    """
    if ctx.invoked_subcommand is not None:
        return
    if layout is AgentLayout.PLUGIN:
        result, lines = _materialise_plugin_layout(output)
    else:
        result, lines = _materialise_workspace_layout(output)
    _emit_envelope(ctx, command="agent", result=result, lines=lines)
    raise typer.Exit()


def _materialise_workspace_layout(output: Path) -> tuple[AgentWorkspaceResult, list[str]]:
    manifest = materialise_workspace(output)
    result = AgentWorkspaceResult(
        layout=AgentLayout.WORKSPACE,
        output_path=manifest.output_path,
        skills_written=manifest.skills_written,
        rules_written=manifest.rules_written,
        personas_written=manifest.personas_written,
    )
    lines = [
        tr(
            "cli.agent.materialise.summary",
            default="Wrote operator workspace to {path}: {rules} rules, {personas} personas, {skills} skills.",
            path=manifest.output_path,
            rules=str(manifest.rules_written),
            personas=str(manifest.personas_written),
            skills=str(manifest.skills_written),
        ),
    ]
    return result, lines


def _materialise_plugin_layout(output: Path) -> tuple[AgentWorkspaceResult, list[str]]:
    manifest = materialise_plugin(output)
    result = AgentWorkspaceResult(
        layout=AgentLayout.PLUGIN,
        output_path=manifest.output_path,
        skills_written=manifest.skills_written,
        plugin_name=manifest.plugin_name,
        version=manifest.version,
        agents_written=manifest.agents_written,
        persona_default=manifest.persona_default,
    )
    lines = [
        tr(
            "cli.agent.materialise.plugin_summary",
            default="Wrote Claude plugin to {path}: {skills} skills, {agents} agents ({name} v{version}).",
            path=manifest.output_path,
            skills=str(manifest.skills_written),
            agents=str(manifest.agents_written),
            name=manifest.plugin_name,
            version=manifest.version,
        ),
    ]
    return result, lines
