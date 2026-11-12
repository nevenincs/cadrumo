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

from collections.abc import Mapping
from decimal import Decimal
from uuid import UUID

import typer

from cadrumo_client.commands.output import activate_subcommand_output_language
from cadrumo_client.commands.profile_binding import require_profile_client
from cadrumo_client.transport.frontend_client import FrontendClient

from ...application.modelo.action_errors import ModeloEditRefusedError, modelo_edit_refusal_error
from ...application.modelo.carry_amount_statement import prior_carry_statement_submission, resolve_prior_carry_amounts
from ...application.modelo.carry_family_selection import select_prior_carry_attestations
from ...application.modelo.edit_apply_contracts import ModeloEditApplyPublicResultV1
from ...application.modelo.edit_models import ModeloEditRefusedV1, ModeloEditSubmissionV1
from ...application.modelo.work_form_models import ModeloFormCarryAttestation
from ...application.modelo.workbench_operations import ModeloEditPreflightProjectionV1
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from ...domain.calculations.registry.binding_absence_attestation import AbsenceAttestationFamily
from ...domain.calculations.registry.ids import BindingId
from .common import emit_envelope
from .modelo_cli_support import resolve_explicit_or_active_bucket_id
from .modelo_work_carry_attestation_payloads import (
    PriorCarryPayload,
    PriorCarryStatementPayload,
    WorkAttestPriorCarriesResult,
)
from .operation_modelo_carry_attestation import (
    apply_modelo_edit_for_cli,
    preflight_modelo_edit_for_cli,
    read_modelo_work_form_for_cli,
)

_COMMAND = "modelo.work.attest_prior_carries"


def _statement(
    attestation: ModeloFormCarryAttestation, amounts: Mapping[BindingId, Decimal]
) -> PriorCarryStatementPayload:
    return PriorCarryStatementPayload(
        carries=[
            PriorCarryPayload(
                binding_id=binding_id,
                amount=None if binding_id not in amounts else str(amounts[binding_id]),
                effect_words=attestation.effect_words
                if binding_id not in amounts
                else tr("cli.app.modelo.work.attest_prior_carries_amount_effect", amount=amounts[binding_id]),
            )
            for binding_id in attestation.binding_ids
        ],
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


def attest_prior_carries_lines(result: WorkAttestPriorCarriesResult, work_unit_id: str, selection: str) -> list[str]:
    """The text lines of the receipt: each family and carry with its effect, then the findings and the next step."""
    lines = [f"operation\t{_COMMAND}", f"work_unit_id\t{work_unit_id}", f"applied\t{str(result.applied).lower()}"]
    for statement in result.statements:
        lines.append(f"family\t{statement.family}")
        lines.append(f"statement\t{statement.statement_words}")
        lines.extend(
            f"carry\t{statement.family}\t{carry.binding_id}\t{carry.effect_words}" for carry in statement.carries
        )
    lines.extend(f"finding\t{words}" for words in result.findings)
    if result.applied:
        lines.extend((f"receipt_id\t{result.receipt_id}", f"calculation_revision_id\t{result.calculation_revision_id}"))
    else:
        lines.append(
            tr("cli.app.modelo.work.attest_prior_carries_confirm", work_unit_id=work_unit_id, selection=selection)
        )
    return lines


def attest_prior_carries_result(
    submission: ModeloEditSubmissionV1,
    attestations: tuple[ModeloFormCarryAttestation, ...],
    findings: list[str],
    amounts: Mapping[BindingId, Decimal],
    applied: ModeloEditApplyPublicResultV1 | None,
) -> WorkAttestPriorCarriesResult:
    """The receipt of the statement: each family and carry with its effect, applied or only shown."""
    baseline = submission.baseline
    return WorkAttestPriorCarriesResult(
        bucket_id=baseline.bucket_id,
        work_unit_id=baseline.work_unit_id,
        modelo=str(baseline.modelo),
        filing_year=baseline.filing_year,
        applied=applied is not None,
        statements=[_statement(attestation, amounts) for attestation in attestations],
        findings=findings,
        receipt_id=None if applied is None else applied.receipt_id,
        calculation_revision_id=None if applied is None else applied.calculation_revision_id,
    )


def work_attest_prior_carries(
    ctx: typer.Context,
    work_unit_id: str,
    family: list[AbsenceAttestationFamily] | None = None,
    amount: list[str] | None = None,
    confirmed: bool = False,
    output_language: OutputLanguage | None = None,
) -> None:
    """State the carries from earlier ejercicios open in every family, as nothing pending or with an amount."""
    activate_subcommand_output_language(ctx, output_language)
    client = require_profile_client(ctx, expected_profile_id=UUID(resolve_explicit_or_active_bucket_id(None)))
    language = OutputLanguage(active_output_language())
    form = read_modelo_work_form_for_cli(client, work_unit_id=work_unit_id.strip(), language=language)
    if form.admission_refusal is not None:
        raise modelo_edit_refusal_error(form.admission_refusal.refusal)
    if form.admitted_baseline is None:
        raise ModeloEditRefusedError()
    attestations = form.form.form.carry_attestations
    baseline = form.admitted_baseline.to_baseline()
    attestations = select_prior_carry_attestations(baseline, attestations, families=family or ())
    amounts = resolve_prior_carry_amounts(baseline, form.form.form, attestations, amount or ())
    submission = prior_carry_statement_submission(baseline, attestations, amounts)
    review = preflight_modelo_edit_for_cli(client, submission, language=language)
    applied = _applied(client, submission, review, language=language) if confirmed else None
    result = attest_prior_carries_result(submission, attestations, _checked(review), amounts, applied)
    emit_envelope(
        ctx,
        command=_COMMAND,
        result=result,
        lines=attest_prior_carries_lines(
            result, submission.baseline.work_unit_id, _selection(attestations, amount or ())
        ),
    )


def _applied(
    client: FrontendClient,
    submission: ModeloEditSubmissionV1,
    review: ModeloEditPreflightProjectionV1,
    *,
    language: OutputLanguage,
) -> ModeloEditApplyPublicResultV1:
    """Apply the statement the check passed; a blocking finding refuses it instead."""
    if any(finding.blocking for finding in review.findings):
        raise ModeloEditRefusedError()
    return apply_modelo_edit_for_cli(client, submission, language=language).projection


def _selection(attestations: tuple[ModeloFormCarryAttestation, ...], amounts: list[str] | tuple[str, ...]) -> str:
    """The options that repeat this statement, each family and each amount as given."""
    families = "".join(f" --family {statement.family.value}" for statement in attestations)
    return families + "".join(f" --amount {option.strip()}" for option in amounts)


__all__ = ["attest_prior_carries_lines", "attest_prior_carries_result", "work_attest_prior_carries"]
