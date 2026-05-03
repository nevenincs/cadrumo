"""Registry-gated ``aeat data ledgers anexo-d`` command surface."""

from __future__ import annotations

import typer
from pydantic import BaseModel, ConfigDict

from ..._i18n import t, tr
from ..._schemas import OutputRootSchema, register_schema

app = typer.Typer(name="anexo-d", no_args_is_help=True, help="Preview Modelo 100 Anexo D ledger-derived inputs.")

_STRICT = ConfigDict(strict=True, frozen=True, extra="forbid")
_REGISTRY_REQUIRED = t(
    "Anexo D requiere un snapshot de registro validado",
    "Anexo D requires a validated registry snapshot",
    "l'Annex D requereix un snapshot de registre validat",
    "az Anexo D validalt registry snapshotot igenyel",
)


class AnexoDPreviewPayload(BaseModel):
    """Disabled Anexo D preview JSON payload shape retained for schema discovery."""

    model_config = _STRICT

    modelo: str
    year: int
    actividad_id: str
    casillas: dict[str, str]
    source: str


class AnexoDPreviewJson(OutputRootSchema[AnexoDPreviewPayload]):
    """JSON contract for disabled Anexo D preview output."""


register_schema("data ledgers anexo-d preview")(AnexoDPreviewJson)


@app.command(name="preview", help="Preview ledger-derived Modelo 100 Anexo D casillas.")
def preview(
    year: int = typer.Option(..., "--year", help="Tax year."),
    actividad: str = typer.Option(..., "--actividad", help="Economic activity id."),
    modelo: str = typer.Option("100", "--modelo", help="Modelo number. Only 100 is supported."),
) -> None:
    """Reject legacy Anexo D ledger calculation."""
    _ = (year, actividad, modelo)
    raise typer.BadParameter(tr(_REGISTRY_REQUIRED))


__all__ = ["app"]
