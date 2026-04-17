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
    escape_drive_query_literal,
    guess_mime_type,
)

app = typer.Typer(name="drive", no_args_is_help=True, help="Google Drive helpers.")


def _drive() -> Any:
    """Build an authenticated Drive v3 service.

    Imports happen lazily so ``aeat --help`` does not pay the cost of
    loading google-auth + googleapiclient when the user only wants to
    see the command tree.
    """
    from ..auth import DRIVE_SCOPE, build_drive_service, get_credentials_for_scopes

    creds = get_credentials_for_scopes([DRIVE_SCOPE])
    return build_drive_service(creds)


@app.command(name="ls", help="List files inside an optional folder.")
def ls(
    folder: str | None = typer.Option(None, "--folder", "-f", help="Drive folder ID to list inside."),
    page_size: int = typer.Option(50, "--page-size", "-n", help="Maximum entries to fetch."),
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
    table = Table(title=f"drive ls (folder={folder or 'root visible'})", header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("MIME", style="dim")
    table.add_column("Size", style="white", justify="right")
    table.add_column("Modified", style="dim")
    for entry in files:
        table.add_row(
            str(entry.get("id", "")),
            str(entry.get("name", "")),
            str(entry.get("mimeType", "")),
            str(entry.get("size", "")),
            str(entry.get("modifiedTime", "")),
        )
    Console().print(table)


@app.command(name="find", help="Run a raw Drive query string (Drive `q=` syntax).")
def find(query: str = typer.Argument(..., help="Drive query string, e.g. \"name contains 'foo'\".")) -> None:
    """Pass a query through to ``files.list``."""
    service = _drive()
    response = service.files().list(q=query, fields="files(id, name, mimeType)", pageSize=100).execute()
    files = response.get("files", [])
    table = Table(title=f"drive find: {query}", header_style="bold")
    table.add_column("ID", style="cyan")
    table.add_column("Name", style="white")
    table.add_column("MIME", style="dim")
    for entry in files:
        table.add_row(str(entry.get("id", "")), str(entry.get("name", "")), str(entry.get("mimeType", "")))
    Console().print(table)


@app.command(name="cat", help="Download a Drive file to stdout (or export Workspace docs).")
def cat(
    file_id: str = typer.Argument(..., help="Drive file ID."),
    export_mime: str | None = typer.Option(
        None,
        "--export-mime",
        "-m",
        help="Export MIME for Workspace files (e.g. text/plain, application/pdf).",
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


@app.command(name="put", help="Upload a local file to Drive.")
def put(
    local: Path = typer.Argument(..., help="Path to the local file."),
    folder: str | None = typer.Option(None, "--folder", "-f", help="Destination folder ID."),
    name: str | None = typer.Option(None, "--name", "-n", help="Override the uploaded file name."),
    mime: str | None = typer.Option(None, "--mime", "-m", help="MIME type override."),
) -> None:
    """Resumably upload a local file to Drive."""
    from googleapiclient.http import MediaFileUpload

    if not local.exists():
        typer.secho(f"local file does not exist: {local}", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    service = _drive()
    metadata: dict[str, Any] = {"name": name or local.name}
    if folder:
        metadata["parents"] = [folder]
    media = MediaFileUpload(str(local), mimetype=mime or guess_mime_type(local), resumable=True)
    response = service.files().create(body=metadata, media_body=media, fields="id, name").execute()
    typer.echo(f"{response.get('id', '')}\t{response.get('name', '')}")


@app.command(name="mkdir", help="Create a Drive folder.")
def mkdir(
    name: str = typer.Argument(..., help="New folder name."),
    parent: str | None = typer.Option(None, "--parent", "-p", help="Parent folder ID."),
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


@app.command(name="rm", help="Trash a Drive file (or permanently delete with --permanent).")
def rm(
    file_id: str = typer.Argument(..., help="Drive file ID."),
    permanent: bool = typer.Option(False, "--permanent", "-P", help="Permanently delete instead of trashing."),
) -> None:
    """Move a Drive file to trash, or delete it permanently."""
    service = _drive()
    if permanent:
        service.files().delete(fileId=file_id).execute()
        typer.secho(f"deleted {file_id}", fg=typer.colors.RED)
    else:
        service.files().update(fileId=file_id, body={"trashed": True}).execute()
        typer.secho(f"trashed {file_id}", fg=typer.colors.YELLOW)


# Keep the helper exports importable from the sub-app namespace.
__all__ = [
    "app",
    "build_listing_query",
    "escape_drive_query_literal",
    "guess_mime_type",
]
