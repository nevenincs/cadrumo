"""CLI presentation handlers for the registered capital-goods operations."""

from __future__ import annotations

import typer

from .common import emit_envelope
from .runtime_ledger_bienes_inversion import declare_bien_inversion as submit_bien_inversion_declaration
from .runtime_ledger_bienes_inversion import read_bienes_inversion_register


def bienes_inversion_declare(
    ctx: typer.Context,
    identifier: str,
    description: str,
    acquisition_year: int,
    acquisition_ledger_id: str,
    cuota_soportada: str,
    prorrata_inicial_pct: str,
    kind: str,
    art108_elegible: bool = True,
    prorrata_sector_id: str | None = None,
    disposal_year: int | None = None,
    disposal_regime: str | None = None,
) -> None:
    """Submit one profile-bound declaration and present its canonical result."""
    _, payload = submit_bien_inversion_declaration(
        ctx,
        identifier=identifier,
        description=description,
        acquisition_year=acquisition_year,
        acquisition_ledger_id=acquisition_ledger_id,
        cuota_soportada=cuota_soportada,
        prorrata_inicial_pct=prorrata_inicial_pct,
        kind=kind,
        art108_elegible=art108_elegible,
        prorrata_sector_id=prorrata_sector_id,
        disposal_year=disposal_year,
        disposal_regime=disposal_regime,
    )
    record = payload.record
    emit_envelope(
        ctx,
        command="ledger.bienes_inversion.declare",
        result=payload,
        lines=(
            f"bucket\t{payload.bucket_id}",
            f"identifier\t{record.identifier}",
            f"acquisition_year\t{record.acquisition_year}",
            f"kind\t{record.kind}",
            f"cuota_soportada\t{record.cuota_soportada}",
            f"prorrata_inicial_pct\t{record.prorrata_inicial_pct}",
            f"deduccion_efectuada\t{record.deduccion_efectuada}",
            f"count\t{payload.count}",
        ),
    )


def bienes_inversion_list(ctx: typer.Context) -> None:
    """Read the complete profile register and present its canonical projection."""
    _, payload = read_bienes_inversion_register(ctx)
    lines = [f"bucket\t{payload.bucket_id}", f"count\t{payload.count}"]
    for record in payload.rows:
        lines.append(
            f"{record.identifier}\t{record.acquisition_year}\t{record.kind}\t"
            f"cuota={record.cuota_soportada}\tprorrata={record.prorrata_inicial_pct}",
        )
    emit_envelope(
        ctx,
        command="ledger.bienes_inversion.list",
        result=payload,
        lines=lines,
    )
