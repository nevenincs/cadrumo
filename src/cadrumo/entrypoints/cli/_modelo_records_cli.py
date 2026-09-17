"""Behavior handlers for modelo filing-record and verification-report commands.

The filing-record commands render stored :class:`ModeloRecord` rows, import
AEAT-attested external evidence through
:func:`import_external_filing_evidence`, and record
operator-supplied local observations for calculation prefill. Verification-report
commands expose persisted :class:`VerificationReport` rows.
"""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Literal

import typer

from ...application.modelo.action_errors import (
    ExternalModeloImportError,
    ModeloLocalObservationError,
    ModeloRecordNotFoundError,
    VerificationReportNotFoundError,
    WorkUnitMutationRefusedError,
    WorkUnitNotFoundError,
)
from ...application.modelo.external_import_actions import (
    ExternalFilingBaselineSource,
    ExternalFilingImportResult,
    import_external_filing_evidence,
    import_external_filing_source,
)
from ...application.modelo.filing_actions import (
    get_filing_record,
    get_verification_report,
    list_filing_records,
    list_verification_reports,
)
from ...application.modelo.local_observation_actions import (
    OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND,
    LocalObservationPorts,
    ModeloLocalObservationClearResult,
    ModeloLocalObservationResult,
    clear_operator_local_observation,
    record_operator_local_observation,
)
from ...application.modelo.local_observation_spreadsheet import (
    parse_casilla_lexical_spreadsheet,
    parse_casilla_value_spreadsheet,
)
from ...application.modelo.work_lifecycle import get_work_unit
from ...core.casilla_id import CasillaId, validated_casilla_id
from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.i18n.render import tr
from ...core.json_contract import Notice
from ...core.period import Period, PeriodError
from ...domain.modelos.codes import ModeloCode
from ...domain.modelos.errors import ModeloValidationError
from ...domain.modelos.filing_record import ExternalEvidenceKind, FilingDeclarationKind
from ._filing_chain_payloads import (
    ObservationLayersPayload,
    filing_reconciliation_lines,
    filing_reconciliation_notices,
    filing_reconciliation_payload,
    observation_layers_lines,
    observation_layers_payload,
)
from ._modelo_cli_support import (
    bad_parameter_from_error,
    parse_casilla_override,
    resolve_default_actor,
    validate_work_unit_id,
)
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
from .common import active_bucket_id_or_refuse, declared_tax_id, emit_envelope, notice_lines
from .state_projection_support import authority_operation, calculation_action_ports_factory, filing_action_ports_factory


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


def _actor() -> str:
    """Return the active-profile default actor for record commands."""
    return resolve_default_actor()


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


def _import_record(
    *,
    ctx: typer.Context,
    work_unit_id: str,
    casilla_values: dict[CasillaId, Decimal],
    evidence_kind: ExternalEvidenceKind,
    evidence_reference_id: str,
    declared_kind: FilingDeclarationKind | None,
    actor: str,
    file: Path | None,
) -> ExternalFilingImportResult:
    """Load profile identity and delegate one external-evidence import path."""
    try:
        from ...application.workflow.persistence import workflow_state_repository

        expected_tax_id = declared_tax_id(workflow_state_repository().load().active_profile_record())
        calculation_ports = calculation_action_ports_factory(ctx)(
            bucket_id=active_bucket_id_or_refuse(),
            operation=authority_operation(ctx),
        )
        work_unit = get_work_unit(work_unit_id, ports=calculation_ports.work_lifecycle_ports)
        calculation_ports = calculation_action_ports_factory(ctx)(
            bucket_id=work_unit.bucket_id,
            operation=authority_operation(ctx),
        )
        if file is not None:
            if declared_kind is not None:
                raise typer.BadParameter(tr("cli.app.modelo.filing_record.import_declared_kind_file_error"))
            return import_external_filing_source(
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
                work_lifecycle_ports=calculation_ports.work_lifecycle_ports,
                operation=authority_operation(ctx),
                observation_repository=calculation_ports.observation_repository,
            )
        return import_external_filing_evidence(
            work_unit_id=work_unit_id,
            casilla_values=casilla_values,
            evidence_kind=evidence_kind,
            evidence_reference_id=evidence_reference_id,
            declared_kind=declared_kind,
            actor=actor or _actor(),
            expected_tax_id=expected_tax_id,
            observation_repository=calculation_ports.observation_repository,
        )
    except WorkUnitMutationRefusedError:
        raise
    except (WorkUnitNotFoundError, ExternalModeloImportError, ModeloLocalObservationError) as exc:
        raise _bad_from_error(exc) from exc


def filing_record_list(
    ctx: typer.Context, bucket_id: str | None = None, modelo: str | None = None, include_superseded: bool = False
) -> None:
    """List filing records."""
    modelo_code = _modelo_filter(modelo)
    records = list_filing_records(
        ports=filing_action_ports_factory(ctx)(bucket_id=bucket_id or active_bucket_id_or_refuse()),
        bucket_id=bucket_id,
        modelo=modelo_code,
        include_superseded=include_superseded,
    )
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
                record.aeat_register.expediente_id if record.aeat_register is not None else "",
                record.filed_at.isoformat(),
                record.filed_by,
            )
        )
        for record in records
    )
    emit_envelope(ctx, command="modelo.filing_record.list", result=result, lines=lines)


def filing_record_show(ctx: typer.Context, filing_record_id: str) -> None:
    """View one filing record with both observation layers of its coordinate."""
    bucket_id = active_bucket_id_or_refuse()
    try:
        record = get_filing_record(
            filing_record_id,
            ports=filing_action_ports_factory(ctx)(bucket_id=bucket_id),
        )
    except ModeloRecordNotFoundError as exc:
        raise _bad_from_error(exc) from exc
    observation_repository = calculation_action_ports_factory(ctx)(
        bucket_id=record.bucket_id,
        operation=authority_operation(ctx),
    ).observation_repository
    layers = observation_layers_payload(
        observation_repository.load_observation_layers(
            str(record.modelo),
            record.period,
            member_nif=record.member_nif,
        ),
    )
    result = ModeloRecordShowResult.model_validate(
        {**filing_record_payload(record).model_dump(mode="python"), "observation_layers": layers},
    )
    lines = [
        "operation\tmodelo.filing_record.show",
        *filing_record_lines(record),
        *observation_layers_lines(layers),
    ]
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
    delegates to :func:`import_external_filing_evidence`, which decides how the
    AEAT entry joins the chain. ``--declared-kind`` states the declaration kind
    AEAT records, which a presentation after a confirmed declaration requires.
    The result is emitted as :class:`FilingRecordImportResult`: the in-force
    AEAT-attested entry and the reconciliation outcome, never a live submission
    from this application.
    """
    validated_work_unit_id = _work_unit_id(work_unit_id)
    casilla_values = _import_input_values(set_overrides, file)
    imported = _import_record(
        ctx=ctx,
        work_unit_id=validated_work_unit_id,
        casilla_values=casilla_values,
        evidence_kind=evidence_kind,
        evidence_reference_id=evidence_reference_id,
        declared_kind=declared_kind,
        actor=actor,
        file=file,
    )
    reconciliation = imported.reconciliation
    notices = filing_reconciliation_notices((reconciliation,))
    record = imported.filing_record
    # The payload derives the evidence kind and reference from the record's own
    # external evidence, so the in-force AEAT-backed record is the source passed.
    result = FilingRecordImportResult.model_validate(
        {
            **filing_record_payload(record).model_dump(mode="python"),
            "reconciliation": filing_reconciliation_payload(reconciliation),
        },
    )
    lines = [
        "operation\tmodelo.filing_record.import",
        f"evidence_kind\t{evidence_kind.value}",
        f"evidence_reference_id\t{evidence_reference_id}",
        *filing_record_lines(record),
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


def _local_observation_ports(ctx: typer.Context) -> LocalObservationPorts:
    bucket_id = active_bucket_id_or_refuse()
    ports = calculation_action_ports_factory(ctx)(bucket_id=bucket_id, operation=authority_operation(ctx))
    return LocalObservationPorts(
        bucket_id=bucket_id,
        observation_repository=ports.observation_repository,
        bucket_event_repository=ports.bucket_event_repository,
        work_unit_repository=ports.work_unit_repository,
    )


def _record_local_observation(
    *,
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: Period,
    casilla_values: dict[CasillaId, Decimal],
    actor: str,
    reason: str,
) -> tuple[ModeloLocalObservationResult, ObservationLayersPayload]:
    """Record the validated override and read the coordinate's layers back."""
    ports = _local_observation_ports(ctx)
    try:
        recorded = record_operator_local_observation(
            modelo=modelo,
            filing_year=year,
            period=period,
            casilla_values=casilla_values,
            actor=actor,
            reason=reason,
            ports=ports,
            operation=authority_operation(ctx),
        )
    except ModeloLocalObservationError as exc:
        raise _bad_from_error(exc) from exc
    return recorded, observation_layers_payload(ports.observation_repository.load_observation_layers(modelo, period))


def _clear_local_observation(
    *,
    ctx: typer.Context,
    modelo: str,
    year: int,
    period: Period,
    actor: str,
    reason: str,
) -> tuple[ModeloLocalObservationClearResult, ObservationLayersPayload]:
    """Clear the operator override and read the coordinate's layers back."""
    ports = _local_observation_ports(ctx)
    try:
        cleared = clear_operator_local_observation(
            modelo,
            year,
            period,
            reason=reason,
            actor=actor,
            ports=ports,
        )
    except ModeloLocalObservationError as exc:
        raise _bad_from_error(exc) from exc
    return cleared, observation_layers_payload(ports.observation_repository.load_observation_layers(modelo, period))


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
            "source_kind": OPERATOR_MANUAL_OBSERVATION_SOURCE_KIND.value,
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
    resolved_actor = actor or _actor()
    if clear:
        if file is not None or set_overrides:
            raise typer.BadParameter(tr("cli.app.modelo.filing_record.observe_local_clear_values_error"))
        cleared, layers = _clear_local_observation(
            ctx=ctx,
            modelo=str(modelo_code),
            year=year,
            period=filing_period,
            actor=resolved_actor,
            reason=reason,
        )
        result = FilingRecordLocalObservationResult(
            action="cleared",
            modelo=cleared.modelo,
            filing_year=cleared.filing_year,
            period=cleared.period,
            observation_key=cleared.observation_key,
            captured_at=cleared.cleared_at,
            captured_by=cleared.cleared_by,
            reason=cleared.reason,
            observation_layers=layers,
        )
        _emit_local_observation(ctx, result=result, notice=_observe_local_notice("cleared"))
        return
    casilla_values = _local_observation_values(file, set_overrides)
    recorded, layers = _record_local_observation(
        ctx=ctx,
        modelo=str(modelo_code),
        year=year,
        period=filing_period,
        casilla_values=casilla_values,
        actor=resolved_actor,
        reason=reason,
    )
    result = FilingRecordLocalObservationResult(
        action="recorded",
        modelo=recorded.modelo,
        filing_year=recorded.filing_year,
        period=recorded.period,
        revision_id=recorded.revision_id,
        observation_key=recorded.observation_key,
        source_kind=recorded.source_kind,
        casilla_values={casilla_id: str(value) for casilla_id, value in sorted(recorded.casilla_values.items())},
        casilla_count=len(recorded.casilla_values),
        captured_at=recorded.captured_at,
        captured_by=recorded.captured_by,
        reason=recorded.override.reason,
        observation_layers=layers,
    )
    _emit_local_observation(ctx, result=result, notice=_observe_local_notice("recorded"))


def verification_report_list(ctx: typer.Context, calculation_revision_id: str | None = None) -> None:
    """List persisted verification reports, optionally scoped to one revision.

    Each row is a persisted :class:`VerificationReport` projected through
    :class:`VerificationReportListResult` and nested
    :class:`VerificationReportPayload`,
    preserving the same findings surface as ``aeat app modelo work verify``.
    """
    reports = list_verification_reports(
        ports=filing_action_ports_factory(ctx)(bucket_id=active_bucket_id_or_refuse()),
        calculation_revision_id=calculation_revision_id,
        operation=authority_operation(ctx),
    )
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
    emit_envelope(ctx, command="modelo.verification_report.list", result=result, lines=lines)


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
        report = get_verification_report(
            verification_report_id,
            ports=filing_action_ports_factory(ctx)(bucket_id=active_bucket_id_or_refuse()),
            operation=authority_operation(ctx),
        )
    except VerificationReportNotFoundError as exc:
        raise _bad_from_error(exc) from exc
    result = VerificationReportShowResult.model_validate(verification_report_payload(report).model_dump(mode="python"))
    lines = ["operation\tmodelo.verification_report.show", *verification_report_lines(report)]
    emit_envelope(ctx, command="modelo.verification_report.view", result=result, lines=lines)
