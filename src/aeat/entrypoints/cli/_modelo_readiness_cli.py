"""Typer registration for modelo readiness commands."""

from __future__ import annotations

from typing import Annotated

import typer

from ...application.state_projection import (
    ModeloReadinessRequest,
    build_operator_state_projection,
)
from ...core import Period
from ...core.i18n import tr
from ...domain.user_profile import ProfileNotFoundError
from ._common import _emit_envelope
from ._errors import CliRefusedBoundaryError
from ._modelo_payloads import (
    LedgerIssuePayload,
    ModeloReadinessMissingRequirementPayload,
    ModeloReadinessResult,
)


def register_readiness_commands(app: typer.Typer) -> None:
    """Register modelo readiness commands."""

    @app.command(
        "readiness",
        help=tr(
            "cli.app.modelo.readiness_help",
            default="Report whether the active profile is ready to file one modelo / year / period.",
        ),
    )
    def modelo_readiness(
        ctx: typer.Context,
        modelo: Annotated[
            str,
            typer.Option(
                "--modelo",
                help=tr("cli.app.modelo.readiness.modelo_help", default="Modelo code (e.g. 303)."),
            ),
        ],
        revision_id: Annotated[
            str,
            typer.Option(
                "--revision-id",
                help=tr("cli.app.modelo.readiness.revision_help", default="Registry revision id."),
            ),
        ],
        filing_year: Annotated[
            int,
            typer.Option("--year", help=tr("cli.app.modelo.readiness.year_help", default="Filing year.")),
        ],
        period: Annotated[
            str | None,
            typer.Option(
                "--period",
                help=tr(
                    "cli.app.modelo.readiness.period_help",
                    default=(
                        "Period token used to resolve the modelo revision: 0A annual, 1T-4T quarters, "
                        "01-12 months; for censo modelos (036) use alta, modificacion, or baja."
                    ),
                ),
            ),
        ] = None,
    ) -> None:
        """Report active-profile readiness for one modelo target."""
        request = ModeloReadinessRequest(
            modelo=modelo,
            revision_id=revision_id,
            filing_year=filing_year,
            period=(Period.from_year_and_code(filing_year, period) if period else None),
        )
        report = _readiness_report(request)
        readiness_result = _readiness_result(
            report,
            modelo=modelo,
            revision_id=revision_id,
            filing_year=filing_year,
        )
        _emit_envelope(
            ctx,
            command="modelo.readiness",
            result=readiness_result,
            lines=_readiness_lines(
                report,
                modelo=modelo,
                revision_id=revision_id,
                filing_year=filing_year,
                period=period,
            ),
        )


def _readiness_report(request: ModeloReadinessRequest):
    from ...core import resolve_active_bucket_id
    from ...core.i18n import tr as _tr

    if resolve_active_bucket_id() is None:
        raise CliRefusedBoundaryError(_tr("cli.config.errors.no_active_profile"))
    try:
        projection = build_operator_state_projection(modelo_readiness_requests=(request,))
    except ProfileNotFoundError as exc:
        raise CliRefusedBoundaryError(
            _tr("cli.config.profile.unknown_profile", name=resolve_active_bucket_id() or ""),
        ) from exc
    if not projection.modelo_readiness:
        raise CliRefusedBoundaryError(_tr("cli.config.errors.no_active_profile"))
    return projection.modelo_readiness[0]


def _readiness_result(
    report,
    *,
    modelo: str,
    revision_id: str,
    filing_year: int,
) -> ModeloReadinessResult:
    return ModeloReadinessResult(
        profile_id=str(report.profile_id),
        modelo=modelo,
        revision_id=revision_id,
        filing_year=filing_year,
        period=report.period,
        ready=report.ready,
        profile_ready=report.profile_ready,
        missing=[
            ModeloReadinessMissingRequirementPayload(
                section_key=req.section_key,
                field_key=req.field_key,
                selector=req.selector,
            )
            for req in report.missing
        ],
        ledger_preflight_required=report.ledger_preflight_required,
        ledger_ready=report.ledger_ready,
        ledger_period=report.ledger_period,
        ledger_checked_transaction_count=report.ledger_checked_transaction_count,
        ledger_issues=[
            LedgerIssuePayload(
                transaction_id=issue.transaction_id,
                reason=issue.reason.value,
                detail=issue.detail,
            )
            for issue in report.ledger_issues
        ],
    )


def _readiness_lines(
    report,
    *,
    modelo: str,
    revision_id: str,
    filing_year: int,
    period: str | None,
) -> list[str]:
    lines = [
        f"profile_id\t{report.profile_id}",
        f"modelo\t{modelo}",
        f"revision_id\t{revision_id}",
        f"filing_year\t{filing_year}",
        f"period\t{period or ''}",
        "readiness_scope\tprofile_and_source_preflight_not_manual_casilla_completeness",
        f"ready\t{report.ready}",
        f"profile_ready\t{report.profile_ready}",
        f"missing\t{len(report.missing)}",
        f"ledger_preflight_required\t{report.ledger_preflight_required}",
        f"ledger_ready\t{report.ledger_ready if report.ledger_ready is not None else ''}",
        f"ledger_period\t{report.ledger_period or ''}",
        f"ledger_checked\t{report.ledger_checked_transaction_count}",
        f"ledger_issues\t{len(report.ledger_issues)}",
        "finish_line\texport verified-complete revision via 'aeat app modelo export' (local finish line)",
    ]
    for requirement in report.missing:
        lines.append(f"{requirement.section_key}.{requirement.field_key}\t{requirement.selector}")
    for issue in report.ledger_issues:
        lines.append(f"ledger_issue\t{issue.transaction_id}\t{issue.reason.value}\t{issue.detail}")
    return lines


__all__ = ["register_readiness_commands"]
