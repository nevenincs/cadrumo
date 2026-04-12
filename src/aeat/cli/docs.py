"""``aeat docs`` sub-app — Docs v1 helpers via the discovery client."""

from __future__ import annotations

import json
from typing import Any

import typer

from aeat.cli._docs_helpers import (
    build_append_request,
    build_replace_all_request,
    extract_plaintext,
    find_end_index,
)

app = typer.Typer(name="docs", no_args_is_help=True, help="Google Docs helpers.")


def _docs() -> Any:
    """Build an authenticated Docs v1 service lazily."""
    from aeat.auth import DOCS_SCOPE, build_docs_service, get_adc_credentials_with_scopes

    creds = get_adc_credentials_with_scopes([DOCS_SCOPE])
    return build_docs_service(creds)


@app.command(name="get", help="Fetch a document. Pass --plaintext for the rendered text only.")
def get(
    doc_id: str = typer.Argument(..., help="Document ID."),
    plaintext: bool = typer.Option(False, "--plaintext", "-p", help="Print rendered plain text only."),
) -> None:
    """Fetch a document by ID."""
    service = _docs()
    document = service.documents().get(documentId=doc_id).execute()
    if plaintext:
        typer.echo(extract_plaintext(document))
    else:
        typer.echo(json.dumps(document, indent=2))


@app.command(name="new", help="Create a new document and print its ID.")
def new(title: str = typer.Argument(..., help="Document title.")) -> None:
    """Create an empty document."""
    service = _docs()
    response = service.documents().create(body={"title": title}).execute()
    typer.echo(response["documentId"])


@app.command(name="append", help="Append text to a document.")
def append(
    doc_id: str = typer.Argument(..., help="Document ID."),
    text: str = typer.Argument(..., help="Text to append."),
) -> None:
    """Append text to the end of a document."""
    if not text:
        typer.secho("text must not be empty", fg=typer.colors.RED)
        raise typer.Exit(code=1)
    service = _docs()
    document = service.documents().get(documentId=doc_id).execute()
    end_index = find_end_index(document)
    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": build_append_request(text, end_index)},
    ).execute()
    typer.echo(f"appended {len(text)} characters at index {end_index}")


@app.command(name="replace", help="Find and replace text inside a document.")
def replace(
    doc_id: str = typer.Argument(..., help="Document ID."),
    old: str = typer.Argument(..., help="Substring to replace."),
    new_text: str = typer.Argument(..., help="Replacement text."),
) -> None:
    """Replace every occurrence of ``old`` with ``new_text``."""
    service = _docs()
    response = (
        service.documents()
        .batchUpdate(
            documentId=doc_id,
            body={"requests": build_replace_all_request(old, new_text)},
        )
        .execute()
    )
    replies = response.get("replies", [])
    occurrences = sum(reply.get("replaceAllText", {}).get("occurrencesChanged", 0) for reply in replies)
    typer.echo(f"replaced {occurrences} occurrence(s)")


__all__ = [
    "app",
    "build_append_request",
    "build_replace_all_request",
    "extract_plaintext",
    "find_end_index",
]
