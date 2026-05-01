"""``aeat cloud`` sub-app — GCP product helpers (Functions / Run / Storage).

Each sub-sub-app builds the dedicated ``google-cloud-*`` client lazily.
List operations are list-only and free; deploy is intentionally out of
scope for this feature (see the gsuite-bootstrap ADR).
"""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="cloud", no_args_is_help=True, help="GCP product helpers.")
functions_app = typer.Typer(name="functions", no_args_is_help=True, help="Cloud Functions v2 helpers.")
run_app = typer.Typer(name="run", no_args_is_help=True, help="Cloud Run v2 helpers.")
storage_app = typer.Typer(name="storage", no_args_is_help=True, help="Cloud Storage helpers.")

app.add_typer(functions_app, name="functions")
app.add_typer(run_app, name="run")
app.add_typer(storage_app, name="storage")


def _project() -> str:
    """Return the configured GCP project ID, or fail loudly."""
    from ...core.config import Settings

    project = Settings().google_cloud_project
    if not project:
        typer.secho("GOOGLE_CLOUD_PROJECT is empty in env/.env", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    return project


def _adc() -> Any:
    """Return ADC credentials with the cloud-platform scope."""
    from ...adapters.outbound.google import CLOUD_PLATFORM_SCOPE, get_credentials_for_scopes

    return get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])


# ── Cloud Functions ─────────────────────────────────────────────────────────


@functions_app.command(name="list", help="List Cloud Functions across all regions.")
def functions_list() -> None:
    """List every Cloud Function in the project (-).

    The ``-`` location wildcard returns functions from every region in
    a single call.
    """
    from ...adapters.outbound.google import build_cloudfunctions_client

    client = build_cloudfunctions_client(_adc())
    parent = f"projects/{_project()}/locations/-"
    table = Table(title="cloud functions", header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("State", style="white")
    table.add_column("Environment", style="dim")
    table.add_column("Update Time", style="dim")
    count = 0
    for function in client.list_functions(parent=parent):
        count += 1
        table.add_row(
            getattr(function, "name", ""),
            str(getattr(function, "state", "")),
            str(getattr(function, "environment", "")),
            str(getattr(function, "update_time", "")),
        )
    Console().print(table)
    typer.echo(f"{count} function(s)")


@functions_app.command(name="describe", help="Print one Cloud Function's metadata.")
def functions_describe(name: str = typer.Argument(..., help="Fully-qualified function name.")) -> None:
    """Print the full metadata for one function."""
    from ...adapters.outbound.google import build_cloudfunctions_client

    client = build_cloudfunctions_client(_adc())
    function = client.get_function(name=name)
    typer.echo(str(function))


# ── Cloud Run ───────────────────────────────────────────────────────────────


@run_app.command(name="list", help="List Cloud Run services across all regions.")
def run_list() -> None:
    """List every Cloud Run service in the project (-)."""
    from ...adapters.outbound.google import build_cloudrun_client

    client = build_cloudrun_client(_adc())
    parent = f"projects/{_project()}/locations/-"
    table = Table(title="cloud run services", header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Generation", style="white")
    table.add_column("Update Time", style="dim")
    count = 0
    for service in client.list_services(parent=parent):
        count += 1
        table.add_row(
            getattr(service, "name", ""),
            str(getattr(service, "generation", "")),
            str(getattr(service, "update_time", "")),
        )
    Console().print(table)
    typer.echo(f"{count} service(s)")


@run_app.command(name="describe", help="Print one Cloud Run service's metadata.")
def run_describe(name: str = typer.Argument(..., help="Fully-qualified service name.")) -> None:
    """Print full metadata for one Cloud Run service."""
    from ...adapters.outbound.google import build_cloudrun_client

    client = build_cloudrun_client(_adc())
    service = client.get_service(name=name)
    typer.echo(str(service))


# ── Cloud Storage ───────────────────────────────────────────────────────────


@storage_app.command(name="buckets", help="List Cloud Storage buckets in the project.")
def storage_buckets() -> None:
    """List Cloud Storage buckets visible in the project."""
    from ...adapters.outbound.google import build_storage_client

    client = build_storage_client(_adc(), _project())
    table = Table(title="cloud storage buckets", header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Location", style="white")
    table.add_column("Storage Class", style="dim")
    count = 0
    for bucket in client.list_buckets():
        count += 1
        table.add_row(bucket.name, bucket.location or "", bucket.storage_class or "")
    Console().print(table)
    typer.echo(f"{count} bucket(s)")


@storage_app.command(name="ls", help="List objects inside a bucket.")
def storage_ls(
    bucket: str = typer.Argument(..., help="Bucket name (without gs://)."),
    prefix: str | None = typer.Option(None, "--prefix", "-p", help="Object name prefix filter."),
) -> None:
    """List objects inside a Cloud Storage bucket."""
    from ...adapters.outbound.google import build_storage_client

    client = build_storage_client(_adc(), _project())
    table = Table(title=f"gs://{bucket}", header_style="bold")
    table.add_column("Name", style="cyan")
    table.add_column("Size", style="white", justify="right")
    table.add_column("Updated", style="dim")
    count = 0
    for blob in client.list_blobs(bucket, prefix=prefix):
        count += 1
        table.add_row(blob.name, str(blob.size or ""), str(blob.updated or ""))
    Console().print(table)
    typer.echo(f"{count} object(s)")


__all__ = ["app"]
