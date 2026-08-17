"""Typer registration for modelo work verification and internal filing.

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
from typing import Annotated, Any

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
from ...application.modelo import (
    ModeloCalculationRevisionSelector,
    ModeloVerifySelector,
    file_modelo_revision,
    get_calculation_revision,
    get_work_unit,
    require_profile_ready_for_work_unit,
    verify_modelo_revision_with_preconditions,
)
from ...application.workflow import workflow_state_repository
from ...core import PaymentElection, PriorDomiciliationElection, RefundElection
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ...core.resources import resources
from ...domain.calculations.registry import RegistrySnapshotError, derive_taxpayer_files_economic_activity
from ...domain.modelos import CalculationRevisionState
from ._common import _emit_envelope, _filing_taxpayer_or_refuse
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
    verification_report_lines,
    verification_report_notices,
    verification_report_payload,
)
from ._modelo_work_options import (
    _ActorOpt,
    _BucketIdOpt,
    _CalculationRevisionIdArg,
    _ModeloOpt,
    _PaymentElectionOpt,
    _PeriodOpt,
    _PriorDomiciliationElectionOpt,
    _RefundElectionOpt,
    _RevisionOpt,
    _RevisionSelectorOpt,
    _WorkUnitIdOpt,
    _YearOpt,
)


# KWARGS-ANY-RATIONALE-CLI-DI-RESOLVERS: resolve_revision_for_cli is an injected
# resolver callable whose concrete return type varies by call site;
# Callable[..., Any] is the DI composition seam.
@dataclass(frozen=True, slots=True)
class _VerificationDeps:
    """The CLI callables the verification/filing sub-registrars are composed with.

    Bundled so the per-command sub-registrars share one injection seam instead of
    re-declaring the same callable block each (the ``_WizardDeps`` pattern). The
    public :func:`register_work_verification_commands` keeps its explicit keyword
    signature — this bundle is internal composition only.
    """

    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None]
    require_active_profile: Callable[[], None]
    resolve_revision_for_cli: Callable[..., Any]
    resolve_default_actor: Callable[[], str]


# KWARGS-ANY-RATIONALE-CLI-DI-RESOLVERS: resolve_revision_for_cli is an injected
# resolver callable whose concrete return type varies by call site;
# Callable[..., Any] is the DI composition seam.
def register_work_verification_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    resolve_revision_for_cli: Callable[..., Any],
    resolve_default_actor: Callable[[], str],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> None:
    """Register revision verification, dependency, and internal filing commands."""
    deps = _VerificationDeps(
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        resolve_revision_for_cli=resolve_revision_for_cli,
        resolve_default_actor=resolve_default_actor,
    )
    _register_work_verify_command(work_app, deps=deps)
    _register_work_dependencies_command(
        work_app,
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        bad_parameter_from_error=bad_parameter_from_error,
    )
    _register_work_file_command(work_app, deps=deps)


def _register_work_verify_command(work_app: typer.Typer, *, deps: _VerificationDeps) -> None:
    @work_app.command("verify", help=tr("cli.app.modelo.work.verify_help"))
    def work_verify(
        ctx: typer.Context,
        calculation_revision_id: _CalculationRevisionIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        work_unit_id: _WorkUnitIdOpt = None,
        select: Annotated[
            ModeloVerifySelector,
            typer.Option(
                "--select",
                help=tr("cli.app.modelo.work.verify_selector_help"),
            ),
        ] = ModeloVerifySelector.CURRENT,
        bucket_id: _BucketIdOpt = None,
        actor: _ActorOpt = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Persist a :class:`VerificationReport` for the selected draft revision."""
        deps.activate_output_language(ctx, output_language)
        deps.require_active_profile()
        selected_revision = deps.resolve_revision_for_cli(
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
        # A revision already out of BORRADOR is the current verified answer, so
        # the verify call is a guarded-idempotent no-op that returns the
        # existing granting report unchanged (no re-run, no duplicate lifecycle
        # event). Capture that before the call to surface it as an info Notice.
        already_verified = selected_revision.state is not CalculationRevisionState.BORRADOR
        verification = verify_modelo_revision_with_preconditions(
            selected_revision.calculation_revision_id,
            actor=actor or deps.resolve_default_actor(),
            workflow_profile=workflow_profile,
        )
        report = verification.report
        report_payload = verification_report_payload(
            report,
            finding_preconditions=verification.finding_preconditions,
        )
        result = WorkVerifyResult.model_validate(report_payload.model_dump(mode="python"))
        lines = [
            "operation\tmodelo.work.verify",
            *verification_report_lines(
                report,
                finding_actions=tuple(finding.action for finding in report_payload.findings),
            ),
        ]
        notices = verification_report_notices(report)
        if already_verified:
            noop_message = tr(
                "cli.app.modelo.work.verify_idempotent_noop",
                calculation_revision_id=report.calculation_revision_id,
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
                ),
            )
            lines.append(noop_message)
        notices.extend(
            m184_socio_handoff_notices(get_calculation_revision(selected_revision.calculation_revision_id)),
        )
        _emit_envelope(ctx, command="modelo.work.verify", result=result, lines=lines, notices=notices)

        if not report.granted_verificado_completo:
            raise typer.Exit(code=1)


def _register_work_dependencies_command(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
) -> None:
    @work_app.command("dependencies", help=tr("cli.app.modelo.work.dependencies_help"))
    def work_dependencies(
        ctx: typer.Context,
        year: Annotated[
            int,
            typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
        ],
        modelo: _ModeloOpt = None,
        period: _PeriodOpt = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Show cross-period dependency inventory and clean-state blockers."""
        activate_output_language(ctx, output_language)
        require_active_profile()
        if period is not None and modelo is None:
            raise typer.BadParameter(tr("cli.app.modelo.work.dependencies_period_requires_modelo"))

        try:
            state = workflow_state_repository().load()
            workflow_profile = _filing_taxpayer_or_refuse(state)
            inventory = cross_period_dependency_inventory(
                resources().modelos.authority,
                filing_year=year,
                modelos=(modelo,) if modelo is not None else None,
            )
            clean_state = None
            if modelo is not None and period is not None:
                active_bucket_id = state.active_profile_bucket_id() or ""
                snapshot = resources().modelos.authority.snapshot(modelo, filing_year=year, period=period)
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
        _emit_envelope(
            ctx,
            command="modelo.work.dependencies",
            result=result,
            lines=_dependency_inventory_lines(result),
        )


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
            ),
        )
        for item in result.items
    )
    if result.clean_state is None:
        return lines
    lines.extend(
        [
            "clean_state",
            "target\t"
            f"{result.clean_state.target_modelo} "
            f"{result.clean_state.target_filing_year} "
            f"{result.clean_state.target_period.registry_token}",
            f"requires_clean_state\t{result.clean_state.requires_clean_state}",
            f"clean\t{result.clean_state.clean}",
            f"blockers\t{', '.join(result.clean_state.blockers)}",
            "source_modelo\tyear\tperiod\tclean\tblockers\tevidence_kind\tfiling_record_id",
        ],
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
            ),
        )
        for evidence in result.clean_state.dependencies
    )
    return lines


def _register_work_file_command(work_app: typer.Typer, *, deps: _VerificationDeps) -> None:
    @work_app.command("file", help=tr("cli.app.modelo.work.file_help"))
    def work_file(
        ctx: typer.Context,
        calculation_revision_id: _CalculationRevisionIdArg = None,
        modelo: _ModeloOpt = None,
        year: _YearOpt = None,
        period: _PeriodOpt = None,
        revision: _RevisionOpt = None,
        work_unit_id: _WorkUnitIdOpt = None,
        select: _RevisionSelectorOpt = ModeloCalculationRevisionSelector.CURRENT.value,
        bucket_id: _BucketIdOpt = None,
        actor: _ActorOpt = None,
        notes: Annotated[
            str | None,
            typer.Option("--notes", help=tr("cli.app.modelo.work.notes_help")),
        ] = None,
        refund_election: _RefundElectionOpt = RefundElection.COMPENSAR,
        payment_election: _PaymentElectionOpt = PaymentElection.INGRESO,
        prior_domiciliation_election: _PriorDomiciliationElectionOpt = PriorDomiciliationElection.KEEP,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Create an internal :class:`ModeloRecord` for a verified revision."""
        deps.activate_output_language(ctx, output_language)
        deps.require_active_profile()
        selected_revision = deps.resolve_revision_for_cli(
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
        # A revision already in PRESENTADO is the current filed answer, so the
        # file call is a guarded-idempotent no-op that returns the existing
        # record unchanged (no duplicate filing record or lifecycle event).
        # Capture that before the call to surface it as an info Notice.
        already_filed = selected_revision.state is CalculationRevisionState.PRESENTADO
        record = file_modelo_revision(
            selected_revision.calculation_revision_id,
            actor=actor or deps.resolve_default_actor(),
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
                "cli.app.modelo.work.file_idempotent_noop",
                calculation_revision_id=record.calculation_revision_id,
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
                ),
            )
            lines.append(noop_message)
        notices.extend(
            m184_socio_handoff_notices(get_calculation_revision(record.calculation_revision_id)),
        )
        _emit_envelope(ctx, command="modelo.work.file", result=result, lines=lines, notices=notices or None)


__all__ = ["register_work_verification_commands"]
