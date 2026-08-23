"""CLI command for ``aeat app quickfile`` — the one-command modelo filing chain.

Drives the full local filing lifecycle for one ``(modelo, year, period)`` target
in a single verb: it resolves readiness, resumes or creates the work unit,
calculates a draft revision, verifies it, and exports the verified revision to a
local fichero-BOE file — surfacing each stage's typed outcome and stopping
instructively at the first stage that refuses. It re-implements no stage; it is a
thin transport over :func:`application.modelo.run_modelo_quickfile`, which
composes the existing single-stage application services.

The command is a child of ``app`` (the CLI root surface is pinned to ``config``
and ``app``; this adds no third root). It is BUILD + EXPORT only: it never
performs a live AEAT submission and never contacts AEAT. The terminal step is the
local export the human files themselves through the AEAT sede
(``sensitive-financial-data-secure-storage-only``).
"""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.modelo import QuickfileCommand, run_modelo_quickfile
from ...application.workflow import workflow_state_repository
from ...core import OutputLanguage, PaymentElection, Period, PeriodError, PriorDomiciliationElection, RefundElection
from ...core.i18n import tr
from ...core.json_contract import Notice
from ._app_quickfile_payloads import QuickfileResultPayload
from ._common import (
    _emit_envelope,
    _filing_taxpayer_or_refuse,
    _no_active_profile_refusal,
    activate_subcommand_output_language,
)
from ._m303_filing_evidence_input import m303_filing_instance_evidence_from_cli
from ._modelo_cli_support import unsupported_local_work_period_refusal, work_calculate_input_bundle_from_cli
from ._modelo_rendering import advisory_notice, verification_report_notices


def _require_active_profile() -> str:
    """Return the active bucket id, refusing cold-start with clean guidance."""
    from ...core import resolve_active_bucket_id

    bucket_id = resolve_active_bucket_id()
    if bucket_id is None:
        raise _no_active_profile_refusal()
    return bucket_id


def _resolve_period(*, modelo: str, year: int, period: str) -> Period:
    try:
        return Period.from_year_and_code(year, period.strip())
    except PeriodError as exc:
        if refusal := unsupported_local_work_period_refusal(modelo=modelo, token=period):
            raise refusal from exc
        raise typer.BadParameter(str(exc)) from exc


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
    m303_filing_evidence: Path | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Run readiness -> create -> calculate -> verify -> export for one modelo target."""
    if ctx.invoked_subcommand is not None:
        return
    activate_subcommand_output_language(ctx, output_language)
    # ``aeat app quickfile`` is an ``invoke_without_command`` group, so the CLI
    # root treats it as a bare-subgroup introspection surface and skips the
    # active-bucket session activation it performs for leaf verbs. This command
    # DOES mutate profile-bound storage (calculate + verify persist), so it
    # activates the session itself through the same root helper — which also
    # applies the storage write-policy guard for the ``app quickfile`` path.
    from . import _activate_active_bucket_session

    _activate_active_bucket_session(ctx)
    if output is None or not str(output).strip() or str(output).strip() == ".":
        raise typer.BadParameter(tr("cli.app.modelo.export.errors.output_required"))

    resolved_bucket = _require_active_profile() if bucket_id is None else bucket_id
    resolved_period = _resolve_period(modelo=modelo, year=year, period=period)
    resolved_year = resolved_period.filing_year
    resolved_actor = actor or "operator"
    workflow_profile = _filing_taxpayer_or_refuse(workflow_state_repository().load())
    filing_instance_evidence = m303_filing_instance_evidence_from_cli(
        modelo=modelo,
        period=resolved_period,
        evidence_file=m303_filing_evidence,
    )

    def _build_inputs(work_unit_id: str):
        return work_calculate_input_bundle_from_cli(
            work_unit_id=work_unit_id,
            casilla=casilla,
            binding=binding,
            relation=relation,
            row=row,
            borrador_snapshot_id=None,
            filing_instance_evidence=filing_instance_evidence,
            prestacion_inss_exenta=None,
            rescate_plan_pensiones_capital=None,
            rescate_plan_pensiones_aportaciones_pre_2007=None,
            rescate_plan_pensiones_aportaciones_totales=None,
            sal_beneficio_neto=None,
            sal_reserva_dotada=None,
            sal_capital_social=None,
            autoconsumo_promotor_base=None,
        )

    result = run_modelo_quickfile(
        QuickfileCommand(
            bucket_id=resolved_bucket,
            modelo=modelo,
            filing_year=resolved_year,
            period=resolved_period,
            registry_revision_id=revision,
            output_path=output,
            actor=resolved_actor,
            refund_election=refund_election,
            payment_election=payment_election,
            prior_domiciliation_election=prior_domiciliation_election,
            filing_instance_evidence=filing_instance_evidence,
        ),
        workflow_profile=workflow_profile,
        build_calculation_inputs=_build_inputs,
    )

    payload = QuickfileResultPayload.from_result(result)
    _emit_envelope(
        ctx,
        command="quickfile",
        result=payload,
        lines=_quickfile_lines(result),
        notices=_quickfile_notices(result),
    )
    if not result.completed:
        raise typer.Exit(code=1)


def _quickfile_lines(result) -> list[str]:
    """Render the per-stage progress block for text mode."""
    lines = [
        "operation\tquickfile",
        f"modelo\t{result.modelo}",
        f"filing_year\t{result.filing_year}",
        f"period\t{result.period.registry_token}",
        f"registry_revision_id\t{result.registry_revision_id}",
    ]
    for outcome in result.stages:
        detail = f"\t{outcome.message}" if outcome.message else ""
        lines.append(f"stage\t{outcome.stage.value}\t{outcome.status.value}{detail}")
    lines.append(f"completed\t{str(result.completed).lower()}")
    if result.stopped_at_stage is not None:
        lines.append(f"stopped_at_stage\t{result.stopped_at_stage.value}")
    if result.work_unit is not None:
        lines.append(f"work_unit_id\t{result.work_unit.work_unit_id}")
    if result.calculation_revision is not None:
        lines.append(f"calculation_revision_id\t{result.calculation_revision.calculation_revision_id}")
    if result.export_result is not None:
        lines.append(f"output_path\t{result.export_result.output_path}")
        lines.append(f"file_sha256\t{result.export_result.file_sha256}")
    return lines


def _quickfile_notices(result) -> list[Notice]:
    """Surface each non-OK stage as a warning notice on the shared channel.

    A refused verify additionally re-uses the verification report's own findings
    notices so the operator sees the exact blocking findings and their next
    actions, identical to what ``aeat app modelo work verify`` would surface.
    """
    from ...application.modelo import QuickfileStage, QuickfileStageStatus

    notices: list[Notice] = []
    for outcome in result.stages:
        if outcome.status in (QuickfileStageStatus.OK, QuickfileStageStatus.SKIPPED):
            continue
        message = (
            tr(outcome.translated_message, **dict(outcome.context))
            if outcome.translated_message is not None
            else outcome.message
        )
        notices.append(
            advisory_notice(
                f"quickfile.stage.{outcome.stage.value}",
                message,
                context={"stage": outcome.stage.value, "status": outcome.status.value, **dict(outcome.context)},
            ),
        )
    if result.stopped_at_stage is QuickfileStage.VERIFY and result.verification_report is not None:
        notices.extend(verification_report_notices(result.verification_report))
    return notices


__all__ = ["quickfile"]
