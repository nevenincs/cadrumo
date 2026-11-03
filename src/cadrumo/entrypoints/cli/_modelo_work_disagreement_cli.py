"""Behavior for the commands that accept, revoke and list disputed Modelo figures.

A calculation that finds two sources stating different values for one figure
withholds checking, export and filing, and names each disagreement by a finding
id. These commands let the operator accept the value the calculation used, by
that id and with a stated reason, take the acceptance back, or list what a
declaration holds. An acceptance changes no figure and lasts only while the
sources keep stating the amounts it was made against.
"""

from __future__ import annotations

import typer
from pydantic import ValidationError

from cadrumo_client.commands.output import activate_subcommand_output_language

from ...application.modelo.credit_resolution_contracts import (
    CreditResolutionAcceptRequest,
    CreditResolutionListRequest,
    CreditResolutionRevokeRequest,
)
from ...application.modelo.selectors import ModeloCalculationRevisionSelector
from ...core.external_constants import OutputLanguage
from ...core.i18n.render import output_language as active_output_language
from ...core.i18n.render import tr
from ._modelo_work_disagreement_payloads import (
    DisagreementResolutionPayload,
    WorkAcceptDisagreementResult,
    WorkDisagreementsResult,
    WorkRevokeDisagreementResult,
)
from .common import bad, emit_envelope
from .operation_modelo_credit_resolution import (
    accept_credit_resolution,
    list_credit_resolutions,
    resolution_payload,
    revoke_credit_resolution_for_cli,
)
from .operation_modelo_verification import select_modelo_work_revision_for_cli

__all__ = ["work_accept_disagreement", "work_disagreements", "work_revoke_disagreement"]


def _line(resolution: DisagreementResolutionPayload) -> str:
    amounts = "; ".join(f"{source.role}={source.value}" for source in resolution.sources)
    return (
        f"{resolution.finding_id}\t{resolution.key}\t{resolution.state}\t{amounts}\t"
        f"accepted={resolution.accepted_role}\tapplies={resolution.applies}\trevision={resolution.revision_id}"
    )


def _select(
    ctx: typer.Context,
    *,
    calculation_revision_id: str | None,
    work_unit_id: str | None,
    modelo: str | None,
    year: int | None,
    period: str | None,
    revision: str | None,
    bucket_id: str | None,
):
    return select_modelo_work_revision_for_cli(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
        selector=ModeloCalculationRevisionSelector.CURRENT,
        default_for=None,
    )


def work_accept_disagreement(
    ctx: typer.Context,
    finding_id: str,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    work_unit_id: str | None = None,
    bucket_id: str | None = None,
    reason: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Accept the value a calculation used for one disagreement of its sources, by the finding id."""
    activate_subcommand_output_language(ctx, output_language)
    stated = (reason or "").strip()
    if not stated:
        raise typer.BadParameter(tr("cli.app.modelo.work.accept_disagreement_reason_required"))
    client, selected = _select(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    try:
        request = CreditResolutionAcceptRequest(
            profile_id=client.profile_id,
            calculation_revision_id=selected.calculation_revision_id,
            output_language=OutputLanguage(active_output_language()),
            finding_id=finding_id.strip().lower(),
            reason=stated,
        )
    except ValidationError:
        raise bad(tr("cli.app.modelo.work.disagreement_invalid_input")) from None
    resolution = accept_credit_resolution(client, work_unit_id=selected.unit.work_unit_id, request=request)
    result = WorkAcceptDisagreementResult(
        bucket_id=str(client.profile_id),
        calculation_revision_id=selected.calculation_revision_id,
        resolution=resolution_payload(resolution),
    )
    emit_envelope(
        ctx,
        command="modelo.work.accept_disagreement",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", _line(result.resolution)),
    )


def work_revoke_disagreement(
    ctx: typer.Context,
    finding_id: str,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    work_unit_id: str | None = None,
    bucket_id: str | None = None,
    expected_revision: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """Take back the acceptance of one disagreement, guarded by the revision it is stored at."""
    activate_subcommand_output_language(ctx, output_language)
    if expected_revision is None or not expected_revision.strip():
        raise typer.BadParameter(tr("cli.app.modelo.work.revoke_disagreement_revision_required"))
    client, selected = _select(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    try:
        request = CreditResolutionRevokeRequest(
            profile_id=client.profile_id,
            calculation_revision_id=selected.calculation_revision_id,
            output_language=OutputLanguage(active_output_language()),
            finding_id=finding_id.strip().lower(),
            expected_revision_id=expected_revision.strip(),
        )
    except ValidationError:
        raise bad(tr("cli.app.modelo.work.disagreement_invalid_input")) from None
    resolution = revoke_credit_resolution_for_cli(client, work_unit_id=selected.unit.work_unit_id, request=request)
    result = WorkRevokeDisagreementResult(
        bucket_id=str(client.profile_id),
        calculation_revision_id=selected.calculation_revision_id,
        resolution=resolution_payload(resolution),
    )
    emit_envelope(
        ctx,
        command="modelo.work.revoke_disagreement",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", _line(result.resolution)),
    )


def work_disagreements(
    ctx: typer.Context,
    calculation_revision_id: str | None = None,
    modelo: str | None = None,
    year: int | None = None,
    period: str | None = None,
    revision: str | None = None,
    work_unit_id: str | None = None,
    bucket_id: str | None = None,
    output_language: OutputLanguage | None = None,
) -> None:
    """List every acceptance a declaration holds, active and revoked, with the revision each is stored at."""
    activate_subcommand_output_language(ctx, output_language)
    client, selected = _select(
        ctx,
        calculation_revision_id=calculation_revision_id,
        work_unit_id=work_unit_id,
        modelo=modelo,
        year=year,
        period=period,
        revision=revision,
        bucket_id=bucket_id,
    )
    rows = list_credit_resolutions(
        client,
        work_unit_id=selected.unit.work_unit_id,
        request=CreditResolutionListRequest(
            profile_id=client.profile_id,
            calculation_revision_id=selected.calculation_revision_id,
            output_language=OutputLanguage(active_output_language()),
        ),
    )
    result = WorkDisagreementsResult(
        bucket_id=str(client.profile_id),
        calculation_revision_id=selected.calculation_revision_id,
        resolutions=[resolution_payload(row) for row in rows],
        count=len(rows),
    )
    emit_envelope(
        ctx,
        command="modelo.work.disagreements",
        result=result,
        lines=(f"bucket\t{result.bucket_id}", f"count\t{result.count}", *(_line(row) for row in result.resolutions)),
    )
