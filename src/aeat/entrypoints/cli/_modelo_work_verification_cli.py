"""Typer registration for modelo work verify and file commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

import typer

from ...application.calculations import (
    CalculationObservationRepository,
    CrossPeriodExpectedMemberSet,
    cross_period_dependency_inventory,
    evaluate_cross_period_clean_state,
)
from ...application.modelo import (
    CalculationRevisionNotFoundError,
    CalculationRevisionStateError,
    ModeloCalculationRevisionSelector,
    ModeloVerifySelector,
    WorkUnitNotFoundError,
    file_modelo_revision,
    verify_modelo_revision,
)
from ...application.workflow import workflow_state_repository
from ...core import Period
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ...core.resources import resources
from ...domain.calculations.registry import RegistrySnapshotError
from ...domain.modelos._calculation_repository import CalculationRevisionCatalogueRepository
from ...domain.modelos._filing_repository import ModeloRecordCatalogueRepository
from ...domain.modelos._verification_repository import VerificationReportCatalogueRepository
from ._common import _emit_envelope, _profile_to_taxpayer
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
    verification_report_lines,
    verification_report_payload,
)


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
    calculation_revision_not_found_bad_parameter: Callable[[str, BaseException], typer.BadParameter],
) -> None:
    """Register state-changing revision verification commands."""
    _register_work_verify_command(
        work_app,
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        resolve_revision_for_cli=resolve_revision_for_cli,
        resolve_default_actor=resolve_default_actor,
        bad_parameter_from_error=bad_parameter_from_error,
        calculation_revision_not_found_bad_parameter=calculation_revision_not_found_bad_parameter,
    )
    _register_work_dependencies_command(
        work_app,
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        bad_parameter_from_error=bad_parameter_from_error,
    )
    _register_work_file_command(
        work_app,
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        resolve_revision_for_cli=resolve_revision_for_cli,
        resolve_default_actor=resolve_default_actor,
        bad_parameter_from_error=bad_parameter_from_error,
        calculation_revision_not_found_bad_parameter=calculation_revision_not_found_bad_parameter,
    )


# KWARGS-ANY-RATIONALE-CLI-DI-RESOLVERS: resolve_revision_for_cli is an injected
# resolver callable whose concrete return type varies by call site;
# Callable[..., Any] is the DI composition seam.
def _register_work_verify_command(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    resolve_revision_for_cli: Callable[..., Any],
    resolve_default_actor: Callable[[], str],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
    calculation_revision_not_found_bad_parameter: Callable[[str, BaseException], typer.BadParameter],
) -> None:
    @work_app.command("verify", help=tr("cli.app.modelo.work.verify_help"))
    def work_verify(
        ctx: typer.Context,
        calculation_revision_id: Annotated[
            str | None,
            typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help")),
        ] = None,
        modelo: Annotated[
            str | None,
            typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
        ] = None,
        year: Annotated[
            int | None,
            typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
        ] = None,
        period: Annotated[
            str | None,
            typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
        ] = None,
        revision: Annotated[
            str | None,
            typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help")),
        ] = None,
        work_unit_id: Annotated[
            str | None,
            typer.Option("--work-unit-id", help=tr("cli.app.modelo.work.work_unit_id_help")),
        ] = None,
        select: Annotated[
            ModeloVerifySelector,
            typer.Option(
                "--select",
                help=tr("cli.app.modelo.work.verify_selector_help", default="Draft revision selector."),
            ),
        ] = ModeloVerifySelector.CURRENT,
        bucket_id: Annotated[
            str | None,
            typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
        ] = None,
        actor: Annotated[
            str | None,
            typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
        ] = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Verify a draft calculation revision against the verified-complete contract."""
        activate_output_language(ctx, output_language)
        require_active_profile()
        try:
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
            workflow_profile = _profile_to_taxpayer(workflow_state_repository().load())
            report = verify_modelo_revision(
                selected_revision.calculation_revision_id,
                actor=actor or resolve_default_actor(),
                workflow_profile=workflow_profile,
            )
        except CalculationRevisionNotFoundError as exc:
            if calculation_revision_id is not None:
                raise calculation_revision_not_found_bad_parameter(calculation_revision_id, exc) from exc
            raise bad_parameter_from_error(exc) from exc
        except (
            CalculationRevisionStateError,
            WorkUnitNotFoundError,
        ) as exc:
            raise bad_parameter_from_error(exc) from exc

        result = WorkVerifyResult.model_validate(verification_report_payload(report).model_dump(mode="python"))
        lines = ["operation\tmodelo.work.verify", *verification_report_lines(report)]
        _emit_envelope(ctx, command="modelo.work.verify", result=result, lines=lines)

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
        modelo: Annotated[
            str | None,
            typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
        ] = None,
        period: Annotated[
            str | None,
            typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
        ] = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Show registry cross-period dependencies and current clean-state blockers."""
        activate_output_language(ctx, output_language)
        require_active_profile()
        if period is not None and modelo is None:
            raise typer.BadParameter("--period requires --modelo")

        try:
            state = workflow_state_repository().load()
            workflow_profile = _profile_to_taxpayer(state)
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
            period=Period.from_year_and_code(roster.filing_year, roster.period),
            member_nifs=roster.member_nifs,
        )
        for roster in getattr(profile, "cross_period_group_member_rosters", ())
    )


def _dependency_inventory_item_payload(item: object) -> CrossPeriodDependencyInventoryItemPayload:
    return CrossPeriodDependencyInventoryItemPayload(
        target_modelo=item.target_modelo,
        target_revision_id=item.target_revision_id,
        target_filing_year=item.target_filing_year,
        target_period=item.target_period.registry_token,
        dependency_count=len(item.dependencies),
        source_modelos=item.source_modelos,
        dependencies=tuple(
            CrossPeriodDependencyRequirementPayload(
                source_modelo=requirement.source_modelo,
                filing_year=requirement.filing_year,
                period=requirement.period.registry_token,
                source_casillas=requirement.source_casillas,
                origin=requirement.origin.value,
                origin_ids=requirement.origin_ids,
                requires_member_fan_in=requirement.requires_member_fan_in,
            )
            for requirement in item.dependencies
        ),
    )


def _clean_state_payload(verdict: object) -> CrossPeriodCleanStatePayload:
    return CrossPeriodCleanStatePayload(
        target_modelo=verdict.target_modelo,
        target_filing_year=verdict.target_filing_year,
        target_period=verdict.target_period.registry_token,
        requires_clean_state=verdict.requires_clean_state,
        clean=verdict.clean,
        blockers=tuple(blocker.value for blocker in verdict.blockers),
        dependencies=tuple(
            CrossPeriodDependencyEvidencePayload(
                source_modelo=evidence.requirement.source_modelo,
                filing_year=evidence.requirement.filing_year,
                period=evidence.requirement.period.registry_token,
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
                item.target_period,
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
            f"{result.clean_state.target_period}",
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
                evidence.period,
                str(evidence.clean),
                ", ".join(evidence.blockers),
                evidence.external_evidence_kind or "",
                evidence.filing_record_id or "",
            ),
        )
        for evidence in result.clean_state.dependencies
    )
    return lines


# KWARGS-ANY-RATIONALE-CLI-DI-RESOLVERS: resolve_revision_for_cli is an injected
# resolver callable whose concrete return type varies by call site;
# Callable[..., Any] is the DI composition seam.
def _register_work_file_command(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    resolve_revision_for_cli: Callable[..., Any],
    resolve_default_actor: Callable[[], str],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
    calculation_revision_not_found_bad_parameter: Callable[[str, BaseException], typer.BadParameter],
) -> None:
    @work_app.command("file", help=tr("cli.app.modelo.work.file_help"))
    def work_file(
        ctx: typer.Context,
        calculation_revision_id: Annotated[
            str | None,
            typer.Argument(help=tr("cli.app.modelo.work.calculation_revision_id_help")),
        ] = None,
        modelo: Annotated[
            str | None,
            typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
        ] = None,
        year: Annotated[
            int | None,
            typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
        ] = None,
        period: Annotated[
            str | None,
            typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
        ] = None,
        revision: Annotated[
            str | None,
            typer.Option("--revision", help=tr("cli.app.modelo.work.revision_help")),
        ] = None,
        work_unit_id: Annotated[
            str | None,
            typer.Option("--work-unit-id", help=tr("cli.app.modelo.work.work_unit_id_help")),
        ] = None,
        select: Annotated[
            str,
            typer.Option(
                "--select",
                help=tr("cli.app.modelo.work.revision_selector_help", default="Revision selector."),
            ),
        ] = ModeloCalculationRevisionSelector.CURRENT.value,
        bucket_id: Annotated[
            str | None,
            typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
        ] = None,
        actor: Annotated[
            str | None,
            typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
        ] = None,
        notes: Annotated[
            str | None,
            typer.Option("--notes", help=tr("cli.app.modelo.work.notes_help")),
        ] = None,
        output_language: OutputLanguage | None = typer.Option(
            None,
            "--output-language",
            "--language",
            help=tr("cli.config.auth.output_language_help"),
        ),
    ) -> None:
        """Mark a verified modelo revision as internally filed. Does NOT submit to AEAT."""
        activate_output_language(ctx, output_language)
        require_active_profile()
        try:
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
            workflow_profile = _profile_to_taxpayer(workflow_state_repository().load())
            record = file_modelo_revision(
                selected_revision.calculation_revision_id,
                actor=actor or resolve_default_actor(),
                workflow_profile=workflow_profile,
                notes=notes,
            )
        except CalculationRevisionNotFoundError as exc:
            if calculation_revision_id is not None:
                raise calculation_revision_not_found_bad_parameter(calculation_revision_id, exc) from exc
            raise bad_parameter_from_error(exc) from exc
        except (
            CalculationRevisionStateError,
            WorkUnitNotFoundError,
        ) as exc:
            raise bad_parameter_from_error(exc) from exc

        result = WorkFileResult.model_validate(filing_record_payload(record).model_dump(mode="python"))
        lines = ["operation\tmodelo.work.file", *filing_record_lines(record)]
        lines.append("filing_disambiguation\t(internal only — does not submit to AEAT)")
        _emit_envelope(ctx, command="modelo.work.file", result=result, lines=lines)


__all__ = ["register_work_verification_commands"]
