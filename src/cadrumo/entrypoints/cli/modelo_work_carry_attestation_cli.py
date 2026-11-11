"""Behavior for the command that states no carry from an earlier ejercicio is pending on a declaration.

A Modelo 100 reads the negative general bases still pending from the four
previous ejercicios from the earlier return. With no earlier return stored they
are unknown, and only the filer's statement records them as nothing pending.
The declaration's form serves that statement and the carries it answers; this
command stages exactly those carries, shows the served words and the check of
the staged change, and applies it through the guarded edit only when the filer
confirms with ``--yes``.
"""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.output import activate_subcommand_output_language
from cadrumo_client.commands.profile_binding import require_profile_client

from ...application.modelo.action_errors import ModeloEditRefusedError, modelo_edit_refusal_error
from ...application.modelo.carry_attestation_submission import prior_carry_attestation_submission
from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1
from ...application.modelo.edit_models import ModeloEditRefusedV1, ModeloEditSubmissionV1
from ...application.modelo.work_form_models import ModeloFormCarryAttestation
from ...application.modelo.workbench_operations import ModeloEditPreflightProjectionV1
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from .common import emit_envelope
from .modelo_cli_support import resolve_explicit_or_active_bucket_id
from .modelo_work_carry_attestation_payloads import PriorCarryStatementPayload, WorkAttestPriorCarriesResult
from .operation_modelo_carry_attestation import (
    apply_modelo_edit_for_cli,
    preflight_modelo_edit_for_cli,
    read_modelo_work_form_for_cli,
)

_COMMAND = "modelo.work.attest_prior_carries"


def _statement(attestation: ModeloFormCarryAttestation) -> PriorCarryStatementPayload:
    return PriorCarryStatementPayload(
        family=attestation.family.value,
        action_words=attestation.action_words,
        statement_words=attestation.statement_words,
        effect_words=attestation.effect_words,
        binding_ids=list(attestation.binding_ids),
    )


def _checked(review: ModeloEditPreflightProjectionV1) -> list[str]:
    """The check's findings in words, refusing the staged change the check refused."""
    if isinstance(review.outcome, ModeloEditRefusedV1):
        raise modelo_edit_refusal_error(review.outcome.refusal)
    return [finding.words for finding in review.findings]


def _lines(result: WorkAttestPriorCarriesResult, work_unit_id: str) -> list[str]:
    lines = [f"operation\t{_COMMAND}", f"work_unit_id\t{work_unit_id}", f"applied\t{str(result.applied).lower()}"]
    for statement in result.statements:
        lines.append(f"statement\t{statement.statement_words}")
        lines.extend(f"carry\t{binding_id}\t{statement.effect_words}" for binding_id in statement.binding_ids)
    lines.extend(f"finding\t{words}" for words in result.findings)
    if result.applied:
        lines.extend((f"receipt_id\t{result.receipt_id}", f"calculation_revision_id\t{result.calculation_revision_id}"))
    else:
        lines.append(tr("cli.app.modelo.work.attest_prior_carries_confirm", work_unit_id=work_unit_id))
    return lines


def _result(
    submission: ModeloEditSubmissionV1,
    attestations: tuple[ModeloFormCarryAttestation, ...],
    findings: list[str],
    applied: ModeloEditApplyPublicResultV1 | None,
) -> WorkAttestPriorCarriesResult:
    baseline = submission.baseline
    return WorkAttestPriorCarriesResult(
        bucket_id=baseline.bucket_id,
        work_unit_id=baseline.work_unit_id,
        modelo=str(baseline.modelo),
        filing_year=baseline.filing_year,
        applied=applied is not None,
        statements=[_statement(attestation) for attestation in attestations],
        findings=findings,
        receipt_id=None if applied is None else applied.receipt_id,
        calculation_revision_id=None if applied is None else applied.calculation_revision_id,
    )


def work_attest_prior_carries(
    ctx: typer.Context,
    work_unit_id: str,
    confirmed: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """State that no carry from an earlier ejercicio is pending, for every carry the declaration's form names."""
    activate_subcommand_output_language(ctx, output_language)
    client = require_profile_client(ctx, expected_profile_id=UUID(resolve_explicit_or_active_bucket_id(None)))
    language = OutputLanguage(active_output_language())
    form = read_modelo_work_form_for_cli(client, work_unit_id=work_unit_id.strip(), language=language)
    if form.admission_refusal is not None:
        raise modelo_edit_refusal_error(form.admission_refusal.refusal)
    if form.admitted_baseline is None:
        raise ModeloEditRefusedError()
    attestations = form.form.form.carry_attestations
    submission = prior_carry_attestation_submission(form.admitted_baseline.to_baseline(), attestations)
    review = preflight_modelo_edit_for_cli(client, submission, language=language)
    findings = _checked(review)
    applied: ModeloEditApplyPublicResultV1 | None = None
    if confirmed:
        if any(finding.blocking for finding in review.findings):
            raise ModeloEditRefusedError()
        applied = apply_modelo_edit_for_cli(client, submission, language=language).projection
    result = _result(submission, attestations, findings, applied)
    emit_envelope(ctx, command=_COMMAND, result=result, lines=_lines(result, submission.baseline.work_unit_id))


__all__ = ["work_attest_prior_carries"]
