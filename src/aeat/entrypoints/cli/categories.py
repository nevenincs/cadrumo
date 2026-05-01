"""CLI commands for AEAT spending-category catalogues."""

from __future__ import annotations

import json

import typer

from ...domain.casillas import ModeloCode
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


@app.command(name="show", help="Show one category profile with citations and casilla mappings.")
def show_category(category: SpendingCategory = typer.Argument(..., help="Stable category identifier.")) -> None:
    """Print one category profile as JSON."""

    profile = CATEGORY_PROFILES_2025[category]
    payload = {
        "category": category.value,
        "family": family_for(category).value,
        "profile": profile.model_dump(mode="json"),
    }
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


@app.command(name="casillas", help="List which categories map to which casillas for a modelo.")
def list_casillas(
    modelo: str = typer.Argument(..., help="AEAT modelo identifier, e.g. MODELO_130 or 130."),
) -> None:
    """Print category-to-casilla mappings for one modelo."""

    try:
        modelo_code = ModeloCode[modelo.upper()]
    except KeyError:
        try:
            modelo_code = ModeloCode(modelo)
        except ValueError:
            valid = ", ".join(code.name for code in ModeloCode)
            raise typer.BadParameter(f"{modelo!r} is not a known modelo. Use one of: {valid}") from None

    payload: list[dict[str, object]] = []
    for category in SpendingCategory:
        profile = CATEGORY_PROFILES_2025[category]
        mappings = [
            {**mapping.model_dump(mode="json"), "modelo": mapping.modelo.name}
            for mapping in profile.casilla_mappings
            if mapping.modelo is modelo_code
        ]
        if not mappings:
            continue
        payload.append({"category": category.value, "mappings": mappings})
    typer.echo(json.dumps(payload, indent=2, ensure_ascii=False))


__all__ = ["app"]
