"""Import-light executable callback for the config root."""

from __future__ import annotations

import typer

from .._common import _emit_envelope


def config_root(
    ctx: typer.Context,
    help_: bool = False,
) -> None:
    """Render config-level workflow help when requested."""
    if not help_ and ctx.invoked_subcommand is not None:
        return
    from .._command_specs import COMMAND_GRAPH
    from .._tui_policy import enforce_tui_request

    enforce_tui_request(ctx, spec=COMMAND_GRAPH.by_key()["config"])
    from ....application.operator_surface import build_help_document, render_help_text
    from .._config_help_payloads import ConfigHelpEntryPayload, ConfigHelpSectionPayload, ConfigRootResult

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
        metadata_only=True,
    )
    raise typer.Exit()
