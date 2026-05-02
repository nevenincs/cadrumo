"""``aeat browser`` sub-app — Playwright browser session health probes.

A small, directory-backed sub-app that mirrors the convention used by
:mod:`aeat.entrypoints.cli.workflow`. Today the only command is
``health``; additional browser-layer operations can be added by landing
new modules in this package. See
:func:`aeat.entrypoints.cli.browser.health.health_cmd` for the locked
exit-code table.
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


__all__ = ["app"]
