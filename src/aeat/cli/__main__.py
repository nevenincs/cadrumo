"""Root Typer application for the ``aeat`` CLI.

Wires every sub-app under one entry point so ``uv run aeat --help``
lists the full command tree. Sub-apps are imported lazily inside
sub-app factories to keep startup fast even as the dependency graph
grows (every Google client library at module load is several hundred
milliseconds).
"""

from __future__ import annotations

import typer

from aeat.cli import bootstrap as bootstrap_module
from aeat.cli import cloud as cloud_module
from aeat.cli import docs as docs_module
from aeat.cli import doctor as doctor_module
from aeat.cli import drive as drive_module
from aeat.cli import oauth as oauth_module
from aeat.cli import sheets as sheets_module

app = typer.Typer(
    name="aeat",
    help="AEAT automation CLI: Google Workspace + GCP helpers and health checks.",
    no_args_is_help=True,
    add_completion=False,
)

app.command(name="doctor", help="Report Google Workspace + GCP health for this workstation.")(doctor_module.doctor)
app.command(name="bootstrap", help="Provision scratch resources and persist their IDs to env/.env.")(
    bootstrap_module.bootstrap
)
app.add_typer(drive_module.app, name="drive", help="Google Drive helpers.")
app.add_typer(sheets_module.app, name="sheets", help="Google Sheets helpers.")
app.add_typer(docs_module.app, name="docs", help="Google Docs helpers.")
app.add_typer(cloud_module.app, name="cloud", help="GCP product helpers (Functions / Run / Storage).")
app.add_typer(oauth_module.app, name="oauth-client", help="OAuth 2.0 Desktop client provisioning.")


if __name__ == "__main__":
    app()
