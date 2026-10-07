"""Behavior handlers for modelo filing-record and verification-report commands.

The filing-record and verification-report commands render results returned by
the profile-bound operation worker. Imports and local observations enter the
same worker before changing private application state.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

import typer

from ...application.calculations.observations_repository import ObservationSourceKind
from ...application.modelo.action_errors import (
    ModeloLocalObservationError,
)
from ...application.modelo.local_observation_spreadsheet import (
    parse_casilla_value_spreadsheet,
)
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.i18n.render import tr
from ...core.json_contract import Notice
from ...core.period import Period, PeriodError
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind
from ._filing_chain_payloads import (
    filing_reconciliation_lines,
    filing_reconciliation_notices,
    observation_layers_lines,
)
from ._modelo_cli_support import (
    bad_parameter_from_error,
    parse_casilla_override,
    validate_work_unit_id,
)
from ._modelo_payloads import (
    FilingRecordLocalObservationResult,
    ModeloRecordListResult,
    ModeloRecordShowResult,
)
from ._modelo_rendering import (
    advisory_notice,
    filing_record_lines,
)
from .common import emit_envelope, notice_lines
from .runtime_modelo_filing_record_import import import_modelo_filing_record
from .runtime_modelo_filing_record_list import read_modelo_filing_record_list
from .runtime_modelo_filing_record_view import read_modelo_filing_record_view
from .runtime_modelo_local_observation import clear_modelo_local_observation, record_modelo_local_observation
from .runtime_modelo_verification_report_read import (
    read_modelo_verification_report_list,
    read_modelo_verification_report_view,
)


def _work_unit_id(raw: str) -> str:
    """Validate a filing-record command work-unit id."""
    return validate_work_unit_id(raw)


def _casilla_value(spec: str) -> tuple[CasillaId, Decimal]:
    """Parse one ``--set`` casilla value through the modelo CLI parser."""
    key, raw_value = parse_casilla_override(spec)
    value = try_parse_canonical_decimal(raw_value, max_fraction_digits=2)
    if value is None:
        raise typer.BadParameter(tr("cli.app.modelo.work.set_not_decimal", value=raw_value))
    return validated_casilla_id(str(key), surface="--set casilla"), value


def _bad_from_error(exc: Exception) -> typer.BadParameter:
    """Adapt application exceptions into Typer parameter errors."""
    return bad_parameter_from_error(exc)


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


def _import_input_values(
    set_overrides: list[str] | None,
    file: Path | None,
) -> dict[CasillaId, Decimal]:
    """Validate the import transport choice and parse any ``--set`` values."""
    if file is not None and set_overrides:
        raise typer.BadParameter("filing-record import accepts either --file or --set, not both")
    casilla_values: dict[CasillaId, Decimal] = {}
    for spec in set_overrides or ():
        key, value = _casilla_value(spec)
        casilla_values[key] = value
    if not casilla_values and file is None:
        raise typer.BadParameter(tr("cli.app.modelo.filing_record.import_set_required"))
    return casilla_values


def filing_record_list(
    ctx: typer.Context, bucket_id: str | None = None, modelo: str | None = None, include_superseded: bool = False
) -> None:
    """List filing records."""
    modelo_code = _modelo_filter(modelo)
    records = read_modelo_filing_record_list(
        ctx,
        bucket_id=bucket_id,
        modelo=modelo_code,
        include_superseded=include_superseded,
    )
    result = ModeloRecordListResult(
        bucket_id_filter=bucket_id,
        modelo_filter=str(modelo_code) if modelo_code is not None else None,
        include_superseded=include_superseded,
        record_count=len(records),
        records=list(records),
    )
    lines = [
        "operation\tmodelo.filing_record.list",
        f"bucket_id_filter\t{bucket_id or ''}",
        f"modelo_filter\t{modelo_code or ''}",
        f"include_superseded\t{include_superseded}",
        f"record_count\t{len(records)}",
        "filing_record_id\tbucket_id\tmodelo\tyear\tperiod\tstatus\torigin\tconfirmation\t"
        "declaration_kind\tamends_filing_record_id\taeat_expediente_id\tfiled_at\tfiled_by",
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
                record.origin.value,
                record.confirmation.value,
                record.declaration_kind.value,
                record.amends_filing_record_id or "",
                (record.aeat_register.expediente_id or "") if record.aeat_register is not None else "",
                record.filed_at.isoformat(),
                record.filed_by,
            )
        )
        for record in records
    )
    emit_envelope(ctx, command="modelo.filing_record.list", result=result, lines=lines)


def filing_record_show(ctx: typer.Context, filing_record_id: str) -> None:
    """View one filing record with both observation layers of its coordinate."""
    record, layers, historical = read_modelo_filing_record_view(ctx, filing_record_id=filing_record_id)
    result = ModeloRecordShowResult.model_validate(
        {**record.model_dump(mode="python"), "observation_layers": layers, "historical_content": historical},
    )
    lines = [
        "operation\tmodelo.filing_record.show",
        *filing_record_lines(record),
        *observation_layers_lines(layers),
        f"historical_content\t{historical.availability}",
        f"historical_calculation_revision_id\t{historical.calculation_revision_id}",
    ]
    lines.extend(f"historical_value\t{row.casilla_id}\t{row.value}" for row in historical.observations)
    emit_envelope(ctx, command="modelo.filing_record.view", result=result, lines=lines)


def filing_record_import(
    ctx: typer.Context,
    work_unit_id: str,
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    actor: str = "aeat-import",
    set_overrides: list[str] | None = None,
    file: Path | None = None,
    declared_kind: FilingDeclarationKind | None = None,
) -> None:
    """Reconcile AEAT external evidence with the period's filing chain.

    Typer validates :class:`ExternalEvidenceKind` at the boundary, the CLI parses
    each ``--set`` value
    into a :class:`CasillaId` decimal, resolves the active profile tax id, and
    delegates to the profile-bound import operation, which decides how the
    AEAT entry joins the chain. ``--declared-kind`` states the declaration kind
    AEAT records, which a presentation after a confirmed declaration requires.
    The result is emitted as :class:`FilingRecordImportResult`: the in-force
    AEAT-attested entry and the reconciliation outcome, never a live submission
    from this application.
    """
    validated_work_unit_id = _work_unit_id(work_unit_id)
    casilla_values = _import_input_values(set_overrides, file)
    result = import_modelo_filing_record(
        ctx,
        work_unit_id=validated_work_unit_id,
        casilla_values=casilla_values if file is None else None,
        evidence_kind=evidence_kind,
        evidence_reference_id=evidence_reference_id,
        declared_kind=declared_kind,
        actor=actor,
        source_file=file,
    )
    reconciliation = result.reconciliation
    notices = filing_reconciliation_notices((reconciliation,))
    lines = [
        "operation\tmodelo.filing_record.import",
        f"evidence_kind\t{evidence_kind.value}",
        f"evidence_reference_id\t{evidence_reference_id}",
        *filing_record_lines(result),
        *filing_reconciliation_lines((reconciliation,)),
        *notice_lines(notices),
    ]
    lines.append("filing_disambiguation\t(imported AEAT-attested baseline)")
    emit_envelope(ctx, command="modelo.filing_record.import", result=result, lines=lines, notices=notices)


def _local_observation_values(
    file: Path | None,
    set_overrides: list[str] | None,
) -> dict[CasillaId, Decimal]:
    """Parse spreadsheet values first, then apply later ``--set`` overrides."""
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
    return casilla_values


def _observe_local_notice(action: Literal["recorded", "cleared"]) -> Notice:
    message = (
        tr("cli.app.modelo.filing_record.observe_local_recorded_notice")
        if action == "recorded"
        else tr("cli.app.modelo.filing_record.observe_local_cleared_notice")
    )
    return advisory_notice(
        "modelo.filing_record.observe_local.non_official"
        if action == "recorded"
        else "modelo.filing_record.observe_local.cleared",
        message,
        context={
            "source_kind": ObservationSourceKind.OPERATOR_MANUAL.value,
            "official_evidence": "false",
            "filing_record_created": "false",
        },
    )


def _emit_local_observation(
    ctx: typer.Context,
    *,
    result: FilingRecordLocalObservationResult,
    notice: Notice,
) -> None:
    lines = [
        "operation\tmodelo.filing_record.observe_local",
        f"action\t{result.action}",
        f"modelo\t{result.modelo}",
        f"filing_year\t{result.filing_year}",
        f"period\t{result.period.registry_token}",
        f"revision_id\t{result.revision_id or ''}",
        f"observation_key\t{result.observation_key}",
        f"source_kind\t{result.source_kind.value if result.source_kind is not None else ''}",
        "official_evidence\tFalse",
        "filing_record_created\tFalse",
        "aeat_accepted\tFalse",
        f"captured_at\t{result.captured_at.isoformat()}",
        f"captured_by\t{result.captured_by}",
        f"reason\t{result.reason}",
        "casilla_id\tvalue",
        *(f"{casilla_id}\t{value}" for casilla_id, value in result.casilla_values.items()),
        *observation_layers_lines(result.observation_layers),
        *notice_lines((notice,)),
    ]
    emit_envelope(ctx, command="modelo.filing_record.observe_local", result=result, lines=lines, notices=[notice])


def filing_record_observe_local(
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: str,
    reason: str,
    actor: str | None = None,
    set_overrides: list[str] | None = None,
    file: Path | None = None,
    clear: bool = False,
) -> None:
    """Record or clear an operator override of a period's observation.

    Recording parses canonical :class:`CasillaId` decimal values from ``--set``
    flags and/or a ``--file`` spreadsheet (CSV or XLSX, ``casilla_code,value``
    columns) and stores them, with the operator and ``--reason``, as the
    pending-local layer above any official AEAT observation. ``--clear``
    removes that override so readers see the official layer again. Neither
    mode creates a :class:`ModeloRecord` or supplies official AEAT evidence.
    """
    modelo_code = _modelo_code(modelo)
    filing_period = _filing_period(year, period)
    if clear:
        if file is not None or set_overrides:
            raise typer.BadParameter(tr("cli.app.modelo.filing_record.observe_local_clear_values_error"))
        result = clear_modelo_local_observation(
            ctx,
            modelo=str(modelo_code),
            period=filing_period,
            actor=actor,
            reason=reason,
        )
        _emit_local_observation(ctx, result=result, notice=_observe_local_notice("cleared"))
        return
    casilla_values = _local_observation_values(file, set_overrides)
    result = record_modelo_local_observation(
        ctx,
        modelo=str(modelo_code),
        period=filing_period,
        casilla_values=casilla_values,
        actor=actor,
        reason=reason,
    )
    _emit_local_observation(ctx, result=result, notice=_observe_local_notice("recorded"))


def verification_report_list(ctx: typer.Context, calculation_revision_id: str | None = None) -> None:
    """List persisted verification reports through the profile-bound worker."""
    result, lines = read_modelo_verification_report_list(ctx, calculation_revision_id=calculation_revision_id)
    emit_envelope(ctx, command="modelo.verification_report.list", result=result, lines=lines)


def verification_report_show(ctx: typer.Context, verification_report_id: str) -> None:
    """View one persisted verification report through the profile-bound worker."""
    result, lines = read_modelo_verification_report_view(ctx, verification_report_id=verification_report_id)
    emit_envelope(ctx, command="modelo.verification_report.view", result=result, lines=lines)
