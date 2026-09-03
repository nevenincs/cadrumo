"""Behavior handler for the root-level modelo export command."""

from __future__ import annotations

from pathlib import Path

import typer

from ...application.modelo.action_errors import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloPaymentElectionCapabilityRefusedError,
    ModeloPaymentElectionIncompatibleError,
    ModeloPriorDomiciliationElectionRefusedError,
    ModeloRefundElectionNotEligibleError,
    WorkUnitNotFoundError,
)
from ...application.modelo.export import (
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportOutputPathError,
    ModeloExportResult,
    export_modelo_revision,
)
from ...application.modelo.iva_wallet_gate import ModeloIvaWalletReconciliationBlocked
from ...application.modelo.selectors import (
    ModeloCalculationRevisionSelector,
)
from ...application.workflow.persistence import workflow_state_repository
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...domain.deadlines.models import TaxpayerProfile
from ._common import emit_envelope, filing_taxpayer_or_refuse
from ._modelo_behavior_support import resolve_exportable_revision_for_cli
from ._modelo_cli_support import (
    bad_parameter_from_error,
    resolve_default_actor,
)
from ._modelo_payloads import ModeloExportPayload


def _local_export_evidence_notice(result: ModeloExportResult) -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.export.local_export_not_official_evidence",
        message="The local export is not official filing evidence.",
        context={
            "evidence_status": result.local_evidence_status,
            "modelo": str(result.modelo),
            "filing_year": str(result.filing_year),
            "period": result.period.registry_token,
        },
    )


def _completeness_advisory_notice(result: ModeloExportResult) -> Notice:
    return Notice(
        severity=NoticeSeverity.WARNING,
        code="modelo.export.completeness_unverified",
        message=result.completeness_advisory_message,
        context={
            "reason": "no_completeness_manifest",
            "modelo": str(result.modelo),
            "filing_year": str(result.filing_year),
            "period": result.period.registry_token,
        },
    )


def _export_notices(result: ModeloExportResult) -> list[Notice]:
    notices = [_local_export_evidence_notice(result)]
    if result.completeness_unverified:
        notices.append(_completeness_advisory_notice(result))
    return notices


def _export_text_lines(result: ModeloExportResult) -> list[str]:
    return [
        "operation\tmodelo.export",
        f"work_unit_id\t{result.work_unit_id}",
        f"calculation_revision_id\t{result.calculation_revision_id}",
        f"bucket\t{result.bucket_id}",
        f"modelo\t{result.modelo}",
        f"filing_year\t{result.filing_year}",
        f"period\t{result.period}",
        f"output_path\t{result.output_path}",
        f"byte_size\t{result.byte_size}",
        f"file_sha256\t{result.file_sha256}",
        f"format\t{result.format}",
        f"bucket_event_id\t{result.bucket_event_id}",
        f"evidence_status\t{result.local_evidence_status}",
        f"evidence_notice\t{result.official_evidence_message}",
    ]


def _export_modelo_revision_for_cli(
    *,
    calculation_revision_id: str,
    output_path: Path,
    actor: str,
    refund_election: RefundElection,
    payment_election: PaymentElection,
    prior_domiciliation_election: PriorDomiciliationElection,
    workflow_profile: TaxpayerProfile,
) -> ModeloExportResult:
    """Run the canonical export service and translate its CLI-owned refusals.

    Both the standalone export and review-package builder create a fichero-BOE
    draft through this boundary. Their output contracts remain separate.
    """
    try:
        from ...adapters.persistence.profile.justificante import JustificanteRepository

        return export_modelo_revision(
            ModeloExportCommand(
                calculation_revision_id=calculation_revision_id,
                output_path=output_path,
                actor=actor,
                refund_election=refund_election,
                payment_election=payment_election,
                prior_domiciliation_election=prior_domiciliation_election,
            ),
            workflow_profile=workflow_profile,
            justificante_repository=JustificanteRepository(),
        )
    except (
        CalculationRevisionNotFoundError,
        CalculationRevisionStateError,
        WorkUnitNotFoundError,
        ModeloExportCrossBucketRefusedError,
        ModeloExportNoActiveBucketError,
        ModeloExportOutputPathError,
        ModeloIvaWalletReconciliationBlocked,
        ModeloPaymentElectionCapabilityRefusedError,
        ModeloPaymentElectionIncompatibleError,
        ModeloPriorDomiciliationElectionRefusedError,
        ModeloRefundElectionNotEligibleError,
    ) as exc:
        raise bad_parameter_from_error(exc) from exc


__all__ = ["modelo_export_verb"]


def modelo_export_verb(
    ctx: typer.Context,
    work_unit_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    registry_revision: str | None = None,
    bucket_id: str | None = None,
    select: str = ModeloCalculationRevisionSelector.CURRENT.value,
    output: Path | None = None,
    revision: str | None = None,
    actor: str | None = None,
    refund_election: RefundElection = RefundElection.COMPENSAR,
    payment_election: PaymentElection = PaymentElection.INGRESO,
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP,
) -> None:
    """Export a verified-complete or filed modelo revision to disk."""
    workflow_state = workflow_state_repository().load()
    workflow_profile = filing_taxpayer_or_refuse(workflow_state)
    if output is None or not str(output).strip() or str(output).strip() == ".":
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.export.errors.output_required",
                default="Supply --output PATH for the fichero-BOE artefact.",
            )
        )
    selected_revision = resolve_exportable_revision_for_cli(
        revision=revision,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision=registry_revision,
        bucket_id=bucket_id,
        select=select,
    )
    target_revision_id = selected_revision.calculation_revision_id
    result = _export_modelo_revision_for_cli(
        calculation_revision_id=target_revision_id,
        output_path=output,
        actor=actor or resolve_default_actor(),
        refund_election=refund_election,
        payment_election=payment_election,
        prior_domiciliation_election=prior_domiciliation_election,
        workflow_profile=workflow_profile,
    )
    export_result = ModeloExportPayload.from_result(result)
    emit_envelope(
        ctx,
        command="modelo.export",
        result=export_result,
        lines=_export_text_lines(result),
        notices=_export_notices(result),
    )
