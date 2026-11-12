"""CLI presentation handlers for the suffered-withholding certificate operations."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.operations.public_scalar import PublicDecimal
from ...application.retencion_soportada_certificado.requests import (
    RetencionSoportadaListRequest,
    RetencionSoportadaRecordRequest,
    RetencionSoportadaRemoveRequest,
)
from ...core.i18n.render import tr
from ...core.retencion_soportada import RetencionSoportadaClase
from ...domain.renta.retencion_soportada import RetencionSoportadaOrigen
from .common import active_bucket_id_or_refuse, bad, emit_envelope
from .decimal_parsing import parse_decimal_amount
from .operation_ledger_retencion_soportada import (
    list_retencion_soportada,
    record_retencion_soportada,
    remove_retencion_soportada,
)
from .retencion_soportada_results import RetencionSoportadaRowPayload


def _profile_id() -> UUID:
    return UUID(active_bucket_id_or_refuse())


def _amount(raw: str, *, label: str) -> PublicDecimal:
    return PublicDecimal(decimal=str(parse_decimal_amount(raw, label=label, signed=False)))


def _stated(figure: str | None) -> str:
    return "" if figure is None else figure


def _row_line(row: RetencionSoportadaRowPayload) -> str:
    return (
        f"{row.income_class}\t{row.payer_ref}\t{row.payer_name or ''}\t{row.origin}\t"
        f"retencion={row.retencion}\tingreso_a_cuenta={row.ingreso_a_cuenta}\t"
        f"repercutido={row.ingreso_a_cuenta_repercutido}\tpago_a_cuenta={row.pago_a_cuenta}\t"
        f"reducciones={_stated(row.reducciones_aplicables)}\tgastos={_stated(row.gastos_deducibles)}\t"
        f"revision={row.revision_id}"
    )


def retencion_soportada_record(
    ctx: typer.Context,
    payer_tax_id: str,
    ejercicio: int,
    income_class: RetencionSoportadaClase,
    origin: RetencionSoportadaOrigen,
    retencion: str = "0",
    ingreso_a_cuenta: str = "0",
    ingreso_a_cuenta_repercutido: str = "0",
    importe_integro_dinerario: str = "0",
    valoracion_especie: str = "0",
    reducciones_aplicables: str | None = None,
    gastos_deducibles: str | None = None,
    payer_name: str | None = None,
    certificate_file: Path | None = None,
    evidence_sha256: str | None = None,
    expected_revision: str | None = None,
) -> None:
    """Record or replace the figures one payer's certificate states and present the stored row."""
    amounts = {
        "importe_integro_dinerario": _amount(importe_integro_dinerario, label="--importe-integro"),
        "valoracion_especie": _amount(valoracion_especie, label="--valoracion-especie"),
        "retencion": _amount(retencion, label="--retencion"),
        "ingreso_a_cuenta": _amount(ingreso_a_cuenta, label="--ingreso-a-cuenta"),
        "ingreso_a_cuenta_repercutido": _amount(ingreso_a_cuenta_repercutido, label="--ingreso-a-cuenta-repercutido"),
    }
    try:
        request = RetencionSoportadaRecordRequest(
            profile_id=_profile_id(),
            ejercicio=ejercicio,
            income_class=income_class,
            payer_tax_id=payer_tax_id,
            payer_legal_name=payer_name,
            origin=origin,
            evidence_fingerprint=evidence_sha256,
            source_path=None if certificate_file is None else str(certificate_file),
            source_directory=None if certificate_file is None else str(Path.cwd()),
            expected_revision_id=expected_revision,
            reducciones_aplicables=(
                None
                if reducciones_aplicables is None
                else _amount(reducciones_aplicables, label="--reducciones-aplicables")
            ),
            gastos_deducibles=(
                None if gastos_deducibles is None else _amount(gastos_deducibles, label="--gastos-deducibles")
            ),
            **amounts,
        )
    except ValidationError:
        raise bad(tr("cli.app.ledger.retencion_soportada.invalid_input")) from None
    result = record_retencion_soportada(ctx, request)
    emit_envelope(
        ctx,
        command="ledger.retencion_soportada.record",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", _row_line(result.row), f"count\t{result.count}"),
    )


def retencion_soportada_list(ctx: typer.Context, ejercicio: int) -> None:
    """Read the stored payer records of one ejercicio and present them without tax identifiers."""
    try:
        request = RetencionSoportadaListRequest(profile_id=_profile_id(), ejercicio=ejercicio)
    except ValidationError:
        raise bad(tr("cli.app.ledger.retencion_soportada.invalid_input")) from None
    result = list_retencion_soportada(ctx, request)
    emit_envelope(
        ctx,
        command="ledger.retencion_soportada.list",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", f"count\t{result.count}", *(_row_line(row) for row in result.rows)),
    )


def retencion_soportada_remove(
    ctx: typer.Context,
    payer_ref: str,
    ejercicio: int,
    income_class: RetencionSoportadaClase,
    expected_revision: str,
) -> None:
    """Remove one payer record against the revision a list showed."""
    try:
        request = RetencionSoportadaRemoveRequest(
            profile_id=_profile_id(),
            ejercicio=ejercicio,
            income_class=income_class,
            payer_ref=payer_ref,
            expected_revision_id=expected_revision,
        )
    except ValidationError:
        raise bad(tr("cli.app.ledger.retencion_soportada.invalid_input")) from None
    result = remove_retencion_soportada(ctx, request)
    emit_envelope(
        ctx,
        command="ledger.retencion_soportada.remove",
        result=result,
        lines=(
            f"bucket\t{result.bucket_id}",
            f"removed\t{result.income_class}\t{result.payer_ref}",
            f"count\t{result.count}",
        ),
    )
