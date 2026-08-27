# ruff: noqa: E501
"""Behavior for modelo work verification and internal filing.

This transport module resolves operator revision targets, calls
:func:`verify_modelo_revision_with_preconditions` or
:func:`file_modelo_revision`, and serializes the
resulting :class:`VerificationReport` or
:class:`ModeloRecord` into :class:`WorkVerifyResult` and
:class:`WorkFileResult` envelopes. Cross-period dependency inspection is read
only and emits :class:`WorkDependenciesResult`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import typer

from ...adapters.persistence.profile.modelos_calculation import CalculationRevisionCatalogueRepository
from ...adapters.persistence.profile.modelos_filing import ModeloRecordCatalogueRepository
from ...adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ...application.calculations import (
    CalculationObservationRepository,
    CrossPeriodCleanStateVerdict,
    CrossPeriodDependencyInventoryItem,
    CrossPeriodExpectedMemberSet,
    cross_period_dependency_inventory,
    evaluate_cross_period_clean_state,
    m111_no_retenciones_periods_for_bucket,
)
from ...application.modelo._calculation_actions import get_calculation_revision
from ...application.modelo._filing_actions import file_modelo_revision
from ...application.modelo._profile_readiness_gate import require_profile_ready_for_work_unit
from ...application.modelo._selectors import ModeloCalculationRevisionSelector
from ...application.modelo._verification_actions import verify_modelo_revision_with_preconditions
from ...application.modelo._work_lifecycle import get_work_unit
from ...application.modelo._work_plazo import calculated_m210_plazo_resolution
from ...application.modelo.verify_selector import ModeloVerifySelector
from ...application.workflow.persistence import workflow_state_repository
from ...core import PaymentElection, PriorDomiciliationElection, RefundElection
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...domain.calculations.registry.applicability import derive_taxpayer_files_economic_activity
from ...domain.calculations.registry.authority import bundled_authority
from ...domain.calculations.registry.errors import RegistrySnapshotError
from ...domain.modelos import CalculationRevisionState
from ._common import _filing_taxpayer_or_refuse, activate_subcommand_output_language, emit_envelope
from ._modelo_behavior_support import require_active_profile, resolve_revision_for_cli
from ._modelo_cli_support import bad_parameter_from_error, resolve_default_actor
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
    m184_socio_handoff_notices,
    m210_plazo_notice,
    verification_report_lines,
    verification_report_notices,
    verification_report_payload,
)


@dataclass(frozen=True, slots=True)
class _VerificationDeps:
    """Typed behavior dependencies shared by verification and filing."""

    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_revision_for_cli: Callable[..., Any]
    resolve_default_actor: Callable[[], str]


def _profile_expected_member_sets(profile: object) -> tuple[CrossPeriodExpectedMemberSet, ...]:
    return tuple(
        CrossPeriodExpectedMemberSet(
            source_modelo=roster.source_modelo,
            filing_year=roster.filing_year,
            period=roster.period,
            member_nifs=roster.member_nifs,
        )
        for roster in getattr(profile, "cross_period_group_member_rosters", ())
    )


def _dependency_inventory_item_payload(
    item: CrossPeriodDependencyInventoryItem,
) -> CrossPeriodDependencyInventoryItemPayload:
    return CrossPeriodDependencyInventoryItemPayload(
        target_modelo=item.target_modelo,
        target_revision_id=item.target_revision_id,
        target_filing_year=item.target_filing_year,
        target_period=item.target_period,
        dependency_count=len(item.dependencies),
        source_modelos=item.source_modelos,
        dependencies=tuple(
            CrossPeriodDependencyRequirementPayload(
                source_modelo=requirement.source_modelo,
                filing_year=requirement.filing_year,
                period=requirement.period,
                source_casilla_ids=requirement.source_casilla_ids,
                origin=requirement.origin.value,
                origin_ids=requirement.origin_ids,
                requires_member_fan_in=requirement.requires_member_fan_in,
            )
            for requirement in item.dependencies
        ),
    )


def _clean_state_payload(verdict: CrossPeriodCleanStateVerdict) -> CrossPeriodCleanStatePayload:
    return CrossPeriodCleanStatePayload(
        target_modelo=verdict.target_modelo,
        target_filing_year=verdict.target_filing_year,
        target_period=verdict.target_period,
        requires_clean_state=verdict.requires_clean_state,
        clean=verdict.clean,
        blockers=tuple(blocker.value for blocker in verdict.blockers),
        dependencies=tuple(
            CrossPeriodDependencyEvidencePayload(
                source_modelo=evidence.requirement.source_modelo,
                filing_year=evidence.requirement.filing_year,
                period=evidence.requirement.period,
                clean=evidence.clean,
                blockers=tuple(blocker.value for blocker in evidence.blockers),
                observation_source_kind=evidence.observation_source_kind,
                filing_record_id=evidence.filing_record_id,
                calculation_revision_id=evidence.calculation_revision_id,
                external_evidence_kind=evidence.external_evidence_kind,
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
            f"target\t{result.clean_state.target_modelo} {result.clean_state.target_filing_year} {result.clean_state.target_period.registry_token}",
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
    require_active_profile()
    selected_revision = resolve_revision_for_cli(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision=revision,
        bucket_id=bucket_id,
        selector=select.to_calculation_revision_selector().value,
        default_for="verify",
    )
    require_profile_ready_for_work_unit(get_work_unit(selected_revision.work_unit_id))
    workflow_profile = _filing_taxpayer_or_refuse(workflow_state_repository().load())
    already_verified = selected_revision.state is not CalculationRevisionState.BORRADOR
    verification = verify_modelo_revision_with_preconditions(
        selected_revision.calculation_revision_id,
        actor=actor or resolve_default_actor(),
        workflow_profile=workflow_profile,
    )
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
    plazo_resolution = calculated_m210_plazo_resolution(
        work_unit=get_work_unit(selected_revision.work_unit_id),
        revision=selected_revision,
        workflow_profile=workflow_profile,
    )
    if plazo_resolution is not None:
        notices.append(m210_plazo_notice(plazo_resolution))
    if already_verified:
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
    notices.extend(m184_socio_handoff_notices(get_calculation_revision(selected_revision.calculation_revision_id)))
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
    require_active_profile()
    if period is not None and modelo is None:
        raise typer.BadParameter(tr("cli.app.modelo.work.dependencies_period_requires_modelo"))
    try:
        state = workflow_state_repository().load()
        workflow_profile = _filing_taxpayer_or_refuse(state)
        inventory = cross_period_dependency_inventory(
            bundled_authority(), filing_year=year, modelos=(modelo,) if modelo is not None else None
        )
        clean_state = None
        if modelo is not None and period is not None:
            active_bucket_id = state.active_profile_bucket_id() or ""
            snapshot = bundled_authority().snapshot(modelo, filing_year=year, period=period)
            clean_state = evaluate_cross_period_clean_state(
                snapshot,
                bucket_id=active_bucket_id,
                observation_repository=CalculationObservationRepository(),
                filing_repository=ModeloRecordCatalogueRepository(),
                calculation_repository=CalculationRevisionCatalogueRepository(),
                verification_repository=VerificationReportCatalogueRepository(),
                expected_member_sets=_profile_expected_member_sets(workflow_profile),
                taxpayer_tax_id=workflow_profile.tax_id,
                activity_start_date=workflow_profile.activity_start_date,
                taxpayer_files_economic_activity=derive_taxpayer_files_economic_activity(workflow_profile),
                m111_no_retenciones_periods=m111_no_retenciones_periods_for_bucket(active_bucket_id),
            )
    except (FileNotFoundError, RegistrySnapshotError, ValueError) as exc:
        raise bad_parameter_from_error(exc) from exc
    result = WorkDependenciesResult(
        filing_year=year,
        modelo_filter=modelo,
        period_filter=period,
        target_modelos=inventory.target_modelos,
        source_modelos=inventory.source_modelos,
        target_count=len(inventory.items),
        items=tuple(_dependency_inventory_item_payload(item) for item in inventory.items),
        clean_state=_clean_state_payload(clean_state) if clean_state is not None else None,
    )
    emit_envelope(ctx, command="modelo.work.dependencies", result=result, lines=_dependency_inventory_lines(result))


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
    require_active_profile()
    selected_revision = resolve_revision_for_cli(
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        registry_revision=revision,
        bucket_id=bucket_id,
        selector=select,
        default_for="file",
    )
    require_profile_ready_for_work_unit(get_work_unit(selected_revision.work_unit_id))
    workflow_profile = _filing_taxpayer_or_refuse(workflow_state_repository().load())
    already_filed = selected_revision.state is CalculationRevisionState.PRESENTADO
    record = file_modelo_revision(
        selected_revision.calculation_revision_id,
        actor=actor or resolve_default_actor(),
        workflow_profile=workflow_profile,
        notes=notes,
        refund_election=refund_election,
        payment_election=payment_election,
        prior_domiciliation_election=prior_domiciliation_election,
    )
    result = WorkFileResult.model_validate(filing_record_payload(record).model_dump(mode="python"))
    lines = ["operation\tmodelo.work.file", *filing_record_lines(record)]
    lines.append(f"filing_disambiguation\t{tr('cli.app.modelo.work.file_internal_disambiguation')}")
    notices: list[Notice] = []
    if already_filed:
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
    notices.extend(m184_socio_handoff_notices(get_calculation_revision(record.calculation_revision_id)))
    emit_envelope(ctx, command="modelo.work.file", result=result, lines=lines, notices=notices or None)
