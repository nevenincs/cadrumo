"""``aeat profile`` Typer subcommands for Kent's tax-residence profile.

Provides commands to read, set and clear the local tax-residence profile
that downstream RENTA importers use to resolve autonomic-region casillas.
The persistence layer lives in :mod:`aeat.adapters.persistence.profile`
and the domain types in :mod:`aeat.domain.profile`.

Three subcommands are wired here:

- ``aeat profile show`` — render the configured CCAA, JSON path and
  affected RENTA boxes.
- ``aeat profile set tax-region <ccaa>`` — persist the ordinary CCAA.
- ``aeat profile clear`` — remove the local profile.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

import typer
from pydantic import Field
from rich.console import Console
from rich.table import Table

from ....domain.profile import (
    CCAA,
    KentTaxResidence,
    parse_tax_region,
)
from ....adapters.persistence.profile import (
    clear_tax_residence,
    default_path,
    load_tax_residence,
    save_tax_residence,
)
from .._errors import json_output_requested
from .._schemas import OutputSchema, emit_json_success, register_schema
from .._i18n import t, tr


PROFILE_HELP = tr(
    t(
        "Gestiona la residencia fiscal CCAA usada para verificar RENTA automaticamente.",
        "Manage the tax-residence CCAA used to verify RENTA automatically.",
        "Gestiona la residència fiscal CCAA emprada per verificar la RENTA automàticament.",
        "A RENTA automatikus ellenorzesehez hasznalt adoilletosegi CCAA kezelese.",
    )
)
SET_HELP = tr(
    t(
        "Configura campos locales del perfil de residencia fiscal.",
        "Set local tax-residence profile fields.",
        "Configura camps locals del perfil de residència fiscal.",
        "Helyi adoilletosegi profilmezok beallitasa.",
    )
)
SHOW_HELP = tr(
    t(
        "Muestra la CCAA configurada, la ruta JSON local y las casillas RENTA afectadas.",
        "Show the configured CCAA, local JSON path, and affected RENTA boxes.",
        "Mostra la CCAA configurada, la ruta JSON local i les caselles RENTA afectades.",
        "Megjeleniti a beallitott CCAA-t, a helyi JSON utvonalat es az erintett RENTA mezoket.",
    )
)
SET_TAX_REGION_HELP = tr(
    t(
        "Guarda la CCAA ordinaria de residencia fiscal para RENTA. "
        "Ejemplo: aeat profile set tax-region madrid --since 2025-01-01.",
        "Save the ordinary tax-residence CCAA for RENTA. "
        "Example: aeat profile set tax-region madrid --since 2025-01-01.",
        "Desa la CCAA ordinària de residència fiscal per a la RENTA. "
        "Exemple: aeat profile set tax-region madrid --since 2025-01-01.",
        "Elmenti a rendes adoilletosegi CCAA-t a RENTA-hoz. "
        "Pelda: aeat profile set tax-region madrid --since 2025-01-01.",
    )
)
CLEAR_HELP = tr(
    t(
        "Borra el perfil local de residencia fiscal; las importaciones RENTA volveran a pedir configuracion.",
        "Clear the local tax-residence profile; RENTA imports will require setup again.",
        "Esborra el perfil local de residència fiscal; les importacions RENTA tornaran a demanar configuració.",
        "Torli a helyi adoilletosegi profilt; a RENTA import ujra beallitast ker.",
    )
)
_CCAA_IDS = ", ".join(ccaa.value for ccaa in CCAA)
CCAA_ARGUMENT_HELP = tr(
    t(
        "Identificador CCAA ordinario. Valores: "
        f"{_CCAA_IDS}. Pais Vasco y Navarra son regimenes forales fuera de #452.",
        f"Ordinary CCAA id. Values: {_CCAA_IDS}. Pais Vasco and Navarra are foral regimes outside #452.",
        f"Identificador CCAA ordinari. Valors: {_CCAA_IDS}. País Basc i Navarra són règims forals fora de #452.",
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
    """Machine-readable payload for ``aeat profile show --json``.

    Attributes:
        configured: ``True`` when a tax residence is persisted on disk.
        schema_version: Pydantic schema version of the persisted record.
        ccaa: Stable identifier (lower-case kebab-case) of the configured CCAA.
        ccaa_label: Human-readable Spanish label for the configured CCAA.
        tax_residence_since: ISO date marking the start of the current
            residence, or ``None`` when not pinned.
        profile_path: Filesystem path of the JSON record on disk.
        downstream_references: Pre-localised references to the RENTA
            casillas affected by this profile.
    """

    configured: bool
    schema_version: str | None = None
    ccaa: str | None = None
    ccaa_label: str | None = None
    tax_residence_since: str | None = None
    profile_path: str
    downstream_references: list[str] = Field(default_factory=list)


def _references() -> tuple[str, ...]:
    """Return the localised RENTA casilla references shown after ``show``."""
    return (
        tr(
            t(
                "Modelo 100 casilla 0551: tarifa autonómica general",
                "Modelo 100 box 0551: general autonomic tax scale",
                "Modelo 100 casella 0551: tarifa autonòmica general",
                "Modelo 100 0551 mező: altalanos autonom adoskala",
            )
        ),
        tr(
            t(
                "Modelo 100 casilla 0622: deducciones autonómicas Anexo Ñ",
                "Modelo 100 box 0622: autonomic deductions from Anexo Ñ",
                "Modelo 100 casella 0622: deduccions autonòmiques de l'Annex Ñ",
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
            help=tr(
                t(
                    "Emite el perfil con el esquema JSON registrado.",
                    "Emit the profile using the registered JSON schema.",
                    "Emet el perfil amb l'esquema JSON registrat.",
                    "A profil kiirasa a regisztralt JSON semaval.",
                )
            ),
        ),
    ] = False,
) -> None:
    """Display the configured tax-residence profile.

    Args:
        json_output: Emit the registered :class:`ProfileShowJson` payload
            instead of the rich table when truthy.
    """

    residence = load_tax_residence()
    payload = _show_payload(residence)
    if json_output or json_output_requested():
        emit_json_success("profile show", payload)
        return
    if residence is None:
        typer.echo(
            tr(
                t(
                    "No hay residencia fiscal configurada.",
                    "No tax residence configured.",
                    "No hi ha residència fiscal configurada.",
                    "Nincs adoilletoseg beallitva.",
                )
            )
        )
        typer.echo("aeat profile set tax-region <ccaa>")
        return

    table = Table(
        title=tr(
            t(
                "Perfil de residencia fiscal",
                "Tax-residence profile",
                "Perfil de residència fiscal",
                "Adoilletosegi profil",
            )
        )
    )
    table.add_column(tr(t("Campo", "Field", "Camp", "Mezo")))
    table.add_column(tr(t("Valor", "Value", "Valor", "Ertek")))
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
            help=tr(
                t(
                    "Fecha inicial opcional de esta residencia fiscal en formato YYYY-MM-DD; "
                    "dejala vacia si es siempre vigente.",
                    "Optional first date of this tax residence as YYYY-MM-DD; "
                    "omit it when the profile is simply current.",
                    "Data inicial opcional d'aquesta residència fiscal en format YYYY-MM-DD; "
                    "deixa-la buida si sempre és vigent.",
                    "Az adoilletoseg opcionalis kezdodatuma YYYY-MM-DD formatumban; hagyd el, ha csak aktualis profil.",
                )
            ),
        ),
    ] = None,
) -> None:
    """Persist Kent's ordinary CCAA tax residence.

    Args:
        ccaa: One of the ordinary CCAA identifiers in :class:`CCAA`.
            Foral regimes (Pais Vasco, Navarra) are rejected by
            :func:`aeat.domain.profile.parse_tax_region`.
        since: Optional ISO date (``YYYY-MM-DD``) marking when the
            residence began; left unset when the profile is simply current.
    """

    parsed = parse_tax_region(ccaa)
    parsed_since = date.fromisoformat(since) if since is not None else None
    residence = KentTaxResidence(ccaa=parsed, tax_residence_since=parsed_since)
    save_tax_residence(residence)
    typer.echo(
        tr(
            t(
                f"Residencia fiscal guardada: {_CCAA_LABELS[parsed]} ({parsed.value}).",
                f"Tax residence saved: {_CCAA_LABELS[parsed]} ({parsed.value}).",
                f"Residència fiscal desada: {_CCAA_LABELS[parsed]} ({parsed.value}).",
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
            help=tr(
                t(
                    "No pedir confirmacion.",
                    "Do not ask for confirmation.",
                    "No demanis confirmació.",
                    "Ne kerjen megerositest.",
                )
            ),
        ),
    ] = False,
) -> None:
    """Remove Kent's tax-residence profile.

    Args:
        yes: Skip the interactive confirmation prompt when truthy.
    """

    if not yes and not typer.confirm(
        tr(
            t(
                "¿Borrar la residencia fiscal?",
                "Clear tax residence?",
                "Voleu esborrar la residència fiscal?",
                "Toroljem az adoilletoseget?",
            )
        )
    ):
        raise typer.Abort()
    clear_tax_residence()
    typer.echo(
        tr(
            t(
                "Residencia fiscal borrada.",
                "Tax residence cleared.",
                "Residència fiscal esborrada.",
                "Adoilletoseg torolve.",
            )
        )
    )


def _show_payload(residence: KentTaxResidence | None) -> ProfileShowJson:
    """Build the :class:`ProfileShowJson` payload for ``residence``."""
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
