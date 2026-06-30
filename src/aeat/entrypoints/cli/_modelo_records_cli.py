"""Typer registration for modelo filing-record and verification-report commands.

The filing-record commands render stored :class:`aeat.domain.modelos.ModeloRecord`
rows, import AEAT-attested external evidence through
:func:`aeat.application.modelo.import_external_filing_evidence`, and record
operator-supplied local observations for calculation prefill. Verification-report
commands expose persisted :class:`aeat.domain.modelos.VerificationReport` rows.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from typing import Annotated

import typer

from ...application.modelo import (
    ExternalEvidenceKind,
    ExternalModeloImportError,
    ModeloLocalObservationError,
    ModeloRecordNotFoundError,
    VerificationReportNotFoundError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    get_filing_record,
    get_verification_report,
    import_external_filing_evidence,
    list_filing_records,
    list_verification_reports,
    record_operator_local_observation,
)
from ...core import Period, PeriodError
from ...core.i18n import tr
from ...domain.calculations.registry import CasillaId
from ...domain.modelos import ModeloCode
from ...domain.modelos._errors import ModeloValidationError
from ._common import _emit_envelope, _profile_to_taxpayer
from ._modelo_payloads import (
    FilingRecordImportResult,
    FilingRecordLocalObservationResult,
    ModeloRecordListResult,
    ModeloRecordShowResult,
    VerificationReportListResult,
    VerificationReportShowResult,
)
from ._modelo_rendering import (
    advisory_notice,
    filing_record_lines,
    filing_record_payload,
    verification_report_lines,
    verification_report_payload,
)

_validate_work_unit_id: Callable[[str], str] | None = None
_parse_amendment_casilla: Callable[[str], tuple[CasillaId, Decimal]] | None = None
_resolve_default_actor: Callable[[], str] | None = None
_bad_parameter_from_error: Callable[[Exception], typer.BadParameter] | None = None


def register_record_commands(
    app: typer.Typer,
    *,
    validate_work_unit_id: Callable[[str], str],
    parse_amendment_casilla: Callable[[str], tuple[CasillaId, Decimal]],
    resolve_default_actor: Callable[[], str],
    bad_parameter_from_error: Callable[[Exception], typer.BadParameter],
) -> None:
    """Mount filing-record and verification-report command groups."""
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
    """Validate a filing-record command work-unit id."""
    if _validate_work_unit_id is None:
        raise RuntimeError("modelo record commands were not registered")
    return _validate_work_unit_id(raw)


def _casilla_value(spec: str) -> tuple[CasillaId, Decimal]:
    """Parse one ``--set`` casilla value through the modelo CLI parser."""
    if _parse_amendment_casilla is None:
        raise RuntimeError("modelo record commands were not registered")
    return _parse_amendment_casilla(spec)


def _actor() -> str:
    """Return the active-profile default actor for record commands."""
    if _resolve_default_actor is None:
        raise RuntimeError("modelo record commands were not registered")
    return _resolve_default_actor()


def _bad_from_error(exc: Exception) -> typer.BadParameter:
    """Adapt application exceptions into Typer parameter errors."""
    if _bad_parameter_from_error is None:
        raise RuntimeError("modelo record commands were not registered")
    return _bad_parameter_from_error(exc)


def _modelo_filter(raw: str | None) -> ModeloCode | None:
    if raw is None:
        return None
    return _modelo_code(raw)


def _modelo_code(raw: str) -> ModeloCode:
    try:
        return ModeloCode(raw)
    except ModeloValidationError as exc:
        raise _bad_from_error(exc) from exc


def _filing_period(year: int, token: str) -> Period:
    try:
        return Period.from_year_and_code(year, token)
    except PeriodError as exc:
        raise _bad_from_error(exc) from exc


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
    modelo: Annotated[
        str | None,
        typer.Option("--modelo", help=tr("cli.app.modelo.filing_record.modelo_help")),
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
    modelo_code = _modelo_filter(modelo)
    records = list_filing_records(bucket_id=bucket_id, modelo=modelo_code, include_superseded=include_superseded)
    result = ModeloRecordListResult(
        bucket_id_filter=bucket_id,
        modelo_filter=str(modelo_code) if modelo_code is not None else None,
        include_superseded=include_superseded,
        record_count=len(records),
        records=[filing_record_payload(record) for record in records],
    )
    lines = [
        "operation\tmodelo.filing_record.list",
        f"bucket_id_filter\t{bucket_id or ''}",
        f"modelo_filter\t{modelo_code or ''}",
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
                record.period.registry_token,
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
    """Import AEAT external evidence as a current :class:`aeat.domain.modelos.ModeloRecord`.

    The CLI validates :class:`ExternalEvidenceKind`, parses each ``--set`` value
    into a ``CasillaId`` decimal, resolves the active profile tax id, and
    delegates to :func:`aeat.application.modelo.import_external_filing_evidence`.
    The result is emitted as :class:`FilingRecordImportResult`; it is an
    AEAT-attested baseline for the amendment path, not a live submission from
    this application.
    """
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

    casilla_values: dict[CasillaId, Decimal] = {}
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


@filing_record_app.command(
    "observe-local",
    help="Record an operator-supplied local observation for calculation prefill.",
)
def filing_record_observe_local(
    ctx: typer.Context,
    modelo: Annotated[
        str,
        typer.Option("--modelo", help=tr("cli.app.modelo.work.modelo_help")),
    ],
    year: Annotated[
        int,
        typer.Option("--year", help=tr("cli.app.modelo.work.year_help")),
    ],
    period: Annotated[
        str,
        typer.Option("--period", help=tr("cli.app.modelo.work.period_help")),
    ],
    actor: Annotated[
        str | None,
        typer.Option("--by", help=tr("cli.app.modelo.work.actor_help")),
    ] = None,
    set_overrides: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help="Canonical casilla.id and Decimal value to record, e.g. --set 1391=0.",
        ),
    ] = None,
) -> None:
    """Persist local, non-official prior filing observations for calculations."""
    modelo_code = _modelo_code(modelo)
    filing_period = _filing_period(year, period)
    casilla_values: dict[CasillaId, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _casilla_value(spec)
        casilla_values[key] = value
    if not casilla_values:
        raise typer.BadParameter("observe-local requires at least one --set CASILLA=DECIMAL value")

    try:
        local_observation = record_operator_local_observation(
            modelo=str(modelo_code),
            filing_year=year,
            period=filing_period,
            casilla_values=casilla_values,
            actor=actor or _actor(),
        )
    except ModeloLocalObservationError as exc:
        raise _bad_from_error(exc) from exc

    result = FilingRecordLocalObservationResult(
        modelo=local_observation.modelo,
        filing_year=local_observation.filing_year,
        period=local_observation.period,
        revision_id=local_observation.revision_id,
        observation_key=local_observation.observation_key,
        source_kind=local_observation.source_kind,
        casilla_values={
            casilla_id: str(value) for casilla_id, value in sorted(local_observation.casilla_values.items())
        },
        casilla_count=len(local_observation.casilla_values),
        captured_at=local_observation.captured_at.isoformat(),
        captured_by=local_observation.captured_by,
        official_evidence=local_observation.official_evidence,
        filing_record_created=local_observation.filing_record_created,
        aeat_accepted=local_observation.aeat_accepted,
    )
    notice_message = (
        "Operator-supplied local observation recorded for calculation prefill only; "
        "it is not AEAT evidence and no filing record was created."
    )
    notice = advisory_notice(
        "modelo.filing_record.observe_local.non_official",
        notice_message,
        context={
            "source_kind": local_observation.source_kind,
            "official_evidence": "false",
            "filing_record_created": "false",
        },
    )
    lines = [
        "operation\tmodelo.filing_record.observe_local",
        f"modelo\t{local_observation.modelo}",
        f"filing_year\t{local_observation.filing_year}",
        f"period\t{local_observation.period.registry_token}",
        f"revision_id\t{local_observation.revision_id}",
        f"observation_key\t{local_observation.observation_key}",
        f"source_kind\t{local_observation.source_kind}",
        "official_evidence\tFalse",
        "filing_record_created\tFalse",
        "aeat_accepted\tFalse",
        f"captured_at\t{local_observation.captured_at.isoformat()}",
        f"captured_by\t{local_observation.captured_by}",
        "casilla_id\tvalue",
    ]
    lines.extend(
        f"{casilla_id}\t{value}" for casilla_id, value in sorted(local_observation.casilla_values.items())
    )
    lines.append(f"WARNING\t{notice_message}")
    _emit_envelope(
        ctx,
        command="modelo.filing_record.observe_local",
        result=result,
        lines=lines,
        notices=[notice],
    )


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
