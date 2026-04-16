"""``aeat browser`` sub-app — Playwright browser diagnostics.

A small, directory-backed sub-app that mirrors the convention used by
:mod:`aeat.cli.status` and :mod:`aeat.cli.workflow`. The current
commands are ``health`` for public site-health probing and
``verify-cert`` for read-only client-certificate verification.

See [[2026-04-13-aeat-mantenimiento-detection-adr]] for the exit-code
table locked into :func:`aeat.cli.browser.health.health_cmd`.
"""

from __future__ import annotations

import typer

from aeat.cli.browser import health as _health_module
from aeat.cli.browser import verify_cert as _verify_cert_module

app = typer.Typer(
    name="browser",
    help="Playwright browser session health probes and diagnostics.",
    no_args_is_help=True,
    add_completion=False,
)

app.command("health", help="Probe the AEAT site-health endpoint.")(_health_module.health_cmd)
app.command("verify-cert", help="Verify AEAT client-certificate handshake and one read-only expedientes fetch.")(
    _verify_cert_module.verify_cert_cmd
)


__all__ = ["app"]
