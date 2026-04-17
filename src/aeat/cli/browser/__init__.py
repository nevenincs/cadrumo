"""``aeat browser`` sub-app — Playwright browser session health probes.

A small, directory-backed sub-app that mirrors the convention used by
:mod:`aeat.cli.status` and :mod:`aeat.cli.workflow`. Today the only
command is ``health``; additional browser-layer operations can be
added by landing new modules in this package.

See [[2026-04-13-aeat-mantenimiento-detection-adr]] for the exit-code
table locked into :func:`aeat.cli.browser.health.health_cmd`.
"""

from __future__ import annotations

import typer

from . import health as _health_module

app = typer.Typer(
    name="browser",
    help="Playwright browser session health probes and diagnostics.",
    no_args_is_help=True,
    add_completion=False,
)

app.command("health", help="Probe the AEAT site-health endpoint.")(_health_module.health_cmd)


@app.command("_reserved", hidden=True, help="Reserved placeholder to keep `browser` multi-command.")
def _reserved_cmd() -> None:
    """No-op command.

    Present to stop Typer from collapsing the ``browser`` sub-app to
    a single-command shape (which would break
    ``aeat browser health``). Will be replaced by additional browser
    commands in follow-up work.
    """
    return None


__all__ = ["app"]
