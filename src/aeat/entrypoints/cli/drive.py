"""``aeat drive`` sub-app — Drive v3 helpers via the discovery client.

Every command builds the Drive service lazily so importing this module
does not pay the discovery round-trip cost. Output goes through rich
where it benefits from a table or colour, and through stdout for raw
file content (so ``aeat drive cat ID > file`` works).
"""

from __future__ import annotations

import io
import sys
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from ._drive_helpers import (
    build_listing_query,
    build_name_query,
    escape_drive_query_literal,
    guess_mime_type,
)
from ._i18n import tr

app = typer.Typer(name="drive", no_args_is_help=True, help=tr("cli.drive.app_help"))


def _drive() -> Any:
    """Build an authenticated Drive v3 service.

    Imports happen lazily so ``aeat --help`` does not pay the cost of
    loading google-auth + googleapiclient when the user only wants to
    see the command tree.
    """
    from ...adapters.outbound.google import DRIVE_SCOPE, build_drive_service, get_credentials_for_scopes

    creds = get_credentials_for_scopes([DRIVE_SCOPE])
    return build_drive_service(creds)


@app.command(name="ls", help=tr("cli.drive.ls_help"))
def ls(
    folder: str | None = typer.Option(None, "--folder", "-f", help=tr("cli.drive.ls_folder_help")),
    page_size: int = typer.Option(50, "--page-size", "-n", help=tr("cli.drive.ls_page_size_help")),
) -> None:
    """List Drive files (default scope: everything visible to the caller)."""
    service = _drive()
    response = (
        service.files()
        .list(
            q=build_listing_query(folder),
            fields="files(id, name, mimeType, size, modifiedTime)",
            pageSize=page_size,
        )
        .execute()
    )
    files = response.get("files", [])
    table = Table(title=tr("cli.drive.ls_table_title", folder=folder or "root visible"), header_style="bold")
    table.add_column(tr("cli.drive.table_id"), style="cyan")
    table.add_column(tr("cli.drive.table_name"), style="white")
    table.add_column(tr("cli.drive.table_mime"), style="dim")
    table.add_column(tr("cli.drive.table_size"), style="white", justify="right")
    table.add_column(tr("cli.drive.table_modified"), style="dim")
    for entry in files:
        table.add_row(
            str(entry.get("id", "")),
            str(entry.get("name", "")),
            str(entry.get("mimeType", "")),
            str(entry.get("size", "")),
            str(entry.get("modifiedTime", "")),
        )
    Console().print(table)


@app.command(name="find", help=tr("cli.drive.find_help"))
def find(query: str = typer.Argument(..., help=tr("cli.drive.find_query_help"))) -> None:
    """Pass a query through to ``files.list``."""
    service = _drive()
    response = service.files().list(q=query, fields="files(id, name, mimeType)", pageSize=100).execute()
    files = response.get("files", [])
    table = Table(title=tr("cli.drive.find_table_title", query=query), header_style="bold")
    table.add_column(tr("cli.drive.table_id"), style="cyan")
    table.add_column(tr("cli.drive.table_name"), style="white")
    table.add_column(tr("cli.drive.table_mime"), style="dim")
    for entry in files:
        table.add_row(str(entry.get("id", "")), str(entry.get("name", "")), str(entry.get("mimeType", "")))
    Console().print(table)


@app.command(name="cat", help=tr("cli.drive.cat_help"))
def cat(
    file_id: str = typer.Argument(..., help=tr("cli.drive.cat_file_id_help")),
    export_mime: str | None = typer.Option(
        None,
        "--export-mime",
        "-m",
        help=tr("cli.drive.cat_export_mime_help"),
    ),
) -> None:
    """Stream a Drive file to stdout, exporting Workspace docs if requested."""
    from googleapiclient.http import MediaIoBaseDownload

    service = _drive()
    if export_mime:
        request = service.files().export_media(fileId=file_id, mimeType=export_mime)
    else:
        request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    sys.stdout.buffer.write(buffer.getvalue())


@app.command(
    name="fetch",
    help=tr("cli.drive.fetch_help"),
)
def fetch(
    name: str = typer.Argument(..., help=tr("cli.drive.fetch_name_help")),
    out: Path = typer.Option(
        Path("credentials"),
        "--out",
        "-o",
        help=tr("cli.drive.fetch_out_help"),
    ),
    overwrite: bool = typer.Option(
        False,
        "--overwrite",
        help=tr("cli.drive.fetch_overwrite_help"),
    ),
) -> None:
    """Locate a single file by exact name and download it.

    Convenience wrapper around ``aeat drive find`` + ``aeat drive cat``
    that fails fast on zero or multiple matches and writes to a local
    path instead of stdout. Used by ``just aeat-cert-fetch`` to fetch
    a PKCS#12 cert from Drive without copy-pasting file IDs.
    """
    from googleapiclient.http import MediaIoBaseDownload

    console = Console()
    service = _drive()
    response = service.files().list(q=build_name_query(name), fields="files(id, name, mimeType)", pageSize=10).execute()
    files = response.get("files", [])
    if not files:
        console.print("[red]drive fetch:[/red] " + tr("cli.drive.errors.not_found", name=name))
        raise typer.Exit(code=1)
    if len(files) > 1:
        console.print("[red]drive fetch:[/red] " + tr("cli.drive.errors.multiple_matches", name=name))
        raise typer.Exit(code=1)
    file_entry = files[0]
    file_id = str(file_entry["id"])

    target = out / name if out.exists() and out.is_dir() else out
    if target.exists() and not overwrite:
        console.print("[red]drive fetch:[/red] " + tr("cli.drive.errors.already_exists", path=target))
        raise typer.Exit(code=1)
    target.parent.mkdir(parents=True, exist_ok=True)

    request = service.files().get_media(fileId=file_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request)
    done = False
    while not done:
        _status, done = downloader.next_chunk()
    target.write_bytes(buffer.getvalue())
    console.print("[green]drive fetch:[/green] " + tr("cli.drive.success.fetched", name=name, path=target))


@app.command(name="put", help=tr("cli.drive.put_help"))
def put(
    local: Path = typer.Argument(..., help=tr("cli.drive.put_local_help")),
    folder: str | None = typer.Option(None, "--folder", "-f", help=tr("cli.drive.put_folder_help")),
    name: str | None = typer.Option(None, "--name", "-n", help=tr("cli.drive.put_name_help")),
    mime: str | None = typer.Option(None, "--mime", "-m", help=tr("cli.drive.put_mime_help")),
) -> None:
    """Resumably upload a local file to Drive."""
    from googleapiclient.http import MediaFileUpload

    if not local.exists():
        typer.secho(
            tr("cli.drive.errors.local_not_found", path=local),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    service = _drive()
    metadata: dict[str, Any] = {"name": name or local.name}
    if folder:
        metadata["parents"] = [folder]
    media = MediaFileUpload(str(local), mimetype=mime or guess_mime_type(local), resumable=True)
    response = service.files().create(body=metadata, media_body=media, fields="id, name").execute()
    typer.echo(f"{response.get('id', '')}\t{response.get('name', '')}")


@app.command(name="mkdir", help=tr("cli.drive.mkdir_help"))
def mkdir(
    name: str = typer.Argument(..., help=tr("cli.drive.mkdir_name_help")),
    parent: str | None = typer.Option(None, "--parent", "-p", help=tr("cli.drive.mkdir_parent_help")),
) -> None:
    """Create a Drive folder under an optional parent."""
    service = _drive()
    metadata: dict[str, Any] = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent:
        metadata["parents"] = [parent]
    response = service.files().create(body=metadata, fields="id, name").execute()
    typer.echo(f"{response.get('id', '')}\t{response.get('name', '')}")


@app.command(name="rm", help=tr("cli.drive.rm_help"))
def rm(
    file_id: str = typer.Argument(..., help=tr("cli.drive.rm_file_id_help")),
    permanent: bool = typer.Option(False, "--permanent", "-P", help=tr("cli.drive.rm_permanent_help")),
) -> None:
    """Move a Drive file to trash, or delete it permanently."""
    service = _drive()
    if permanent:
        service.files().delete(fileId=file_id).execute()
        typer.secho(
            tr("cli.drive.success.deleted", id=file_id),
            fg=typer.colors.RED,
        )
    else:
        service.files().update(fileId=file_id, body={"trashed": True}).execute()
        typer.secho(
            tr("cli.drive.success.trashed", id=file_id),
            fg=typer.colors.YELLOW,
        )


# Keep the helper exports importable from the sub-app namespace.
__all__ = [
    "app",
    "build_listing_query",
    "escape_drive_query_literal",
    "guess_mime_type",
]
