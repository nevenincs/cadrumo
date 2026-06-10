"""Typer registration for modelo work verify and file commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

import typer

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
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ._common import _emit_envelope, _profile_to_taxpayer
from ._modelo_payloads import WorkFileResult, WorkVerifyResult
from ._modelo_rendering import (
    filing_record_lines,
    filing_record_payload,
    verification_report_lines,
    verification_report_payload,
)


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
    _register_work_file_command(
        work_app,
        activate_output_language=activate_output_language,
        require_active_profile=require_active_profile,
        resolve_revision_for_cli=resolve_revision_for_cli,
        resolve_default_actor=resolve_default_actor,
        bad_parameter_from_error=bad_parameter_from_error,
        calculation_revision_not_found_bad_parameter=calculation_revision_not_found_bad_parameter,
    )


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
