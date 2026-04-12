"""``aeat`` command-line surface.

Sub-modules expose Typer sub-apps that are wired into the root
``app`` exposed at the package root. The CLI is the primary developer
entry point for interacting with Google Workspace and GCP APIs from a
vanilla workstation; see ``aeat doctor`` for the single-command
health check and ``aeat bootstrap`` for the post-gcloud provisioning
step.

The package exposes ``app`` directly so the project entry point in
``pyproject.toml`` reads ``aeat = "aeat.cli:app"``, matching the
single-file convention introduced by the base module structure.
"""

from __future__ import annotations

import typer

from aeat.cli import bootstrap as bootstrap_module
from aeat.cli import cloud as cloud_module
from aeat.cli import docs as docs_module
from aeat.cli import doctor as doctor_module
from aeat.cli import drive as drive_module
from aeat.cli import filing as filing_module
from aeat.cli import llm as llm_module
from aeat.cli import manual as manual_module
from aeat.cli import oauth as oauth_module
from aeat.cli import sheets as sheets_module
from aeat.cli import sync as sync_module

app = typer.Typer(
    name="aeat",
    help="AEAT automation CLI: Google Workspace + GCP helpers and health checks.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command(name="hello", help="Smoke test command — prints a greeting and exits 0.")
def hello() -> None:
    """Sanity check command preserved for the base smoke tests."""
    typer.echo("Hello from AEAT CLI")


app.command(name="doctor", help="Report Google Workspace + GCP health for this workstation.")(doctor_module.doctor)
app.command(name="bootstrap", help="Provision scratch resources and persist their IDs to env/.env.")(
    bootstrap_module.bootstrap
)
app.add_typer(drive_module.app, name="drive", help="Google Drive helpers.")
app.add_typer(sheets_module.app, name="sheets", help="Google Sheets helpers.")
app.add_typer(docs_module.app, name="docs", help="Google Docs helpers.")
app.add_typer(cloud_module.app, name="cloud", help="GCP product helpers (Functions / Run / Storage).")
app.add_typer(llm_module.app, name="llm", help="LLM prompt, translation, cache, and usage helpers.")
app.add_typer(oauth_module.app, name="oauth-client", help="OAuth 2.0 Desktop client provisioning.")
app.add_typer(manual_module.app, name="manual", help="AEAT Manual práctico corpus helpers (#25).")
app.add_typer(sync_module.app, name="sync", help="Self-healing live-to-local sync runner (#11).")
app.add_typer(filing_module.app, name="filing", help="Filing draft engine commands (#39).")


__all__ = ["app"]
