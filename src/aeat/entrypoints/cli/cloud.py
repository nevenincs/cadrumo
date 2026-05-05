"""``aeat cloud`` sub-app — GCP product helpers (Functions / Run / Storage).

Each sub-sub-app builds the dedicated ``google-cloud-*`` client lazily
so ``aeat --help`` does not pay the import cost. Operations exposed here
are read-only (``list`` / ``describe`` / ``ls``); deploy is intentionally
out of scope.
"""

from __future__ import annotations

from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ._i18n import tr

app = typer.Typer(name="cloud", no_args_is_help=True, help=tr("cli.cloud.app_help"))
functions_app = typer.Typer(name="functions", no_args_is_help=True, help=tr("cli.cloud.functions_app_help"))
run_app = typer.Typer(name="run", no_args_is_help=True, help=tr("cli.cloud.run_app_help"))
storage_app = typer.Typer(name="storage", no_args_is_help=True, help=tr("cli.cloud.storage_app_help"))

app.add_typer(functions_app, name="functions")
app.add_typer(run_app, name="run")
app.add_typer(storage_app, name="storage")


def _project() -> str:
    """Return the configured GCP project ID, or fail loudly."""
    from ...core.config import Settings

    project = Settings().google_cloud_project
    if not project:
        typer.secho(
            tr("cli.cloud.errors.missing_project"),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    return project


def _adc() -> Any:
    """Return ADC credentials with the cloud-platform scope."""
    from ...adapters.outbound.google import CLOUD_PLATFORM_SCOPE, get_credentials_for_scopes

    return get_credentials_for_scopes([CLOUD_PLATFORM_SCOPE])


# ── Cloud Functions ─────────────────────────────────────────────────────────


@functions_app.command(name="list", help=tr("cli.cloud.functions_list_help"))
def functions_list() -> None:
    """List every Cloud Function in the project (-).

    The ``-`` location wildcard returns functions from every region in
    a single call.
    """
    from ...adapters.outbound.google import build_cloudfunctions_client

    client = build_cloudfunctions_client(_adc())
    parent = f"projects/{_project()}/locations/-"
    table = Table(title=tr("cli.cloud.functions_list_title"), header_style="bold")
    table.add_column(tr("cli.cloud.name_col"), style="cyan")
    table.add_column(tr("cli.cloud.state_col"), style="white")
    table.add_column(tr("cli.cloud.environment_col"), style="dim")
    table.add_column(tr("cli.cloud.update_time_col"), style="dim")
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
    typer.echo(tr("cli.cloud.labels.functions_found", count=count))


@functions_app.command(name="describe", help=tr("cli.cloud.functions_describe_help"))
def functions_describe(
    name: str = typer.Argument(..., help=tr("cli.cloud.functions_describe_name_help")),
) -> None:
    """Print the full metadata for one function."""
    from ...adapters.outbound.google import build_cloudfunctions_client

    client = build_cloudfunctions_client(_adc())
    function = client.get_function(name=name)
    typer.echo(str(function))


# ── Cloud Run ───────────────────────────────────────────────────────────────


@run_app.command(name="list", help=tr("cli.cloud.run_list_help"))
def run_list() -> None:
    """List every Cloud Run service in the project (-)."""
    from ...adapters.outbound.google import build_cloudrun_client

    client = build_cloudrun_client(_adc())
    parent = f"projects/{_project()}/locations/-"
    table = Table(title=tr("cli.cloud.run_list_title"), header_style="bold")
    table.add_column(tr("cli.cloud.name_col"), style="cyan")
    table.add_column(tr("cli.cloud.generation_col"), style="white")
    table.add_column(tr("cli.cloud.update_time_col"), style="dim")
    count = 0
    for service in client.list_services(parent=parent):
        count += 1
        table.add_row(
            getattr(service, "name", ""),
            str(getattr(service, "generation", "")),
            str(getattr(service, "update_time", "")),
        )
    Console().print(table)
    typer.echo(tr("cli.cloud.labels.services_found", count=count))


@run_app.command(name="describe", help=tr("cli.cloud.run_describe_help"))
def run_describe(
    name: str = typer.Argument(..., help=tr("cli.cloud.run_describe_name_help")),
) -> None:
    """Print full metadata for one Cloud Run service."""
    from ...adapters.outbound.google import build_cloudrun_client

    client = build_cloudrun_client(_adc())
    service = client.get_service(name=name)
    typer.echo(str(service))


# ── Cloud Storage ───────────────────────────────────────────────────────────


@storage_app.command(name="buckets", help=tr("cli.cloud.storage_buckets_help"))
def storage_buckets() -> None:
    """List Cloud Storage buckets visible in the project."""
    from ...adapters.outbound.google import build_storage_client

    client = build_storage_client(_adc(), _project())
    table = Table(title=tr("cli.cloud.storage_buckets_title"), header_style="bold")
    table.add_column(tr("cli.cloud.name_col"), style="cyan")
    table.add_column(tr("cli.cloud.location_col"), style="white")
    table.add_column(tr("cli.cloud.storage_class_col"), style="dim")
    count = 0
    for bucket in client.list_buckets():
        count += 1
        table.add_row(bucket.name, bucket.location or "", bucket.storage_class or "")
    Console().print(table)
    typer.echo(tr("cli.cloud.labels.buckets_found", count=count))


@storage_app.command(name="ls", help=tr("cli.cloud.storage_ls_help"))
def storage_ls(
    bucket: str = typer.Argument(..., help=tr("cli.cloud.storage_ls_bucket_help")),
    prefix: str | None = typer.Option(None, "--prefix", "-p", help=tr("cli.cloud.storage_ls_prefix_help")),
) -> None:
    """List objects inside a bucket."""
    from ...adapters.outbound.google import build_storage_client

    client = build_storage_client(_adc(), _project())
    table = Table(title=f"gs://{bucket}", header_style="bold")
    table.add_column(tr("cli.cloud.name_col"), style="cyan")
    table.add_column(tr("cli.cloud.size_col"), style="white", justify="right")
    table.add_column(tr("cli.cloud.updated_col"), style="dim")
    count = 0
    for blob in client.list_blobs(bucket, prefix=prefix):
        count += 1
        table.add_row(blob.name, str(blob.size or ""), str(blob.updated or ""))
    Console().print(table)
    typer.echo(tr("cli.cloud.labels.objects_found", count=count))


__all__ = ["app"]
