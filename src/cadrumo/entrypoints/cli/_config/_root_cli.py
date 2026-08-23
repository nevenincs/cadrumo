"""Import-light executable callback for the config root."""

from __future__ import annotations

import typer

from ....core.i18n import tr
from .._command_policy import command_execution_policy
from .._common import _emit_envelope
from ._execution_policies import STATE_FREE


@command_execution_policy(STATE_FREE)
def config_root(
    ctx: typer.Context,
    help_: bool = typer.Option(False, "--help", "-h", help=tr("cli.config.workflow_help"), is_eager=True),
) -> None:
    """Render config-level workflow help when requested."""
    if not help_ and ctx.invoked_subcommand is not None:
        return
    from ....application.operator_surface import build_help_document, render_help_text
    from .._config_payloads import ConfigHelpEntryPayload, ConfigHelpSectionPayload, ConfigRootResult

    document = build_help_document("config")
    result = ConfigRootResult(
        surface=document.surface,
        heading=document.heading,
        paragraphs=list(document.paragraphs),
        sections=[
            ConfigHelpSectionPayload(
                title=section.title,
                entries=[
                    ConfigHelpEntryPayload(command=entry.command, description=entry.description)
                    for entry in section.entries
                ],
            )
            for section in document.sections
        ],
        footer=document.footer,
    )
    _emit_envelope(
        ctx,
        command="root.config",
        result=result,
        lines=render_help_text(document).splitlines(),
    )
    raise typer.Exit()
