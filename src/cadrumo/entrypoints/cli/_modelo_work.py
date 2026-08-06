"""Work-subcommand Typer construction for the modelo CLI surface."""

from __future__ import annotations

import typer

from ...core.i18n import tr


def create_work_app() -> typer.Typer:
    """Return the `modelo work` Typer group used by `_modelo` commands."""
    return typer.Typer(
        name="work",
        help=tr("cli.app.modelo.work.app_help"),
        no_args_is_help=True,
        add_completion=False,
    )


__all__ = ["create_work_app"]
