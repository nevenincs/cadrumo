"""CLI transport for secure ordinary Modelo 390 non-applicability attestation."""

from __future__ import annotations

from datetime import datetime

import typer

from ...application.modelo.m303_exonerado_390_applicability_attestation import (
    M303Exonerado390ApplicabilityAttestationRequest,
    admit_m303_exonerado_390_applicability_attestation,
)
from ...application.modelo.profile_readiness_gate import load_modelo_work_profile
from ...core.external_constants import OutputLanguage
from ...domain.attachments.m303_filing_evidence import M303Exonerado390ApplicabilityAssertion
from ._modelo_behavior_support import require_active_profile, resolve_year_period
from ._modelo_cli_support import resolve_default_actor, resolve_explicit_or_active_bucket_id
from ._modelo_payloads import M303Exonerado390AttestationResult
from .common import activate_subcommand_output_language, emit_envelope
from .state_projection_support import attachment_store, authority_operation


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
    require_active_profile()
    resolved_bucket = resolve_explicit_or_active_bucket_id(bucket_id)
    resolved_period = resolve_year_period(year, period, modelo="303")
    operation = authority_operation(ctx)
    profile = load_modelo_work_profile(
        bucket_id=resolved_bucket,
        profile_decode_context=operation.profile_decode_context(),
    )
    admission = admit_m303_exonerado_390_applicability_attestation(
        bucket_id=resolved_bucket,
        request=M303Exonerado390ApplicabilityAttestationRequest(
            filing_year=resolved_period.filing_year,
            period=resolved_period,
            asserted_value=M303Exonerado390ApplicabilityAssertion.NOT_APPLICABLE,
            observed_at=_observed_at_from_cli(observed_at),
        ),
        actor=actor or resolve_default_actor(),
        operation=operation,
        store=attachment_store(ctx, bucket_id=resolved_bucket),
        profile=profile,
    )
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
