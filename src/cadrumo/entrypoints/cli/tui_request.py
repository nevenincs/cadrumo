"""Request the TUI through the invocation's supplied presentation service."""

import typer

from .invocation_services import invocation_services


def launch_tui(ctx: typer.Context) -> None:
    """Let the managing host launch and own the requested interface."""
    invocation_services(ctx).launch_tui()
