"""``aeat categories`` sub-app — AEAT spending-category catalogues.

Wraps :mod:`aeat.domain.categories` so the operator can list the
profile's spending categories and dump the full closed-set taxonomy as
JSON for external pipelines. Read-only by construction; the underlying
catalogue lives in pure :mod:`aeat.domain` records.
"""

from __future__ import annotations

import json

import typer

from ...domain.categories import CATEGORY_PROFILES_2025, SpendingCategory, family_for

app = typer.Typer(
    name="categories",
    no_args_is_help=True,
    help="AEAT spending-category taxonomy and proportionality helpers.",
)


@app.command(name="list", help="List all spending categories and proportionality kinds.")
def list_categories() -> None:
    """Print the available spending categories as JSON."""

    payload = [
        {
            "category": category.value,
            "family": family_for(category).value,
            "proportionality_kind": CATEGORY_PROFILES_2025[category].proportionality.kind.value,
        }
        for category in SpendingCategory
    ]
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@app.command(name="show", help="Show one category profile with citations.")
def show_category(category: SpendingCategory = typer.Argument(..., help="Stable category identifier.")) -> None:
    """Print one category profile as JSON."""

    profile = CATEGORY_PROFILES_2025[category]
    payload = {
        "category": category.value,
        "family": family_for(category).value,
        "profile": profile.model_dump(mode="json"),
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


__all__ = ["app"]
