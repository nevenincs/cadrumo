"""Typer registration for modelo filing-record and verification-report commands."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Annotated

import typer

from ...application.modelo import (
    ExternalEvidenceKind,
    ExternalModeloImportError,
    ModeloRecordNotFoundError,
    VerificationReportNotFoundError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    get_filing_record,
    get_verification_report,
    import_external_filing_evidence,
    list_filing_records,
    list_verification_reports,
)
from ...core.i18n import tr
from ._common import _emit_envelope, _profile_to_taxpayer
from ._modelo_payloads import (
    FilingRecordImportResult,
    ModeloRecordListResult,
    ModeloRecordShowResult,
    VerificationReportListResult,
    VerificationReportShowResult,
)
from ._modelo_rendering import (
    filing_record_lines,
    filing_record_payload,
    verification_report_lines,
    verification_report_payload,
)

_validate_work_unit_id: Callable[[str], str] | None = None
_parse_amendment_casilla: Callable[[str], tuple[str, Decimal]] | None = None
_resolve_default_actor: Callable[[], str] | None = None
_bad_parameter_from_error: Callable[[Exception], typer.BadParameter] | None = None


def register_record_commands(
    app: typer.Typer,
    *,
    validate_work_unit_id: Callable[[str], str],
    parse_amendment_casilla: Callable[[str], tuple[str, Decimal]],
    resolve_default_actor: Callable[[], str],
    bad_parameter_from_error: Callable[[Exception], typer.BadParameter],
) -> None:
    """Mount filing-record and verification-report commands on the modelo app."""
    global _validate_work_unit_id
    global _parse_amendment_casilla
    global _resolve_default_actor
    global _bad_parameter_from_error

    _validate_work_unit_id = validate_work_unit_id
    _parse_amendment_casilla = parse_amendment_casilla
    _resolve_default_actor = resolve_default_actor
    _bad_parameter_from_error = bad_parameter_from_error
    app.add_typer(filing_record_app, name="filing-record")
    app.add_typer(verification_report_app, name="verification-report")


def _work_unit_id(raw: str) -> str:
    if _validate_work_unit_id is None:
        raise RuntimeError("modelo record commands were not registered")
    return _validate_work_unit_id(raw)


def _casilla_value(spec: str) -> tuple[str, Decimal]:
    if _parse_amendment_casilla is None:
        raise RuntimeError("modelo record commands were not registered")
    return _parse_amendment_casilla(spec)


def _actor() -> str:
    if _resolve_default_actor is None:
        raise RuntimeError("modelo record commands were not registered")
    return _resolve_default_actor()


def _bad_from_error(exc: Exception) -> typer.BadParameter:
    if _bad_parameter_from_error is None:
        raise RuntimeError("modelo record commands were not registered")
    return _bad_parameter_from_error(exc)


filing_record_app = typer.Typer(
    name="filing-record",
    help=tr("cli.app.modelo.filing_record.app_help"),
    no_args_is_help=True,
    add_completion=False,
)

verification_report_app = typer.Typer(
    name="verification-report",
    help=tr("cli.app.modelo.verification_report.app_help"),
    no_args_is_help=True,
    add_completion=False,
)


@filing_record_app.command("list", help=tr("cli.app.modelo.filing_record.list_help"))
def filing_record_list(
    ctx: typer.Context,
    bucket_id: Annotated[
        str | None,
        typer.Option("--bucket-id", help=tr("cli.app.modelo.filing_record.bucket_id_help")),
    ] = None,
    include_superseded: Annotated[
        bool,
        typer.Option(
            "--include-superseded",
            help=tr("cli.app.modelo.filing_record.include_superseded_help"),
        ),
    ] = False,
) -> None:
    """List filing records."""
    records = list_filing_records(bucket_id=bucket_id, include_superseded=include_superseded)
    result = ModeloRecordListResult(
        bucket_id_filter=bucket_id,
        include_superseded=include_superseded,
        record_count=len(records),
        records=[filing_record_payload(record) for record in records],
    )
    lines = [
        "operation\tmodelo.filing_record.list",
        f"bucket_id_filter\t{bucket_id or ''}",
        f"include_superseded\t{include_superseded}",
        f"record_count\t{len(records)}",
        "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\tfiled_at\tfiled_by",
    ]
    lines.extend(
        "\t".join(
            (
                record.filing_record_id,
                record.bucket_id,
                str(record.modelo),
                str(record.filing_year),
                record.period,
                record.status.value,
                record.filed_at.isoformat(),
                record.filed_by,
            ),
        )
        for record in records
    )
    _emit_envelope(ctx, command="modelo.filing_record.list", result=result, lines=lines)


@filing_record_app.command("view", help=tr("cli.app.modelo.filing_record.view_help"))
def filing_record_show(
    ctx: typer.Context,
    filing_record_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.filing_record.filing_record_id_help")),
    ],
) -> None:
    """View one filing record by id."""
    try:
        record = get_filing_record(filing_record_id)
    except ModeloRecordNotFoundError as exc:
        raise _bad_from_error(exc) from exc

    result = ModeloRecordShowResult.model_validate(filing_record_payload(record).model_dump(mode="python"))
    lines = ["operation\tmodelo.filing_record.show", *filing_record_lines(record)]
    _emit_envelope(ctx, command="modelo.filing_record.view", result=result, lines=lines)


@filing_record_app.command("import", help=tr("cli.app.modelo.filing_record.import_help"))
def filing_record_import(
    ctx: typer.Context,
    work_unit_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.work.work_unit_id_help")),
    ],
    evidence_kind: Annotated[
        str,
        typer.Option(
            "--evidence-kind",
            help=tr("cli.app.modelo.filing_record.evidence_kind_help"),
        ),
    ],
    evidence_reference_id: Annotated[
        str,
        typer.Option(
            "--evidence-id",
            help=tr("cli.app.modelo.filing_record.evidence_reference_id_help"),
        ),
    ],
    actor: Annotated[
        str,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = "aeat-import",
    set_overrides: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help=tr("cli.app.modelo.filing_record.import_casilla_help"),
        ),
    ] = None,
) -> None:
    """Persist an externally-filed return as a baseline filing record."""
    validated_work_unit_id = _work_unit_id(work_unit_id)
    try:
        kind = ExternalEvidenceKind(evidence_kind)
    except ValueError as exc:
        canonical = ", ".join(repr(k.value) for k in ExternalEvidenceKind)
        raise typer.BadParameter(
            tr(
                "cli.app.modelo.filing_record.invalid_evidence_kind",
                canonical=canonical,
                kind=evidence_kind,
            ),
        ) from exc

    casilla_values: dict[str, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _casilla_value(spec)
        casilla_values[key] = value
    if not casilla_values:
        raise typer.BadParameter(tr("cli.app.modelo.filing_record.import_set_required"))

    try:
        from ...application.workflow import workflow_state_repository

        expected_tax_id = _profile_to_taxpayer(workflow_state_repository().load()).tax_id
        record = import_external_filing_evidence(
            work_unit_id=validated_work_unit_id,
            casilla_values=casilla_values,
            evidence_kind=kind,
            evidence_reference_id=evidence_reference_id,
            actor=actor or _actor(),
            expected_tax_id=expected_tax_id,
        )
    except (
        WorkUnitNotFoundError,
        WorkUnitMutationRefusedError,
        ExternalModeloImportError,
    ) as exc:
        raise _bad_from_error(exc) from exc

    result = FilingRecordImportResult.model_validate(
        {
            "evidence_kind": kind.value,
            "evidence_reference_id": evidence_reference_id,
            **filing_record_payload(record).model_dump(mode="python"),
        },
    )
    lines = [
        "operation\tmodelo.filing_record.import",
        f"evidence_kind\t{kind.value}",
        f"evidence_reference_id\t{evidence_reference_id}",
        *filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(imported AEAT-attested baseline)")
    _emit_envelope(ctx, command="modelo.filing_record.import", result=result, lines=lines)


@verification_report_app.command("list", help=tr("cli.app.modelo.verification_report.list_help"))
def verification_report_list(
    ctx: typer.Context,
    calculation_revision_id: Annotated[
        str | None,
        typer.Option(
            "--calculation-revision-id",
            help=tr("cli.app.modelo.work.calculation_revision_id_help"),
        ),
    ] = None,
) -> None:
    """List verification reports, optionally filtered to one revision."""
    reports = list_verification_reports(calculation_revision_id=calculation_revision_id)
    result = VerificationReportListResult(
        calculation_revision_id_filter=calculation_revision_id,
        report_count=len(reports),
        reports=[verification_report_payload(r) for r in reports],
    )
    lines = [
        "operation\tmodelo.verification_report.list",
        f"calculation_revision_id_filter\t{calculation_revision_id or ''}",
        f"report_count\t{len(reports)}",
        "verification_report_id\tcalculation_revision_id\tcompleteness_status\tgranted\trun_at\tverified_by",
    ]
    lines.extend(
        "\t".join(
            (
                r.verification_report_id,
                r.calculation_revision_id,
                r.completeness_status.value,
                str(r.granted_verificado_completo).lower(),
                r.run_at.isoformat(),
                r.verified_by,
            ),
        )
        for r in reports
    )
    _emit_envelope(ctx, command="modelo.verification_report.list", result=result, lines=lines)


@verification_report_app.command("view", help=tr("cli.app.modelo.verification_report.view_help"))
def verification_report_show(
    ctx: typer.Context,
    verification_report_id: Annotated[
        str,
        typer.Argument(help=tr("cli.app.modelo.verification_report.verification_report_id_help")),
    ],
) -> None:
    """View one verification report by id."""
    try:
        report = get_verification_report(verification_report_id)
    except VerificationReportNotFoundError as exc:
        raise _bad_from_error(exc) from exc

    result = VerificationReportShowResult.model_validate(verification_report_payload(report).model_dump(mode="python"))
    lines = ["operation\tmodelo.verification_report.show", *verification_report_lines(report)]
    _emit_envelope(ctx, command="modelo.verification_report.view", result=result, lines=lines)
