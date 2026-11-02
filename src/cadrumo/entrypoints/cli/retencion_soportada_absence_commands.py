"""CLI presentation handlers for the suffered-withholding absence attestations."""

from __future__ import annotations

from uuid import UUID

import typer
from pydantic import ValidationError

from ...application.retencion_soportada_absence.requests import (
    RetencionSoportadaAbsenceAttestRequest,
    RetencionSoportadaAbsenceWithdrawRequest,
)
from ...core.i18n.render import tr
from ...core.retencion_soportada import RetencionSoportadaClase
from .common import active_bucket_id_or_refuse, bad, emit_envelope
from .operation_ledger_retencion_soportada_absence import (
    attest_retencion_soportada_absence,
    withdraw_retencion_soportada_absence,
)
from .retencion_soportada_absence_results import RetencionSoportadaAbsencePayload

__all__ = ["retencion_soportada_attest_absence", "retencion_soportada_withdraw_absence"]


def _line(attestation: RetencionSoportadaAbsencePayload) -> str:
    return (
        f"{attestation.ejercicio}\t{attestation.income_class}\t{attestation.state}\t"
        f"attested_at={attestation.attested_at}\trevision={attestation.revision_id}"
    )


def retencion_soportada_attest_absence(
    ctx: typer.Context,
    ejercicio: int,
    income_class: RetencionSoportadaClase,
    note: str,
    expected_revision: str | None = None,
) -> None:
    """Attest that no payer withheld on one income class in one ejercicio, and present the stored attestation."""
    try:
        request = RetencionSoportadaAbsenceAttestRequest(
            profile_id=UUID(active_bucket_id_or_refuse()),
            ejercicio=ejercicio,
            income_class=income_class,
            note=note.strip(),
            expected_revision_id=expected_revision,
        )
    except ValidationError:
        raise bad(tr("cli.app.ledger.retencion_soportada.absence_invalid_input")) from None
    result = attest_retencion_soportada_absence(ctx, request)
    emit_envelope(
        ctx,
        command="ledger.retencion_soportada.attest_absence",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", _line(result.attestation)),
    )


def retencion_soportada_withdraw_absence(
    ctx: typer.Context,
    ejercicio: int,
    income_class: RetencionSoportadaClase,
    expected_revision: str,
) -> None:
    """Withdraw the active absence attestation of one income class, guarded by its revision."""
    try:
        request = RetencionSoportadaAbsenceWithdrawRequest(
            profile_id=UUID(active_bucket_id_or_refuse()),
            ejercicio=ejercicio,
            income_class=income_class,
            expected_revision_id=expected_revision,
        )
    except ValidationError:
        raise bad(tr("cli.app.ledger.retencion_soportada.absence_invalid_input")) from None
    result = withdraw_retencion_soportada_absence(ctx, request)
    emit_envelope(
        ctx,
        command="ledger.retencion_soportada.withdraw_absence",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", _line(result.attestation)),
    )
