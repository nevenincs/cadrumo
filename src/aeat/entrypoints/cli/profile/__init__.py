"""``aeat profile`` commands for Kent's tax-residence profile."""

from __future__ import annotations

from datetime import date
from typing import Annotated

import typer
from pydantic import Field
from rich.console import Console
from rich.table import Table

from ....core.i18n import Language, Translatable, get_translation
from ....domain.profile import (
    CCAA,
    KentTaxResidence,
    clear_tax_residence,
    default_path,
    load_tax_residence,
    parse_tax_region,
    save_tax_residence,
)
from .._errors import json_output_requested
from .._schemas import OutputSchema, emit_json_success, register_schema


def _t(es: str, en: str, hu: str) -> Translatable:
    return {"es": es, "en": en, "hu": hu}


def _lang() -> Language:
    from ....core.config import load_settings

    try:
        return Language(load_settings().aeat_output_language)
    except (KeyError, ValueError):
        return Language.ES


def _msg(message: Translatable) -> str:
    return get_translation(message, _lang())


PROFILE_HELP = _msg(
    _t(
        "Gestiona la residencia fiscal CCAA usada para verificar RENTA automaticamente.",
        "Manage the tax-residence CCAA used to verify RENTA automatically.",
        "A RENTA automatikus ellenorzesehez hasznalt adoilletosegi CCAA kezelese.",
    )
)
SET_HELP = _msg(
    _t(
        "Configura campos locales del perfil de residencia fiscal.",
        "Set local tax-residence profile fields.",
        "Helyi adoilletosegi profilmezok beallitasa.",
    )
)
SHOW_HELP = _msg(
    _t(
        "Muestra la CCAA configurada, la ruta JSON local y las casillas RENTA afectadas.",
        "Show the configured CCAA, local JSON path, and affected RENTA boxes.",
        "Megjeleniti a beallitott CCAA-t, a helyi JSON utvonalat es az erintett RENTA mezoket.",
    )
)
SET_TAX_REGION_HELP = _msg(
    _t(
        "Guarda la CCAA ordinaria de residencia fiscal para RENTA. "
        "Ejemplo: aeat profile set tax-region madrid --since 2025-01-01.",
        "Save the ordinary tax-residence CCAA for RENTA. "
        "Example: aeat profile set tax-region madrid --since 2025-01-01.",
        "Elmenti a rendes adoilletosegi CCAA-t a RENTA-hoz. "
        "Pelda: aeat profile set tax-region madrid --since 2025-01-01.",
    )
)
CLEAR_HELP = _msg(
    _t(
        "Borra el perfil local de residencia fiscal; las importaciones RENTA volveran a pedir configuracion.",
        "Clear the local tax-residence profile; RENTA imports will require setup again.",
        "Torli a helyi adoilletosegi profilt; a RENTA import ujra beallitast ker.",
    )
)
_CCAA_IDS = ", ".join(ccaa.value for ccaa in CCAA)
CCAA_ARGUMENT_HELP = _msg(
    _t(
        "Identificador CCAA ordinario. Valores: "
        f"{_CCAA_IDS}. Pais Vasco y Navarra son regimenes forales fuera de #452.",
        f"Ordinary CCAA id. Values: {_CCAA_IDS}. Pais Vasco and Navarra are foral regimes outside #452.",
        f"Rendes CCAA azonosito. Ertekek: {_CCAA_IDS}. Pais Vasco es Navarra foralis rendszer, #452 hatokoren kivul.",
    )
)

app = typer.Typer(
    name="profile",
    no_args_is_help=True,
    help=PROFILE_HELP,
)
set_app = typer.Typer(
    name="set",
    no_args_is_help=True,
    help=SET_HELP,
)
app.add_typer(set_app, name="set")

_console = Console()

_CCAA_LABELS: dict[CCAA, str] = {
    CCAA.ANDALUCIA: "Andalucía",
    CCAA.ARAGON: "Aragón",
    CCAA.ASTURIAS: "Asturias",
    CCAA.BALEARES: "Illes Balears",
    CCAA.CANARIAS: "Canarias",
    CCAA.CANTABRIA: "Cantabria",
    CCAA.CASTILLA_LA_MANCHA: "Castilla-La Mancha",
    CCAA.CASTILLA_Y_LEON: "Castilla y León",
    CCAA.CATALUNA: "Cataluña",
    CCAA.COMUNIDAD_VALENCIANA: "Comunitat Valenciana",
    CCAA.EXTREMADURA: "Extremadura",
    CCAA.GALICIA: "Galicia",
    CCAA.LA_RIOJA: "La Rioja",
    CCAA.MADRID: "Madrid",
    CCAA.MURCIA: "Región de Murcia",
}


@register_schema("profile show")
class ProfileShowJson(OutputSchema):
    """Machine-readable payload for ``aeat profile show --json``."""

    configured: bool
    schema_version: str | None = None
    ccaa: str | None = None
    ccaa_label: str | None = None
    tax_residence_since: str | None = None
    profile_path: str
    downstream_references: list[str] = Field(default_factory=list)


def _references() -> tuple[str, ...]:
    return (
        _msg(
            _t(
                "Modelo 100 casilla 0551: tarifa autonómica general",
                "Modelo 100 box 0551: general autonomic tax scale",
                "Modelo 100 0551 mező: altalanos autonom adoskala",
            )
        ),
        _msg(
            _t(
                "Modelo 100 casilla 0622: deducciones autonómicas Anexo Ñ",
                "Modelo 100 box 0622: autonomic deductions from Anexo Ñ",
                "Modelo 100 0622 mező: autonom kedvezmenyek az Anexo N-bol",
            )
        ),
    )


@app.command("show", help=SHOW_HELP)
def show(
    json_output: Annotated[
        bool,
        typer.Option(
            "--json",
            help=_msg(
                _t(
                    "Emite el perfil con el esquema JSON registrado.",
                    "Emit the profile using the registered JSON schema.",
                    "A profil kiirasa a regisztralt JSON semaval.",
                )
            ),
        ),
    ] = False,
) -> None:
    """Display the configured tax-residence profile."""

    residence = load_tax_residence()
    payload = _show_payload(residence)
    if json_output or json_output_requested():
        emit_json_success("profile show", payload)
        return
    if residence is None:
        typer.echo(
            _msg(
                _t(
                    "No hay residencia fiscal configurada.",
                    "No tax residence configured.",
                    "Nincs adoilletoseg beallitva.",
                )
            )
        )
        typer.echo("aeat profile set tax-region <ccaa>")
        return

    table = Table(title=_msg(_t("Perfil de residencia fiscal", "Tax-residence profile", "Adoilletosegi profil")))
    table.add_column(_msg(_t("Campo", "Field", "Mezo")))
    table.add_column(_msg(_t("Valor", "Value", "Ertek")))
    table.add_row("ccaa", f"{payload.ccaa_label} ({payload.ccaa})")
    table.add_row("tax_residence_since", payload.tax_residence_since or "-")
    table.add_row("schema_version", payload.schema_version or "-")
    table.add_row("profile_path", payload.profile_path)
    _console.print(table)
    for reference in payload.downstream_references:
        typer.echo(reference)


@set_app.command("tax-region", help=SET_TAX_REGION_HELP)
def set_tax_region(
    ccaa: Annotated[
        str,
        typer.Argument(
            help=CCAA_ARGUMENT_HELP,
            metavar="CCAA",
        ),
    ],
    since: Annotated[
        str | None,
        typer.Option(
            "--since",
            help=_msg(
                _t(
                    "Fecha inicial opcional de esta residencia fiscal en formato YYYY-MM-DD; "
                    "dejala vacia si es siempre vigente.",
                    "Optional first date of this tax residence as YYYY-MM-DD; "
                    "omit it when the profile is simply current.",
                    "Az adoilletoseg opcionalis kezdodatuma YYYY-MM-DD formatumban; hagyd el, ha csak aktualis profil.",
                )
            ),
        ),
    ] = None,
) -> None:
    """Persist Kent's ordinary CCAA tax residence."""

    parsed = parse_tax_region(ccaa)
    parsed_since = date.fromisoformat(since) if since is not None else None
    residence = KentTaxResidence(ccaa=parsed, tax_residence_since=parsed_since)
    save_tax_residence(residence)
    typer.echo(
        _msg(
            _t(
                f"Residencia fiscal guardada: {_CCAA_LABELS[parsed]} ({parsed.value}).",
                f"Tax residence saved: {_CCAA_LABELS[parsed]} ({parsed.value}).",
                f"Adoilletoseg mentve: {_CCAA_LABELS[parsed]} ({parsed.value}).",
            )
        )
    )


@app.command("clear", help=CLEAR_HELP)
def clear(
    yes: Annotated[
        bool,
        typer.Option(
            "--yes",
            help=_msg(
                _t(
                    "No pedir confirmacion.",
                    "Do not ask for confirmation.",
                    "Ne kerjen megerositest.",
                )
            ),
        ),
    ] = False,
) -> None:
    """Remove Kent's tax-residence profile."""

    if not yes and not typer.confirm(
        _msg(_t("¿Borrar la residencia fiscal?", "Clear tax residence?", "Toroljem az adoilletoseget?"))
    ):
        raise typer.Abort()
    clear_tax_residence()
    typer.echo(_msg(_t("Residencia fiscal borrada.", "Tax residence cleared.", "Adoilletoseg torolve.")))


def _show_payload(residence: KentTaxResidence | None) -> ProfileShowJson:
    if residence is None:
        return ProfileShowJson(configured=False, profile_path=str(default_path()))
    return ProfileShowJson(
        configured=True,
        schema_version=residence.schema_version,
        ccaa=residence.ccaa.value,
        ccaa_label=_CCAA_LABELS[residence.ccaa],
        tax_residence_since=residence.tax_residence_since.isoformat() if residence.tax_residence_since else None,
        profile_path=str(default_path()),
        downstream_references=list(_references()),
    )


__all__ = ["PROFILE_HELP", "app"]
