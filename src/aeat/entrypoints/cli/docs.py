"""``aeat docs`` sub-app — Google Docs v1 helpers via the discovery client.

Each command builds an authenticated Docs service lazily so importing
this module does not pay the discovery round-trip cost. Body
manipulation requests delegate to
:mod:`aeat.entrypoints.cli._docs_helpers` so the request shape is unit
testable without touching the Google API.
"""

from __future__ import annotations

import json
from typing import Any

import typer

from ._docs_helpers import (
    build_append_request,
    build_replace_all_request,
    extract_plaintext,
    find_end_index,
)
from ._i18n import tr

app = typer.Typer(name="docs", no_args_is_help=True, help=tr("cli.docs.app_help"))


def _docs() -> Any:
    """Build an authenticated Docs v1 service lazily."""
    from ...adapters.outbound.google import DOCS_SCOPE, build_docs_service, get_credentials_for_scopes

    creds = get_credentials_for_scopes([DOCS_SCOPE])
    return build_docs_service(creds)


@app.command(name="get", help=tr("cli.docs.get_help"))
def get(
    doc_id: str = typer.Argument(..., help=tr("cli.docs.get_doc_id_help")),
    plaintext: bool = typer.Option(False, "--plaintext", "-p", help=tr("cli.docs.get_plaintext_help")),
) -> None:
    """Fetch a document by ID."""
    service = _docs()
    document = service.documents().get(documentId=doc_id).execute()
    if plaintext:
        typer.echo(extract_plaintext(document))
    else:
        typer.echo(json.dumps(document, indent=2))


@app.command(name="new", help=tr("cli.docs.new_help"))
def new(title: str = typer.Argument(..., help=tr("cli.docs.new_title_help"))) -> None:
    """Create an empty document."""
    service = _docs()
    response = service.documents().create(body={"title": title}).execute()
    typer.echo(response["documentId"])


@app.command(name="append", help=tr("cli.docs.append_help"))
def append(
    doc_id: str = typer.Argument(..., help=tr("cli.docs.append_doc_id_help")),
    text: str = typer.Argument(..., help=tr("cli.docs.append_text_help")),
) -> None:
    """Append text to the end of a document."""
    if not text:
        typer.secho(
            tr("cli.docs.errors.empty_text"),
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    service = _docs()
    document = service.documents().get(documentId=doc_id).execute()
    end_index = find_end_index(document)
    service.documents().batchUpdate(
        documentId=doc_id,
        body={"requests": build_append_request(text, end_index)},
    ).execute()
    typer.echo(tr("cli.docs.success.appended"))


@app.command(name="replace", help=tr("cli.docs.replace_help"))
def replace(
    doc_id: str = typer.Argument(..., help=tr("cli.docs.replace_doc_id_help")),
    old: str = typer.Argument(..., help=tr("cli.docs.replace_old_help")),
    new_text: str = typer.Argument(..., help=tr("cli.docs.replace_new_text_help")),
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
    sum(reply.get("replaceAllText", {}).get("occurrencesChanged", 0) for reply in replies)
    typer.echo(tr("cli.docs.success.replaced"))


__all__ = [
    "app",
    "build_append_request",
    "build_replace_all_request",
    "extract_plaintext",
    "find_end_index",
]
