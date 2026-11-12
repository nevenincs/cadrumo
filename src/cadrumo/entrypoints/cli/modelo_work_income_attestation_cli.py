"""Behavior for the command that states the work-income boxes no payer certificate fills hold nothing.

A return resting on a work-income payer record needs the employer's contributions
and the protected-estate contribution (boxes 0008, 0009, 0010 and 0024) from the
filer, because no certificate states them. The declaration's form serves one
statement that there are none; this command stages exactly the boxes that
statement names, shows the served words and the check of the staged change, and
applies it through the guarded edit only when the filer confirms with ``--yes``.
It is its own door: these boxes are income, not an amount carried from an earlier
ejercicio.
"""

from __future__ import annotations

from uuid import UUID

import typer

from cadrumo_client.commands.output import activate_subcommand_output_language
from cadrumo_client.commands.profile_binding import require_profile_client

from ...application.modelo.absence_statement_submission import absence_statement_submission
from ...application.modelo.action_errors import ModeloEditRefusedError, modelo_edit_refusal_error
from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1
from ...application.modelo.edit_models import ModeloEditRefusedV1, ModeloEditSubmissionV1
from ...application.modelo.work_form_models import ModeloFormCarryAttestation
from ...application.modelo.workbench_operations import ModeloEditPreflightProjectionV1
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from .common import emit_envelope
from .modelo_cli_support import resolve_explicit_or_active_bucket_id
from .modelo_work_income_attestation_payloads import WorkAttestWorkIncomeResult, WorkIncomeStatementPayload
from .operation_modelo_carry_attestation import (
    apply_modelo_edit_for_cli,
    preflight_modelo_edit_for_cli,
    read_modelo_work_form_for_cli,
)

_COMMAND = "modelo.work.attest_work_income"
_FAMILY = AbsenceAttestationFamily.RENTA_TRABAJO_INCOME_NOT_STATED


def _statement(attestation: ModeloFormCarryAttestation) -> WorkIncomeStatementPayload:
    return WorkIncomeStatementPayload(
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


def _lines(result: WorkAttestWorkIncomeResult, work_unit_id: str) -> list[str]:
    lines = [f"operation\t{_COMMAND}", f"work_unit_id\t{work_unit_id}", f"applied\t{str(result.applied).lower()}"]
    for statement in result.statements:
        lines.append(f"statement\t{statement.statement_words}")
        lines.extend(f"box\t{binding_id}\t{statement.effect_words}" for binding_id in statement.binding_ids)
    lines.extend(f"finding\t{words}" for words in result.findings)
    if result.applied:
        lines.extend((f"receipt_id\t{result.receipt_id}", f"calculation_revision_id\t{result.calculation_revision_id}"))
    else:
        lines.append(tr("cli.app.modelo.work.attest_work_income_confirm", work_unit_id=work_unit_id))
    return lines


def _result(
    submission: ModeloEditSubmissionV1,
    attestations: tuple[ModeloFormCarryAttestation, ...],
    findings: list[str],
    applied: ModeloEditApplyPublicResultV1 | None,
) -> WorkAttestWorkIncomeResult:
    baseline = submission.baseline
    return WorkAttestWorkIncomeResult(
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


def work_attest_work_income(
    ctx: typer.Context,
    work_unit_id: str,
    confirmed: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """State that the work-income boxes no payer certificate fills hold nothing, for the boxes the form names."""
    activate_subcommand_output_language(ctx, output_language)
    client = require_profile_client(ctx, expected_profile_id=UUID(resolve_explicit_or_active_bucket_id(None)))
    language = OutputLanguage(active_output_language())
    form = read_modelo_work_form_for_cli(client, work_unit_id=work_unit_id.strip(), language=language)
    if form.admission_refusal is not None:
        raise modelo_edit_refusal_error(form.admission_refusal.refusal)
    if form.admitted_baseline is None:
        raise ModeloEditRefusedError()
    attestations = tuple(
        attestation for attestation in form.form.form.carry_attestations if attestation.family is _FAMILY
    )
    submission = absence_statement_submission(form.admitted_baseline.to_baseline(), attestations, family=_FAMILY)
    review = preflight_modelo_edit_for_cli(client, submission, language=language)
    findings = _checked(review)
    applied: ModeloEditApplyPublicResultV1 | None = None
    if confirmed:
        if any(finding.blocking for finding in review.findings):
            raise ModeloEditRefusedError()
        applied = apply_modelo_edit_for_cli(client, submission, language=language).projection
    result = _result(submission, attestations, findings, applied)
    emit_envelope(ctx, command=_COMMAND, result=result, lines=_lines(result, submission.baseline.work_unit_id))


__all__ = ["work_attest_work_income"]
