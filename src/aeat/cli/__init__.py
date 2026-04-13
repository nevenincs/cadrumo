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
from aeat.cli import browser as browser_module
from aeat.cli import casillas as casillas_module
from aeat.cli import categories as categories_module
from aeat.cli import cloud as cloud_module
from aeat.cli import deadlines as deadlines_module
from aeat.cli import docs as docs_module
from aeat.cli import doctor as doctor_module
from aeat.cli import drive as drive_module
from aeat.cli import filing as filing_module
from aeat.cli import inbox as inbox_module
from aeat.cli import justificante as justificante_module
from aeat.cli import llm as llm_module
from aeat.cli import manual as manual_module
from aeat.cli import normatives as normatives_module
from aeat.cli import oauth as oauth_module
from aeat.cli import setup as setup_wizard_module
from aeat.cli import sheets as sheets_module
from aeat.cli import status as status_module
from aeat.cli import submission as submission_module
from aeat.cli import sync as sync_module
from aeat.cli import vat as vat_module
from aeat.cli import workflow as workflow_module

app = typer.Typer(
    name="aeat",
    help="AEAT automation CLI: Google Workspace + GCP helpers and health checks.",
    no_args_is_help=True,
    add_completion=False,
)


@app.command(name="hello", help="Smoke test command - prints a greeting and exits 0.")
def hello() -> None:
    """Sanity check command preserved for the base smoke tests."""
    typer.echo("Hello from AEAT CLI")


app.command(name="doctor", help="Report Google Workspace + GCP health for this workstation.")(doctor_module.doctor)
app.command(name="bootstrap", help="Provision scratch resources and persist their IDs to env/.env.")(
    bootstrap_module.bootstrap
)
app.add_typer(browser_module.app, name="browser", help="Playwright browser session health probes (#95).")
app.add_typer(casillas_module.app, name="casillas", help="Curated AEAT casilla catalogue helpers.")
app.add_typer(categories_module.app, name="categories", help="AEAT spending-category taxonomy helpers (#77).")
app.add_typer(drive_module.app, name="drive", help="Google Drive helpers.")
app.add_typer(sheets_module.app, name="sheets", help="Google Sheets helpers.")
app.add_typer(docs_module.app, name="docs", help="Google Docs helpers.")
app.add_typer(cloud_module.app, name="cloud", help="GCP product helpers (Functions / Run / Storage).")
app.add_typer(llm_module.app, name="llm", help="LLM prompt, translation, cache, and usage helpers.")
app.add_typer(oauth_module.app, name="oauth-client", help="OAuth 2.0 Desktop client provisioning.")
app.add_typer(manual_module.app, name="manual", help="AEAT Manual práctico corpus helpers (#25).")
app.add_typer(normatives_module.app, name="normatives", help="Spanish tax normatives corpus helpers (#45).")
app.add_typer(vat_module.app, name="vat", help="Spanish VAT (IVA) taxonomy + rules (#85).")
app.add_typer(sync_module.app, name="sync", help="Self-healing live-to-local sync runner (#11).")
app.add_typer(deadlines_module.app, name="deadlines", help="Filing-deadline computation engine (#38).")
app.add_typer(filing_module.app, name="filing", help="Filing draft engine commands (#39).")
app.add_typer(status_module.app, name="status", help="Live AEAT status reader (#43).")
app.add_typer(submission_module.app, name="submission", help="Filing submission engine (#42).")
app.add_typer(inbox_module.app, name="inbox", help="AEAT notifications inbox (#46).")
app.add_typer(workflow_module.app, name="workflow", help="End-user composite workflow engine (#59).")
app.add_typer(
    justificante_module.app,
    name="justificante",
    help="AEAT justificante (PDF receipt) parser and live CSV verifier (#44).",
)
app.add_typer(setup_wizard_module.app, name="setup", help="First-run interactive setup wizard (#61).")


__all__ = ["app"]
