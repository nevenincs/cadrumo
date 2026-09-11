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
from ...application.modelo.operator_inputs import ModeloExportOperatorInput
from ...application.workflow.persistence import workflow_state_repository
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...domain.deadlines.models import TaxpayerProfile
from ._modelo_behavior_support import resolve_exportable_revision_for_cli
from ._modelo_cli_support import (
    bad_parameter_from_error,
    resolve_default_actor,
)
from ._modelo_payloads import ModeloExportPayload
from .common import emit_envelope, filing_taxpayer_or_refuse


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


def export_modelo_revision_for_cli(
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


__all__ = ["export_modelo_revision_for_cli", "modelo_export_verb"]


def modelo_export_verb(
    ctx: typer.Context,
    **input_values: object,
) -> None:
    """Export a verified-complete or filed modelo revision to disk."""
    operator_input = ModeloExportOperatorInput.model_validate(input_values)
    workflow_state = workflow_state_repository().load()
    workflow_profile = filing_taxpayer_or_refuse(workflow_state)
    if (
        operator_input.output is None
        or not str(operator_input.output).strip()
        or str(operator_input.output).strip() == "."
    ):
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.export.errors.output_required",
                default="Supply --output PATH for the fichero-BOE artefact.",
            )
        )
    selected_revision = resolve_exportable_revision_for_cli(
        revision=operator_input.revision,
        work_unit_id=operator_input.work_unit_id,
        modelo=operator_input.modelo,
        year=operator_input.year,
        period=operator_input.period,
        registry_revision=operator_input.registry_revision,
        bucket_id=operator_input.bucket_id,
        select=operator_input.select,
    )
    target_revision_id = selected_revision.calculation_revision_id
    result = export_modelo_revision_for_cli(
        calculation_revision_id=target_revision_id,
        output_path=operator_input.output,
        actor=operator_input.actor or resolve_default_actor(),
        refund_election=operator_input.refund_election,
        payment_election=operator_input.payment_election,
        prior_domiciliation_election=operator_input.prior_domiciliation_election,
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


setattr(modelo_export_verb, "__input_model__", ModeloExportOperatorInput)  # noqa: B010
