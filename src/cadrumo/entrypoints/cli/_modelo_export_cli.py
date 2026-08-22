"""Typer registration for the root-level modelo export command."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Annotated

import typer

from ...application.modelo import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloCalculationRevisionSelector,
    ModeloCalculationRevisionSelectorAmbiguousError,
    ModeloCalculationRevisionSelectorNotFoundError,
    ModeloCalculationRevisionSelectorStateError,
    ModeloExportCommand,
    ModeloExportCrossBucketRefusedError,
    ModeloExportNoActiveBucketError,
    ModeloExportOutputPathError,
    ModeloExportResult,
    ModeloIvaWalletReconciliationBlocked,
    ModeloPaymentElectionCapabilityRefusedError,
    ModeloPaymentElectionIncompatibleError,
    ModeloPriorDomiciliationElectionRefusedError,
    ModeloRefundElectionNotEligibleError,
    ModeloWorkAddressNotFoundError,
    ModeloWorkPeriodTokenError,
    WorkUnitNotFoundError,
    export_modelo_revision,
    resolve_modelo_revision_for_operator_target,
)
from ...application.workflow import workflow_state_repository
from ...core import PaymentElection, Period, PriorDomiciliationElection, RefundElection
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._command_policy import command_execution_policy
from ._common import _emit_envelope, _filing_taxpayer_or_refuse
from ._modelo_cli_support import (
    parse_revision_selector,
    validate_calculation_revision_id,
    validate_work_unit_id,
)
from ._modelo_execution_policies import MODEL_HANDOFF
from ._modelo_payloads import ModeloExportPayload
from ._modelo_work_options import (
    _BucketIdOpt,
    _ModeloOpt,
    _PaymentElectionOpt,
    _PeriodOpt,
    _PriorDomiciliationElectionOpt,
    _RefundElectionOpt,
    _RegistryRevisionOpt,
    _RevisionSelectorOpt,
    _YearOpt,
)


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
        f"next_action\t{result.official_evidence_next_action}",
    ]


def register_export_commands(
    app: typer.Typer,
    *,
    bad_parameter_from_error,
    selector_bad_parameter,
    resolve_default_actor,
    resolve_optional_cli_period: Callable[..., Period | None],
) -> None:
    """Register root-level modelo export commands against the modelo Typer app."""

    @app.command(
        "export",
        help=tr(
            "cli.app.modelo.export.help",
            default=(
                "Export a verified-complete or filed modelo revision to a local "
                "AEAT-compatible fichero-BOE file. Local-only; never contacts AEAT."
            ),
        ),
    )
    @command_execution_policy(MODEL_HANDOFF)
    def modelo_export_verb(
        ctx: typer.Context,
        work_unit_id: Annotated[
            str | None,
            typer.Argument(
                help=tr(
                    "cli.app.modelo.export.work_unit_id_help",
                    default="Work unit id (SHA-256 or unambiguous prefix).",
                ),
            ),
        ] = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        registry_revision: _RegistryRevisionOpt = None,
        bucket_id: _BucketIdOpt = None,
        select: _RevisionSelectorOpt = ModeloCalculationRevisionSelector.CURRENT.value,
        output: Annotated[
            Path | None,
            typer.Option(
                "--output",
                help=tr(
                    "cli.app.modelo.export.output_help",
                    default="Path to write the fichero-BOE artefact to.",
                ),
            ),
        ] = None,
        revision: Annotated[
            str | None,
            typer.Option(
                "--revision",
                help=tr(
                    "cli.app.modelo.export.revision_help",
                    default=(
                        "Calculation revision id to export; defaults to the work unit's "
                        "most recent verified-complete or filed revision."
                    ),
                ),
            ),
        ] = None,
        actor: Annotated[
            str | None,
            typer.Option(
                "--by",
                help=tr(
                    "cli.app.modelo.export.actor_help",
                    default="Operator label recorded into the MODELO_EXPORTED event.",
                ),
            ),
        ] = None,
        refund_election: _RefundElectionOpt = RefundElection.COMPENSAR,
        payment_election: _PaymentElectionOpt = PaymentElection.INGRESO,
        prior_domiciliation_election: _PriorDomiciliationElectionOpt = PriorDomiciliationElection.KEEP,
    ) -> None:
        """Export a verified-complete or filed modelo revision to disk."""
        workflow_state = workflow_state_repository().load()
        workflow_profile = _filing_taxpayer_or_refuse(workflow_state)
        if output is None or not str(output).strip() or str(output).strip() == ".":
            raise typer.BadParameter(
                tr(
                    "cli.app.modelo.export.errors.output_required",
                    default="Supply --output PATH for the fichero-BOE artefact.",
                ),
            )

        try:
            typed_period = resolve_optional_cli_period(year=year, period=period, modelo=modelo)
            selected_revision = resolve_modelo_revision_for_operator_target(
                calculation_revision_id=(validate_calculation_revision_id(revision) if revision is not None else None),
                work_unit_id=validate_work_unit_id(work_unit_id) if work_unit_id is not None else None,
                modelo=modelo,
                year=year,
                period=typed_period,
                registry_revision_id=registry_revision,
                bucket_id=bucket_id,
                selector=parse_revision_selector(select),
                default_for="export",
            )
        except CalculationRevisionNotFoundError as exc:
            if revision is not None:
                raise bad_parameter_from_error(exc) from exc
            raise selector_bad_parameter(exc) from exc
        except (
            ModeloWorkAddressNotFoundError,
            ModeloCalculationRevisionSelectorNotFoundError,
            ModeloCalculationRevisionSelectorStateError,
            ModeloCalculationRevisionSelectorAmbiguousError,
            ModeloWorkPeriodTokenError,
        ) as exc:
            raise selector_bad_parameter(exc) from exc
        target_revision_id = selected_revision.calculation_revision_id

        try:
            from ...adapters.persistence.profile.justificante import JustificanteRepository

            result = export_modelo_revision(
                ModeloExportCommand(
                    calculation_revision_id=target_revision_id,
                    output_path=output,
                    actor=actor or resolve_default_actor(),
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

        export_result = ModeloExportPayload.from_result(result)
        _emit_envelope(
            ctx,
            command="modelo.export",
            result=export_result,
            lines=_export_text_lines(result),
            notices=_export_notices(result),
        )


__all__ = ["register_export_commands"]
