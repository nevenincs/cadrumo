"""``aeat categories`` sub-app — AEAT spending-category catalogues.

Wraps :mod:`aeat.domain.categories` so the operator can list the
profile's spending categories and dump the full closed-set taxonomy as
JSON for external pipelines. Read-only by construction; the underlying
catalogue lives in pure :mod:`aeat.domain` records.
"""

from __future__ import annotations

import json

import typer

from ...domain.categories import SpendingCategory, family_for, resolve_category_profiles
from ._i18n import tr

app = typer.Typer(
    name="categories",
    no_args_is_help=True,
    help=tr("cli.categories.app_help"),
)


@app.command(name="list", help=tr("cli.categories.list_help"))
def list_categories(year: int = typer.Option(..., "--year", help=tr("cli.categories.year_help"))) -> None:
    """Print the available spending categories as JSON."""

    profiles = resolve_category_profiles(year)
    payload = [
        {
            "category": category.value,
            "family": family_for(category).value,
            "proportionality_kind": profiles[category].proportionality.kind.value,
        }
        for category in SpendingCategory
    ]
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@app.command(name="show", help=tr("cli.categories.show_help"))
def show_category(
    category: SpendingCategory = typer.Argument(..., help=tr("cli.categories.id_help")),
    year: int = typer.Option(..., "--year", help=tr("cli.categories.year_help")),
) -> None:
    """Print one category profile as JSON."""

    profile = resolve_category_profiles(year)[category]
    payload = {
        "category": category.value,
        "family": family_for(category).value,
        "profile": profile.model_dump(mode="json"),
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


__all__ = ["app"]
