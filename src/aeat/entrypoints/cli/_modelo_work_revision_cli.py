"""Typer registration for modelo work calculation revision read commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Any

import typer

from ...application.modelo import (
    CalculationRevisionNotFoundError,
    ModeloCalculationRevisionSelector,
    list_calculation_revisions,
    modelo_202_modality_for_work_unit,
    resolve_modelo_work_unit_for_operator_target,
)
from ...core.external_constants import OutputLanguage
from ...core.i18n import tr
from ._common import _emit_envelope
from ._modelo_cli_support import OutputLanguageOpt
from ._modelo_payloads import WorkRevisionResult, WorkRevisionsResult
from ._modelo_rendering import (
    calculation_revision_lines,
    calculation_revision_payload,
    short_id,
)


def register_work_revision_commands(
    work_app: typer.Typer,
    *,
    activate_output_language: Callable[[typer.Context, OutputLanguage | None], None],
    require_active_profile: Callable[[], None],
    resolve_work_unit_for_cli: Callable[..., Any],
    resolve_revision_for_cli: Callable[..., Any],
    bad_parameter_from_error: Callable[[BaseException], typer.BadParameter],
    selector_bad_parameter: Callable[[BaseException], typer.BadParameter],
) -> None:
    """Register read-only calculation revision commands."""

    @work_app.command("revisions", help=tr("cli.app.modelo.work.revisions_help"))
    def work_revisions(
        ctx: typer.Context,
        work_unit_id: Annotated[
            str | None,
            typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
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
        bucket_id: Annotated[
            str | None,
            typer.Option("--bucket-id", help=tr("cli.app.modelo.work.bucket_id_help")),
        ] = None,
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """List calculation revisions, optionally filtered to one work unit."""
        activate_output_language(ctx, output_language)
        require_active_profile()
        resolved_work_unit_id = work_unit_id
        if work_unit_id is not None or modelo is not None or year is not None or period is not None:
            unit = resolve_work_unit_for_cli(
                work_unit_id=work_unit_id,
                modelo=modelo,
                year=year,
                period=period,
                revision=revision,
                bucket_id=bucket_id,
            )
            resolved_work_unit_id = unit.work_unit_id
        revisions = list_calculation_revisions(work_unit_id=resolved_work_unit_id)

        result = WorkRevisionsResult.model_validate(
            {
                "work_unit_id_filter": resolved_work_unit_id,
                "revision_count": len(revisions),
                "revisions": [calculation_revision_payload(rev) for rev in revisions],
            }
        )
        lines = [
            "operation\tmodelo.work.revisions",
            f"work_unit_id_filter\t{resolved_work_unit_id or ''}",
            f"revision_count\t{len(revisions)}",
            "short_calculation_revision_id\tcalculation_revision_id\tshort_work_unit_id\twork_unit_id\tstate\tcreated_at",
        ]
        lines.extend(
            "\t".join(
                (
                    short_id(rev.calculation_revision_id) or "",
                    rev.calculation_revision_id,
                    short_id(rev.work_unit_id) or "",
                    rev.work_unit_id,
                    rev.state.value,
                    rev.created_at.isoformat(),
                )
            )
            for rev in revisions
        )
        _emit_envelope(ctx, command="modelo.work.revisions", result=result, lines=lines)

    @work_app.command("revision", help=tr("cli.app.modelo.work.revision_show_help"))
    def work_revision(
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
        registry_revision: Annotated[
            str | None,
            typer.Option("--registry-revision", help=tr("cli.app.modelo.work.revision_help")),
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
        output_language: OutputLanguageOpt = None,
    ) -> None:
        """Show one stored calculation revision's persisted casilla values."""
        activate_output_language(ctx, output_language)
        require_active_profile()
        try:
            selected_revision = resolve_revision_for_cli(
                calculation_revision_id=calculation_revision_id,
                work_unit_id=work_unit_id,
                modelo=modelo,
                year=year,
                period=period,
                registry_revision=registry_revision,
                bucket_id=bucket_id,
                selector=select,
            )
        except CalculationRevisionNotFoundError as exc:
            if calculation_revision_id is not None:
                raise bad_parameter_from_error(exc) from exc
            raise selector_bad_parameter(exc) from exc

        modality_payload: dict[str, object] = {}
        modality_lines: list[str] = []
        unit_for_modality = resolve_modelo_work_unit_for_operator_target(work_unit_id=selected_revision.work_unit_id)
        modality_summary = modelo_202_modality_for_work_unit(unit_for_modality)
        if modality_summary is not None:
            modality_payload = {
                "modality": modality_summary.modality,
                "modality_reason": modality_summary.reason,
            }
            modality_lines = [f"modality\t{modality_summary.modality}"]

        result = WorkRevisionResult.model_validate(
            {
                **calculation_revision_payload(selected_revision).model_dump(mode="python"),
                **modality_payload,
            }
        )
        lines = [
            "operation\tmodelo.work.revision",
            *calculation_revision_lines(selected_revision),
            *modality_lines,
        ]
        _emit_envelope(ctx, command="modelo.work.revision", result=result, lines=lines)


__all__ = ["register_work_revision_commands"]
