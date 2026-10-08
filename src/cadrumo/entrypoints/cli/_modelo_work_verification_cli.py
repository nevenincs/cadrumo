"""Behavior for modelo work verification and internal filing.

Verify and file select through the registered runtime and render their
settled writer results. Cross-period dependency inspection remains a separate
read-only command.
"""

from __future__ import annotations

import typer

from ...application.modelo.action_errors import CalculationRevisionStateError, VerificationReportNotFoundError
from ...application.modelo.dependency_projection import DependencyCleanStateSnapshot, DependencyInventoryItemSnapshot
from ...application.modelo.preconditions import build_modelo_work_file_unverified_revision_failure
from ...application.modelo.selectors import ModeloCalculationRevisionSelector
from ...application.modelo.verify_selector import ModeloVerifySelector
from ...application.modelo.work_filing_contracts import (
    ModeloWorkFileApproval,
    ModeloWorkFilePublicResultV2,
    ModeloWorkFileRequest,
)
from ...application.modelo.work_verification_contracts import ModeloWorkVerifyPublicResultV2, ModeloWorkVerifyRequest
from ...application.runtime.contracts import RuntimeRefusalCode, RuntimeRefusalError
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.payment_election import PaymentElection
from ...core.prior_domiciliation_election import PriorDomiciliationElection
from ...core.refund_election import RefundElection
from ...domain.modelos.calculation_revision import CalculationRevisionState
from ._modelo_behavior_support import resolve_optional_cli_period
from ._modelo_cli_support import (
    parse_revision_selector,
    resolve_default_actor,
)
from ._modelo_payloads import (
    CrossPeriodCleanStatePayload,
    CrossPeriodDependencyEvidencePayload,
    CrossPeriodDependencyInventoryItemPayload,
    CrossPeriodDependencyRequirementPayload,
    WorkDependenciesResult,
    WorkFileResult,
    WorkVerifyResult,
)
from ._modelo_rendering import (
    filing_record_lines,
    filing_record_payload,
    m184_socio_handoff_advisory_notices,
    m210_plazo_notice,
    verification_report_lines,
    verification_report_notices,
    verification_report_payload,
)
from .common import activate_subcommand_output_language, emit_envelope
from .registered_operation_errors import submitted_operation_error
from .runtime_modelo_dependencies import read_modelo_dependencies
from .runtime_modelo_verification import (
    run_modelo_work_filing,
    run_modelo_work_verification,
    select_modelo_work_revision_for_cli,
)


def _dependency_inventory_item_payload(
    item: DependencyInventoryItemSnapshot,
) -> CrossPeriodDependencyInventoryItemPayload:
    return CrossPeriodDependencyInventoryItemPayload(
        target_modelo=item.target_modelo,
        target_revision_id=item.target_revision_id,
        target_filing_year=item.target_filing_year,
        target_period=item.target_period.to_period(),
        dependency_count=len(item.dependencies),
        source_modelos=item.source_modelos,
        dependencies=tuple(
            CrossPeriodDependencyRequirementPayload(
                source_modelo=requirement.source_modelo,
                filing_year=requirement.filing_year,
                period=requirement.period.to_period(),
                source_casilla_ids=requirement.source_casilla_ids,
                required_source_casilla_ids=requirement.required_source_casilla_ids,
                source_presence_groups=requirement.source_presence_groups,
                origin=requirement.origin.value,
                origin_ids=requirement.origin_ids,
                legal_refs=requirement.legal_refs,
                source_refs=requirement.source_refs,
                requires_member_fan_in=requirement.requires_member_fan_in,
            )
            for requirement in item.dependencies
        ),
    )


def _clean_state_payload(verdict: DependencyCleanStateSnapshot) -> CrossPeriodCleanStatePayload:
    return CrossPeriodCleanStatePayload(
        target_modelo=verdict.target_modelo,
        target_filing_year=verdict.target_filing_year,
        target_period=verdict.target_period.to_period(),
        requires_clean_state=verdict.requires_clean_state,
        clean=verdict.clean,
        blockers=tuple(blocker.value for blocker in verdict.blockers),
        dependencies=tuple(
            CrossPeriodDependencyEvidencePayload(
                source_modelo=evidence.source_modelo,
                filing_year=evidence.filing_year,
                period=evidence.period.to_period(),
                clean=evidence.clean,
                blockers=tuple(blocker.value for blocker in evidence.blockers),
                observation_source_kind=evidence.observation_source_kind.value
                if evidence.observation_source_kind is not None
                else None,
                filing_record_id=evidence.filing_record_id,
                calculation_revision_id=evidence.calculation_revision_id,
                external_evidence_kind=evidence.external_evidence_kind.value
                if evidence.external_evidence_kind is not None
                else None,
                expected_member_nifs=evidence.expected_member_nifs,
                observed_member_nifs=evidence.observed_member_nifs,
                missing_member_nifs=evidence.missing_member_nifs,
                unexpected_member_nifs=evidence.unexpected_member_nifs,
            )
            for evidence in verdict.dependencies
        ),
    )


def _dependency_inventory_lines(result: WorkDependenciesResult) -> list[str]:
    lines = [
        "operation\tmodelo.work.dependencies",
        f"filing_year\t{result.filing_year}",
        f"modelo_filter\t{result.modelo_filter or ''}",
        f"period_filter\t{result.period_filter or ''}",
        f"target_count\t{result.target_count}",
        f"target_modelos\t{', '.join(result.target_modelos)}",
        f"source_modelos\t{', '.join(result.source_modelos)}",
        "target_modelo\tyear\tperiod\trevision\tdependency_count\tsource_modelos",
    ]
    lines.extend(
        "\t".join(
            (
                item.target_modelo,
                str(item.target_filing_year),
                item.target_period.registry_token,
                item.target_revision_id,
                str(item.dependency_count),
                ", ".join(item.source_modelos),
            )
        )
        for item in result.items
    )
    if result.clean_state is None:
        return lines
    lines.extend(
        [
            "clean_state",
            "target\t"
            f"{result.clean_state.target_modelo} {result.clean_state.target_filing_year} "
            f"{result.clean_state.target_period.registry_token}",
            f"requires_clean_state\t{result.clean_state.requires_clean_state}",
            f"clean\t{result.clean_state.clean}",
            f"blockers\t{', '.join(result.clean_state.blockers)}",
            "source_modelo\tyear\tperiod\tclean\tblockers\tevidence_kind\tfiling_record_id",
        ]
    )
    lines.extend(
        "\t".join(
            (
                evidence.source_modelo,
                str(evidence.filing_year),
                evidence.period.registry_token,
                str(evidence.clean),
                ", ".join(evidence.blockers),
                evidence.external_evidence_kind or "",
                evidence.filing_record_id or "",
            )
        )
        for evidence in result.clean_state.dependencies
    )
    return lines


__all__ = ["work_dependencies", "work_file", "work_verify"]


def work_verify(
    ctx: typer.Context,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    work_unit_id: str | None = None,
    select: ModeloVerifySelector = ModeloVerifySelector.CURRENT,
    bucket_id: str | None = None,
    actor: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Persist a :class:`VerificationReport` for the selected draft revision."""
    activate_subcommand_output_language(ctx, output_language)
    client, selected = select_modelo_work_revision_for_cli(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        selector=select.to_calculation_revision_selector(),
        default_for="verify",
    )
    completed = run_modelo_work_verification(
        client,
        work_unit_id=selected.unit.work_unit_id,
        request=ModeloWorkVerifyRequest(
            calculation_revision_id=selected.calculation_revision_id,
            actor=actor or resolve_default_actor(),
        ),
    )
    projection = completed.projection
    if not isinstance(projection, ModeloWorkVerifyPublicResultV2):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    verification = projection.verification.to_verification()
    report = verification.report
    report_payload = verification_report_payload(report, finding_preconditions=verification.finding_preconditions)
    result = WorkVerifyResult.model_validate(report_payload.model_dump(mode="python"))
    lines = [
        "operation\tmodelo.work.verify",
        *verification_report_lines(
            report, finding_actions=tuple(finding.action for finding in report_payload.findings)
        ),
    ]
    notices = verification_report_notices(report)
    if projection.advisories.m210_plazo is not None:
        notices.append(m210_plazo_notice(projection.advisories.m210_plazo.to_resolution()))
    if not verification.published:
        noop_message = tr(
            "cli.app.modelo.work.verify_idempotent_noop", calculation_revision_id=report.calculation_revision_id
        )
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="modelo.work.verify.idempotent_noop",
                message=noop_message,
                context={
                    "calculation_revision_id": report.calculation_revision_id,
                    "verification_report_id": report.verification_report_id,
                },
            )
        )
        lines.append(noop_message)
    notices.extend(m184_socio_handoff_advisory_notices(projection.advisories.m184_socio_handoffs))
    emit_envelope(ctx, command="modelo.work.verify", result=result, lines=lines, notices=notices)
    if not report.granted_verificado_completo:
        raise typer.Exit(code=1)


def work_dependencies(
    ctx: typer.Context,
    year: int,
    modelo: str | None = None,
    period: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Show cross-period dependency inventory and clean-state blockers."""
    activate_subcommand_output_language(ctx, output_language)
    if period is not None and modelo is None:
        raise typer.BadParameter(tr("cli.app.modelo.work.dependencies_period_requires_modelo"))
    typed_period = resolve_optional_cli_period(year=year, period=period, modelo=modelo)
    completed = read_modelo_dependencies(ctx, filing_year=year, modelo=modelo, period=typed_period)
    snapshot = completed.snapshot
    try:
        result = WorkDependenciesResult(
            filing_year=snapshot.filing_year,
            modelo_filter=snapshot.modelo_filter,
            period_filter=period,
            target_modelos=snapshot.target_modelos,
            source_modelos=snapshot.source_modelos,
            target_count=len(snapshot.items),
            items=tuple(_dependency_inventory_item_payload(item) for item in snapshot.items),
            clean_state=_clean_state_payload(snapshot.clean_state) if snapshot.clean_state is not None else None,
        )
        emit_envelope(ctx, command="modelo.work.dependencies", result=result, lines=_dependency_inventory_lines(result))
    except Exception:
        receipt = completed.completion
        raise submitted_operation_error(
            receipt.operation_id,
            RuntimeRefusalCode.UNAVAILABLE.value,
            terminal_condition=receipt.terminal_condition,
            effect=receipt.effect,
            refusal_code=receipt.refusal_code,
        ) from None


def work_file(
    ctx: typer.Context,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    work_unit_id: str | None = None,
    select: str = ModeloCalculationRevisionSelector.CURRENT.value,
    bucket_id: str | None = None,
    actor: str | None = None,
    notes: str | None = None,
    refund_election: RefundElection = RefundElection.COMPENSAR,
    payment_election: PaymentElection = PaymentElection.INGRESO,
    prior_domiciliation_election: PriorDomiciliationElection = PriorDomiciliationElection.KEEP,
    output_language: OutputLanguage | None = None,
) -> None:
    """Create an internal :class:`ModeloRecord` for a verified revision."""
    activate_subcommand_output_language(ctx, output_language)
    client, selected = select_modelo_work_revision_for_cli(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        selector=parse_revision_selector(select),
        default_for="file",
    )
    if selected.calculation_state not in {
        CalculationRevisionState.VERIFICADO_COMPLETO,
        CalculationRevisionState.PRESENTADO,
    }:
        raise CalculationRevisionStateError(
            translated_message="errors.error.error_modelo_calculation_revision_state",
            context={
                "calculation_revision_id": selected.calculation_revision_id,
                "state": selected.calculation_state.value,
            },
            precondition_failure=build_modelo_work_file_unverified_revision_failure(
                calculation_revision_id=selected.calculation_revision_id,
                state=selected.calculation_state.value,
                work_unit=selected.unit.to_work_unit(),
            ),
        )
    if not selected.granted_verificado_completo or selected.verification_report_id is None:
        raise VerificationReportNotFoundError(
            translated_message="application.modelo.errors.verification_report_not_found",
            context={"calculation_revision_id": selected.calculation_revision_id},
        )
    completion = run_modelo_work_filing(
        client,
        work_unit_id=selected.unit.work_unit_id,
        request=ModeloWorkFileRequest(
            approval=ModeloWorkFileApproval(
                calculation_revision_id=selected.calculation_revision_id,
                verification_report_id=selected.verification_report_id,
            ),
            actor=actor or resolve_default_actor(),
            notes=notes,
            refund_election=refund_election,
            payment_election=payment_election,
            prior_domiciliation_election=prior_domiciliation_election,
        ),
    )
    projection = completion.projection
    if not isinstance(projection, ModeloWorkFilePublicResultV2):
        raise RuntimeRefusalError(RuntimeRefusalCode.INVALID_FRAME)
    record = projection.record.to_record()
    result = WorkFileResult.model_validate(filing_record_payload(record).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.file", *filing_record_lines(record)]
    lines.append(f"filing_disambiguation\t{tr('cli.app.modelo.work.file_internal_disambiguation')}")
    notices: list[Notice] = []
    if not projection.published:
        noop_message = tr(
            "cli.app.modelo.work.file_idempotent_noop", calculation_revision_id=record.calculation_revision_id
        )
        notices.append(
            Notice(
                severity=NoticeSeverity.INFO,
                code="modelo.work.file.idempotent_noop",
                message=noop_message,
                context={
                    "calculation_revision_id": record.calculation_revision_id,
                    "filing_record_id": record.filing_record_id,
                },
            )
        )
        lines.append(noop_message)
    notices.extend(m184_socio_handoff_advisory_notices(projection.advisories.m184_socio_handoffs))
    emit_envelope(ctx, command="modelo.work.file", result=result, lines=lines, notices=notices or None)
