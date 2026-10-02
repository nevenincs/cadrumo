"""Human CLI for the exact-profile registered Quickfile filing chain."""

from __future__ import annotations

from pathlib import Path
from uuid import UUID

import typer

from ...application.modelo.calculation_request_fields import ModeloCalculationOverride
from ...application.modelo.operation_definitions import ModeloWorkCalculateOrdinaryM303EvidenceRequestV2
from ...application.modelo.quickfile import QuickfileStage, QuickfileStageStatus
from ...application.modelo.quickfile_operation_contracts import (
    QuickfileCalculationInputs,
    QuickfileProjection,
    QuickfileRequest,
    QuickfileStageSnapshot,
)
from ...application.operations.public_period import PublicPeriod
from ...core.errors.error_codes import get_registered_error_code_by_code
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity, ResolvedPreconditionAction
from ...core.payment_election import PaymentElection
from ...core.period import Period, PeriodError
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ._app_quickfile_payloads import QuickfileResultPayload, quickfile_stage_message
from ._modelo_cli_support import parse_work_calculate_wire_specs, unsupported_local_work_period_refusal
from ._modelo_rendering import verification_report_notices
from .common import activate_subcommand_output_language, emit_envelope, resolve_cli_precondition_action
from .runtime_profile_binding import bound_profile_client
from .runtime_quickfile import run_quickfile


def _resolve_period(*, modelo: str, year: int, period: str) -> Period:
    try:
        return Period.from_year_and_code(year, period.strip())
    except PeriodError as exc:
        if refusal := unsupported_local_work_period_refusal(modelo=modelo, token=period):
            raise refusal from exc
        raise typer.BadParameter(str(exc)) from exc


def _optional_profile_id(raw: str | None) -> UUID | None:
    if raw is None:
        return None
    try:
        return UUID(raw)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--bucket-id") from exc


def _quickfile_request(
    *,
    profile_id: UUID,
    modelo: str,
    period: Period,
    output: Path,
    revision: str | None,
    bucket_id: str | None,
    casilla: list[str] | None,
    binding: list[str] | None,
    relation: list[str] | None,
    row: list[str] | None,
    actor: str | None,
    refund_election: RefundElection,
    payment_election: PaymentElection,
    prior_domiciliation_election: PriorDomiciliationElection,
    joint_return_elected: bool | None,
    m303_exonerado_390_attachment_id: str | None,
    m303_exonerado_390_sha256: str | None,
) -> QuickfileRequest:
    """Translate the existing command operands into the closed worker request."""
    casilla_pairs, binding_pairs, relation_pairs, detail_rows = parse_work_calculate_wire_specs(
        casilla=casilla,
        binding=binding,
        relation=relation,
        row=row,
    )
    ordinary_m303_evidence = None
    if modelo == "303" and joint_return_elected is not None:
        ordinary_m303_evidence = ModeloWorkCalculateOrdinaryM303EvidenceRequestV2(
            joint_return_elected=joint_return_elected,
            m303_exonerado_390_attachment_id=m303_exonerado_390_attachment_id,
            m303_exonerado_390_sha256=m303_exonerado_390_sha256,
        )
    return QuickfileRequest(
        profile_id=profile_id,
        bucket_id=_optional_profile_id(bucket_id),
        modelo=modelo,
        period=PublicPeriod.from_period(period),
        revision_id=revision,
        output_path=str(output.absolute()),
        actor=actor or "operator",
        refund_election=refund_election,
        payment_election=payment_election,
        prior_domiciliation_election=prior_domiciliation_election,
        ordinary_m303_filing_evidence=ordinary_m303_evidence,
        inputs=QuickfileCalculationInputs(
            casilla_overrides=tuple(
                ModeloCalculationOverride(key=str(key), value=value) for key, value in casilla_pairs.items()
            ),
            binding_overrides=tuple(
                ModeloCalculationOverride(key=str(key), value=value) for key, value in binding_pairs.items()
            ),
            relation_overrides=tuple(
                ModeloCalculationOverride(key=str(key), value=value) for key, value in relation_pairs.items()
            ),
        ),
        detail_rows=detail_rows,
    )


def quickfile(
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: str,
    output: Path | None = None,
    revision: str | None = None,
    bucket_id: str | None = None,
    casilla: list[str] | None = None,
    binding: list[str] | None = None,
    relation: list[str] | None = None,
    row: list[str] | None = None,
    actor: str | None = None,
    refund_election: RefundElection = RefundElection.COMPENSAR,
    payment_election: PaymentElection = PaymentElection.INGRESO,
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP,
    joint_return_elected: bool | None = None,
    m303_exonerado_390_attachment_id: str | None = None,
    m303_exonerado_390_sha256: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Submit readiness, work creation, calculation, verification and export as one operation."""
    if ctx.invoked_subcommand is not None:
        return
    activate_subcommand_output_language(ctx, output_language)
    if output is None or not str(output).strip() or str(output).strip() == ".":
        raise typer.BadParameter(tr("cli.app.modelo.export.errors.output_required"))

    resolved_period = _resolve_period(modelo=modelo, year=year, period=period)
    client = bound_profile_client(ctx)
    request = _quickfile_request(
        profile_id=client.profile_id,
        modelo=modelo,
        period=resolved_period,
        output=output,
        revision=revision,
        bucket_id=bucket_id,
        casilla=casilla,
        binding=binding,
        relation=relation,
        row=row,
        actor=actor,
        refund_election=refund_election,
        payment_election=payment_election,
        prior_domiciliation_election=prior_domiciliation_election,
        joint_return_elected=joint_return_elected,
        m303_exonerado_390_attachment_id=m303_exonerado_390_attachment_id,
        m303_exonerado_390_sha256=m303_exonerado_390_sha256,
    )
    result = run_quickfile(ctx, request)
    payload = QuickfileResultPayload.from_projection(result, output_path_display=str(output))
    emit_envelope(
        ctx,
        command="quickfile",
        result=payload,
        lines=_quickfile_lines(result, output_path_display=str(output)),
        notices=_quickfile_notices(result),
    )
    if not result.completed:
        raise typer.Exit(code=1)


def _quickfile_lines(result: QuickfileProjection, *, output_path_display: str) -> list[str]:
    """Render the existing per-stage progress block from the worker projection."""
    lines = [
        "operation\tquickfile",
        f"modelo\t{result.modelo}",
        f"filing_year\t{result.filing_year}",
        f"period\t{result.period.to_period().registry_token}",
        f"registry_revision_id\t{result.registry_revision_id}",
    ]
    for stage in result.stages:
        message = quickfile_stage_message(stage)
        detail = f"\t{message}" if message else ""
        lines.append(f"stage\t{stage.stage.value}\t{stage.status.value}{detail}")
    lines.append(f"completed\t{str(result.completed).lower()}")
    if result.stopped_at_stage is not None:
        lines.append(f"stopped_at_stage\t{result.stopped_at_stage.value}")
    if result.work_unit_id is not None:
        lines.append(f"work_unit_id\t{result.work_unit_id}")
    if result.calculation_revision_id is not None:
        lines.append(f"calculation_revision_id\t{result.calculation_revision_id}")
    if result.export is not None:
        lines.append(f"output_path\t{output_path_display}")
        lines.append(f"file_sha256\t{result.export.file_sha256}")
    return lines


def _quickfile_notices(result: QuickfileProjection) -> list[Notice]:
    """Render safe stage notices and canonical verification finding notices."""
    notices = [
        _stage_notice(stage)
        for stage in result.stages
        if stage.status not in (QuickfileStageStatus.OK, QuickfileStageStatus.SKIPPED)
    ]
    if result.stopped_at_stage is QuickfileStage.VERIFY and result.verification_report is not None:
        notices.extend(verification_report_notices(result.verification_report.to_report()))
    return notices


def _stage_notice(stage: QuickfileStageSnapshot) -> Notice:
    """Project a closed stage result without transporting exception prose/context."""
    stage_name, status = stage.stage.value, stage.status.value
    code = f"quickfile.stage.{stage_name}"
    action = (
        resolve_cli_precondition_action(stage.precondition_verdict.to_verdict())
        if stage.precondition_verdict is not None
        else None
    )
    facts = {"stage": stage_name, "status": status, **stage.facts.to_context()}
    error_code = stage.error.code if stage.error is not None else None
    if error_code is not None:
        facts["error_code"] = error_code
    message = quickfile_stage_message(stage)
    reasoned = _admitted_notice(code=code, message=message, action=action, context=facts)
    if reasoned is not None:
        return reasoned
    if error_code is None:
        return Notice(
            severity=NoticeSeverity.WARNING,
            code=code,
            message=tr("application.modelo.quickfile.stage_incomplete", stage=stage_name, status=status),
            action=action,
            context={"stage": stage_name, "status": status},
        )
    registered_code = get_registered_error_code_by_code(error_code).code
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=code,
        message=tr("application.modelo.quickfile.stage_refused", stage=stage_name, error_code=registered_code),
        action=action,
        context={"stage": stage_name, "status": status, "error_code": registered_code},
    )


def _admitted_notice(
    *,
    code: str,
    message: str,
    action: ResolvedPreconditionAction | None,
    context: dict[str, str],
) -> Notice | None:
    """Return a validated notice or let the safe stage/code fallback handle it."""
    from pydantic import ValidationError

    try:
        return Notice(severity=NoticeSeverity.WARNING, code=code, message=message, action=action, context=context)
    except ValidationError:
        return None


__all__ = ["quickfile"]
