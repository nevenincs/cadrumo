"""``aeat sheets`` sub-app — Sheets v4 helpers via the discovery client."""

from __future__ import annotations

import json
from typing import Any

import typer
from rich.console import Console
from rich.table import Table

from aeat.cli._sheets_helpers import coerce_value_input_option, parse_values_json

app = typer.Typer(name="sheets", no_args_is_help=True, help="Google Sheets helpers.")


def _sheets() -> Any:
    """Build an authenticated Sheets v4 service lazily."""
    from aeat.auth import SHEETS_SCOPE, build_sheets_service, get_credentials_for_scopes

    creds = get_credentials_for_scopes([SHEETS_SCOPE])
    return build_sheets_service(creds)


@app.command(name="get", help="Read a Sheets range and print as JSON.")
def get(
    spreadsheet_id: str = typer.Argument(..., help="Spreadsheet ID."),
    range_a1: str = typer.Argument(..., help="A1 range, e.g. Sheet1!A1:B10."),
) -> None:
    """Print the values inside an A1 range."""
    service = _sheets()
    response = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=range_a1).execute()
    typer.echo(json.dumps(response.get("values", []), indent=2))


@app.command(name="set", help="Write values into a range. Provide values as a JSON literal.")
def set_(
    spreadsheet_id: str = typer.Argument(..., help="Spreadsheet ID."),
    range_a1: str = typer.Argument(..., help="A1 range to overwrite."),
    values_json: str = typer.Argument(..., help="JSON values: scalar, list, or list-of-lists."),
    raw: bool = typer.Option(False, "--raw", help="Use RAW input mode (skip Google's parsing)."),
) -> None:
    """Overwrite a range with the supplied values."""
    service = _sheets()
    values = parse_values_json(values_json)
    body = {"values": values}
    response = (
        service.spreadsheets()
        .values()
        .update(
            spreadsheetId=spreadsheet_id,
            range=range_a1,
            valueInputOption=coerce_value_input_option(raw),
            body=body,
        )
        .execute()
    )
    typer.echo(f"updated {response.get('updatedCells', 0)} cells in {response.get('updatedRange', range_a1)}")


@app.command(name="append", help="Append rows after the existing data in a range.")
def append(
    spreadsheet_id: str = typer.Argument(..., help="Spreadsheet ID."),
    range_a1: str = typer.Argument(..., help="A1 range that anchors the append."),
    values_json: str = typer.Argument(..., help="JSON values to append."),
    raw: bool = typer.Option(False, "--raw", help="Use RAW input mode."),
) -> None:
    """Append rows after the last row in the anchor range."""
    service = _sheets()
    values = parse_values_json(values_json)
    body = {"values": values}
    response = (
        service.spreadsheets()
        .values()
        .append(
            spreadsheetId=spreadsheet_id,
            range=range_a1,
            valueInputOption=coerce_value_input_option(raw),
            insertDataOption="INSERT_ROWS",
            body=body,
        )
        .execute()
    )
    updates = response.get("updates", {})
    typer.echo(f"appended {updates.get('updatedCells', 0)} cells; updatedRange={updates.get('updatedRange', '')}")


@app.command(name="new", help="Create a new spreadsheet and print its ID.")
def new(title: str = typer.Argument(..., help="Spreadsheet title.")) -> None:
    """Create an empty spreadsheet."""
    service = _sheets()
    response = service.spreadsheets().create(body={"properties": {"title": title}}, fields="spreadsheetId").execute()
    typer.echo(response["spreadsheetId"])


@app.command(name="tabs", help="List the tab titles inside a spreadsheet.")
def tabs(spreadsheet_id: str = typer.Argument(..., help="Spreadsheet ID.")) -> None:
    """List sheet tabs in a spreadsheet."""
    service = _sheets()
    response = service.spreadsheets().get(spreadsheetId=spreadsheet_id, fields="sheets(properties)").execute()
    table = Table(title=f"sheets tabs ({spreadsheet_id})", header_style="bold")
    table.add_column("Index", style="dim", justify="right")
    table.add_column("Title", style="white")
    table.add_column("Sheet ID", style="cyan")
    for sheet in response.get("sheets", []):
        props = sheet.get("properties", {})
        table.add_row(str(props.get("index", "")), str(props.get("title", "")), str(props.get("sheetId", "")))
    Console().print(table)


__all__ = ["app", "coerce_value_input_option", "parse_values_json"]
