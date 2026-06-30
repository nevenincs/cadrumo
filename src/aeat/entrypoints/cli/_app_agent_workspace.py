"""CLI command for ``aeat app agent materialise``.

Materialises the shipped operator harness (rules, personas, skills) into an
operator-chosen directory so an end-user agent runtime can load them. This is the
distinct end-user operator workspace, never the repository's vaultspec developer
``.claude/`` tree. It writes only reviewed harness markdown - no secrets, no tax
data - and computes no value.

A child of ``app`` (the CLI root surface stays pinned to ``config`` and ``app``).
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...agent import materialise_workspace
from ...core.i18n import tr
from ...core.logging import get_logger
from ._app_agent_workspace_payloads import AgentWorkspaceResult
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
) -> None:
    """Write the shipped operator harness into ``--output`` for an agent runtime.

    A group-callback (like ``aeat app contract``) so it never enters the bucket
    session: the materialiser is profile-independent - it reads shipped harness
    data and writes it to an operator directory, needing no active profile or
    secret store.
    """
    if ctx.invoked_subcommand is not None:
        return
    manifest = materialise_workspace(output)
    result = AgentWorkspaceResult.model_validate(manifest.model_dump(mode="json"))
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
    _emit_envelope(ctx, command="agent", result=result, lines=lines)
    raise typer.Exit()
