"""Typer registration for modelo filing-record and verification-report commands.

The filing-record commands render stored :class:`ModeloRecord` rows, import
AEAT-attested external evidence through
:func:`import_external_filing_evidence`, and record
operator-supplied local observations for calculation prefill. Verification-report
commands expose persisted :class:`VerificationReport` rows.
"""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal
from pathlib import Path

import typer

from ...application.modelo import (
    ExternalFilingBaselineSource,
    ExternalModeloImportError,
    ModeloLocalObservationError,
    ModeloRecordNotFoundError,
    VerificationReportNotFoundError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
    get_filing_record,
    get_verification_report,
    get_work_unit,
    import_external_filing_evidence,
    import_external_filing_source,
    list_filing_records,
    list_verification_reports,
    parse_casilla_lexical_spreadsheet,
    parse_casilla_value_spreadsheet,
    record_operator_local_observation,
)
from ...core import CasillaId, Period, PeriodError, validated_casilla_id
from ...core.i18n import tr
from ...domain.modelos import ExternalEvidenceKind, ModeloCode, ModeloValidationError
from ._common import _declared_tax_id, _emit_envelope
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
from ._modelo_work_options import _ActorOpt

_validate_work_unit_id: Callable[[str], str] | None = None
_parse_amendment_casilla: Callable[[str], tuple[CasillaId, Decimal]] | None = None
_resolve_default_actor: Callable[[], str] | None = None
_bad_parameter_from_error: Callable[[Exception], typer.BadParameter] | None = None


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


def filing_record_list(
    ctx: typer.Context, bucket_id: str | None = None, modelo: str | None = None, include_superseded: bool = False
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
                )
            )
            for record in records

    )
    _emit_envelope(ctx, command="modelo.filing_record.list", result=result, lines=lines)


def filing_record_show(ctx: typer.Context, filing_record_id: str) -> None:
    """View one filing record by id."""
    try:
        record = get_filing_record(filing_record_id)
    except ModeloRecordNotFoundError as exc:
        raise _bad_from_error(exc) from exc
    result = ModeloRecordShowResult.model_validate(filing_record_payload(record).model_dump(mode="python"))
    lines = ["operation\tmodelo.filing_record.show", *filing_record_lines(record)]
    _emit_envelope(ctx, command="modelo.filing_record.view", result=result, lines=lines)


def filing_record_import(
    ctx: typer.Context,
    work_unit_id: str,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    actor: str = "aeat-import",
    set_overrides: list[str] | None = None,
    file: Path | None = None,
) -> None:
    """Import AEAT external evidence as a current :class:`ModeloRecord`.

    Typer validates :class:`ExternalEvidenceKind` at the boundary, the CLI parses
    each ``--set`` value
    into a :class:`CasillaId` decimal, resolves the active profile tax id, and
    delegates to :func:`import_external_filing_evidence`.
    The result is emitted as :class:`FilingRecordImportResult`; it is an
    AEAT-attested baseline for the amendment path, not a live submission from
    this application.
    """
    validated_work_unit_id = _work_unit_id(work_unit_id)
    if file is not None and set_overrides:
        raise typer.BadParameter("filing-record import accepts either --file or --set, not both")
    casilla_values: dict[CasillaId, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _casilla_value(spec)
        casilla_values[key] = value
    if not casilla_values and file is None:
        raise typer.BadParameter(tr("cli.app.modelo.filing_record.import_set_required"))
    try:
        from ...application.workflow import workflow_state_repository

        expected_tax_id = _declared_tax_id(workflow_state_repository().load().active_profile_record())
        if file is not None:
            work_unit = get_work_unit(validated_work_unit_id)
            record = import_external_filing_source(
                ExternalFilingBaselineSource(
                    modelo=str(work_unit.modelo),
                    filing_year=work_unit.filing_year,
                    period=work_unit.period,
                    registry_revision_id=work_unit.revision_id,
                    evidence_kind=evidence_kind,
                    evidence_reference_id=evidence_reference_id,
                    tax_id=expected_tax_id or "",
                    casilla_lexicals=parse_casilla_lexical_spreadsheet(file),
                ),
                bucket_id=work_unit.bucket_id,
                actor=actor or _actor(),
            )
        else:
            record = import_external_filing_evidence(
                work_unit_id=validated_work_unit_id,
                casilla_values=casilla_values,
                evidence_kind=evidence_kind,
                evidence_reference_id=evidence_reference_id,
                actor=actor or _actor(),
                expected_tax_id=expected_tax_id,
            )
    except WorkUnitMutationRefusedError:
        raise
    except (WorkUnitNotFoundError, ExternalModeloImportError, ModeloLocalObservationError) as exc:
        raise _bad_from_error(exc) from exc
    result = FilingRecordImportResult.model_validate(
        {
            "evidence_kind": evidence_kind,
            "evidence_reference_id": evidence_reference_id,
            **filing_record_payload(record).model_dump(mode="python"),
        }
    )
    lines = [
        "operation\tmodelo.filing_record.import",
        f"evidence_kind\t{evidence_kind.value}",
        f"evidence_reference_id\t{evidence_reference_id}",
        *filing_record_lines(record),
    ]
    lines.append("filing_disambiguation\t(imported AEAT-attested baseline)")
    _emit_envelope(ctx, command="modelo.filing_record.import", result=result, lines=lines)


def filing_record_observe_local(
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: str,
    actor: _ActorOpt = None,
    set_overrides: list[str] | None = None,
    file: Path | None = None,
    replace_official_evidence: bool = False,
) -> None:
    """Record non-official local observations for later calculation prefill.

    The command parses canonical :class:`CasillaId` decimal values from
    ``--set`` flags and/or a ``--file`` spreadsheet (CSV or XLSX,
    ``casilla_code,value`` columns), delegates to
    :func:`record_operator_local_observation`, and emits
    :class:`FilingRecordLocalObservationResult` plus an advisory
    :class:`Notice`. It deliberately creates no
    :class:`ModeloRecord` and supplies no official AEAT
    evidence for filing-grade clean-state checks — the local reconstruction
    stays non-official regardless of transport (``--set`` or ``--file``).
    """
    modelo_code = _modelo_code(modelo)
    filing_period = _filing_period(year, period)
    casilla_values: dict[CasillaId, Decimal] = {}
    if file is not None:
        try:
            spreadsheet_values = parse_casilla_value_spreadsheet(file)
        except ModeloLocalObservationError as exc:
            raise _bad_from_error(exc) from exc
        for raw_code, value in spreadsheet_values.items():
            try:
                casilla_id = validated_casilla_id(raw_code, surface="--file casilla_code column")
            except ValueError as exc:
                raise typer.BadParameter(f"--file row casilla_code {raw_code!r} is not a valid CasillaId") from exc
            casilla_values[casilla_id] = value
    for spec in set_overrides or ():
        key, value = _casilla_value(spec)
        casilla_values[key] = value
    if not casilla_values:
        raise typer.BadParameter(
            "observe-local requires at least one --set CASILLA=DECIMAL value or a --file spreadsheet"
        )
    try:
        local_observation = record_operator_local_observation(
            modelo=str(modelo_code),
            filing_year=year,
            period=filing_period,
            casilla_values=casilla_values,
            actor=actor or _actor(),
            replace_official_evidence=replace_official_evidence,
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
        captured_at=local_observation.captured_at,
        captured_by=local_observation.captured_by,
    )
    notice_message = "Operator-supplied local observation recorded for calculation prefill only; it is not AEAT evidence and no filing record was created."
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
    lines.extend((f"{casilla_id}\t{value}" for casilla_id, value in sorted(local_observation.casilla_values.items())))
    lines.append(f"WARNING\t{notice_message}")
    _emit_envelope(ctx, command="modelo.filing_record.observe_local", result=result, lines=lines, notices=[notice])


def verification_report_list(ctx: typer.Context, calculation_revision_id: str | None = None) -> None:
    """List persisted verification reports, optionally scoped to one revision.

    Each row is a persisted :class:`VerificationReport` projected through
    :class:`VerificationReportListResult` and nested
    :class:`VerificationReportPayload`,
    preserving the same findings surface as ``aeat app modelo work verify``.
    """
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
                )
            )
            for r in reports

    )
    _emit_envelope(ctx, command="modelo.verification_report.list", result=result, lines=lines)


def verification_report_show(ctx: typer.Context, verification_report_id: str) -> None:
    """View one persisted verification report by id.

    The command validates the shared
    :class:`VerificationReportPayload`
    into
    :class:`VerificationReportShowResult`,
    so saved report views retain the legal/source-reference
    :class:`FindingPayload` detail emitted
    by ``aeat app modelo work verify``.
    """
    try:
        report = get_verification_report(verification_report_id)
    except VerificationReportNotFoundError as exc:
        raise _bad_from_error(exc) from exc
    result = VerificationReportShowResult.model_validate(verification_report_payload(report).model_dump(mode="python"))
    lines = ["operation\tmodelo.verification_report.show", *verification_report_lines(report)]
    _emit_envelope(ctx, command="modelo.verification_report.view", result=result, lines=lines)
