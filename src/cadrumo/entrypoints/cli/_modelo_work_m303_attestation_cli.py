"""CLI transport for secure ordinary Modelo 390 non-applicability attestation."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

import typer

from ...application.modelo.m303_attestation_operation import (
    ModeloWorkM303AttestationPublicResultV2,
    ModeloWorkM303AttestationRequest,
)
from ...application.operations.public_period import PublicPeriod
from ...core.external_constants import OutputLanguage
from ._modelo_behavior_support import resolve_year_period
from ._modelo_cli_support import resolve_explicit_or_active_bucket_id
from ._modelo_payloads import M303Exonerado390AttestationResult
from .common import activate_subcommand_output_language, emit_envelope
from .runtime_modelo_attestation import run_modelo_m303_attestation
from .runtime_profile_binding import require_profile_client


def work_attest_m303_exonerado_390(
    ctx: typer.Context,
    year: int,
    period: str,
    observed_at: str,
    bucket_id: str | None = None,
    actor: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Admit the fixed ordinary-M303 ``not_applicable`` assertion into custody."""
    activate_subcommand_output_language(ctx, output_language)
    resolved_bucket = resolve_explicit_or_active_bucket_id(bucket_id)
    client = require_profile_client(ctx, expected_profile_id=UUID(resolved_bucket))
    resolved_period = resolve_year_period(year, period, modelo="303")
    request = ModeloWorkM303AttestationRequest(
        profile_id=client.profile_id,
        period=PublicPeriod.from_period(resolved_period),
        observed_at=_observed_at_from_cli(observed_at),
        actor=actor or str(client.profile_id),
    )
    completed = run_modelo_m303_attestation(client, request)
    admission = completed.projection
    result = M303Exonerado390AttestationResult(
        filing_year=resolved_period.filing_year,
        period=resolved_period,
        attachment_id=admission.attachment_id,
        sha256=admission.sha256,
    )
    emit_envelope(
        ctx,
        command="modelo.work.attest-m303-exonerado-390",
        result=result,
        lines=(
            "operation\tmodelo.work.attest-m303-exonerado-390",
            f"filing_year\t{resolved_period.filing_year}",
            f"period\t{resolved_period.registry_token}",
            f"attachment_id\t{admission.attachment_id}",
            f"sha256\t{admission.sha256}",
        ),
    )


def _observed_at_from_cli(value: str) -> datetime:
    """Parse the explicit ISO-8601 instant before strict evidence validation."""
    try:
        return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError as exc:
        raise typer.BadParameter("--observed-at must be an ISO-8601 timestamp") from exc


__all__ = ["work_attest_m303_exonerado_390"]
