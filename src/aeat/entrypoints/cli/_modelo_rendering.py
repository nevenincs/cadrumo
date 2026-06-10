"""Rendering helpers shared by modelo CLI command groups."""

from __future__ import annotations

from ...application.modelo import calculation_result_summary, modelo_work_plazo_summary
from ...core.i18n import tr
from ...core.json_contract import Notice, NoticeSeverity
from ._modelo_payloads import (
    CalculationRevisionPayload,
    ExternalEvidencePayload,
    FindingPayload,
    ModeloRecordPayload,
    ObservationPayload,
    ResultSummaryRowPayload,
    VerificationReportPayload,
    WorkUnitPayload,
)


def advisory_notice(
    code: str,
    message: str,
    *,
    suggestion: str | None = None,
    context: dict[str, str] | None = None,
) -> Notice:
    """Project a non-blocking modelo advisory message onto the envelope notices channel.

    The single projection point that turns an incidental, non-blocking
    modelo diagnostic (source-resolution advisory, unauthorized-backend
    advisory, filing-obligation advisory) into a warning-severity
    :class:`Notice`. Command groups call this instead of re-modelling the
    advisory as a bespoke ``*_advisory`` payload field, so every advisory
    flows through the one uniform notices surface. ``context`` carries any
    structured provenance the former bespoke payload exposed (e.g. the
    source-resolution ``reason`` / ``source_kind``).
    """
    return Notice(
        severity=NoticeSeverity.WARNING,
        code=code,
        message=message,
        suggestion=suggestion,
        context=context,
    )


def short_id(value: str | None) -> str | None:
    """Return the display suffix for a content-addressed id."""
    return value[-12:] if value else None


def work_unit_payload(unit) -> WorkUnitPayload:
    return WorkUnitPayload(
        work_unit_id=unit.work_unit_id,
        short_work_unit_id=short_id(unit.work_unit_id) or "",
        bucket_id=unit.bucket_id,
        modelo=str(unit.modelo),
        filing_year=unit.filing_year,
        period=unit.period,
        revision_id=unit.revision_id,
        name=unit.name,
        state=unit.state.value,
        current_calculation_revision_id=unit.current_calculation_revision_id,
        short_current_calculation_revision_id=short_id(unit.current_calculation_revision_id),
        filed_calculation_revision_id=unit.filed_calculation_revision_id,
        short_filed_calculation_revision_id=short_id(unit.filed_calculation_revision_id),
        current_filing_record_id=unit.current_filing_record_id,
        created_at=unit.created_at.isoformat(),
        updated_at=unit.updated_at.isoformat(),
        discarded_at=unit.discarded_at.isoformat() if unit.discarded_at else None,
        discarded_by=unit.discarded_by,
        discard_reason=unit.discard_reason,
        causante_ccaa=unit.causante_ccaa.value if unit.causante_ccaa is not None else None,
    )


def work_unit_lines(unit) -> list[str]:
    lines = [
        f"work_unit_id\t{unit.work_unit_id}",
        f"short_work_unit_id\t{short_id(unit.work_unit_id) or ''}",
        f"bucket_id\t{unit.bucket_id}",
        f"modelo\t{unit.modelo}",
        f"filing_year\t{unit.filing_year}",
        f"period\t{unit.period}",
        f"revision_id\t{unit.revision_id}",
        f"name\t{unit.name}",
        f"state\t{unit.state.value}",
        f"current_calculation_revision_id\t{unit.current_calculation_revision_id or ''}",
        f"short_current_calculation_revision_id\t{short_id(unit.current_calculation_revision_id) or ''}",
        f"filed_calculation_revision_id\t{unit.filed_calculation_revision_id or ''}",
        f"short_filed_calculation_revision_id\t{short_id(unit.filed_calculation_revision_id) or ''}",
        f"current_filing_record_id\t{unit.current_filing_record_id or ''}",
        f"created_at\t{unit.created_at.isoformat()}",
        f"updated_at\t{unit.updated_at.isoformat()}",
    ]
    if unit.discarded_at is not None:
        lines.append(f"discarded_at\t{unit.discarded_at.isoformat()}")
    if unit.discarded_by is not None:
        lines.append(f"discarded_by\t{unit.discarded_by}")
    if unit.discard_reason is not None:
        lines.append(f"discard_reason\t{unit.discard_reason}")
    if unit.causante_ccaa is not None:
        lines.append(f"causante_ccaa\t{unit.causante_ccaa.value}")
    lines.extend(work_unit_plazo_lines(unit))
    return lines


def work_unit_list_lines(units, *, bucket_id: str | None, include_discarded: bool) -> list[str]:
    lines = [
        "operation\tmodelo.work.list",
        f"bucket_id_filter\t{bucket_id or ''}",
        f"include_discarded\t{include_discarded}",
        f"work_unit_count\t{len(units)}",
        "short_work_unit_id\twork_unit_id\tbucket_id\tmodelo\tyear\tperiod\trevision_id\tstate\tcurrent_revision\tfiled_revision\tname",
    ]
    lines.extend(
        "\t".join(
            (
                short_id(unit.work_unit_id) or "",
                unit.work_unit_id,
                unit.bucket_id,
                str(unit.modelo),
                str(unit.filing_year),
                unit.period,
                unit.revision_id,
                unit.state.value,
                short_id(unit.current_calculation_revision_id) or "",
                short_id(unit.filed_calculation_revision_id) or "",
                unit.name,
            )
        )
        for unit in units
    )
    return lines


def work_unit_plazo_lines(unit) -> list[str]:
    """Render plazo voluntario and extemporaneidad lines for the work unit."""
    summary = modelo_work_plazo_summary(unit)
    if summary is None:
        return []

    out: list[str] = [f"plazo_closes_on\t{summary.closes_on.isoformat()}"]
    if summary.days_remaining is not None:
        out.append(
            tr(
                "cli.app.modelo.work.plazo_days_remaining",
                default="days_remaining\t{days_remaining}",
                days_remaining=summary.days_remaining,
            )
        )
        return out

    if summary.days_overdue is None:
        return out

    out.append(f"days_overdue\t{summary.days_overdue}")
    if summary.recargo is None:
        out.append(
            tr(
                "cli.app.modelo.work.plazo_vencido_warning",
                default=(
                    "AVISO: plazo voluntario vencido. Presenta con recargo "
                    "Art. 27 LGT antes de recibir requerimiento de la AEAT."
                ),
            )
        )
        return out

    out.extend(
        [
            f"recargo_band\t{summary.recargo.band_id}",
            f"recargo_pct\t{summary.recargo.surcharge_pct}",
            f"recargo_interest_applies\t{summary.recargo.interest_applies}",
            f"recargo_legal_ref\t{summary.recargo.legal_ref}",
            tr(
                "cli.app.modelo.work.plazo_vencido_warning",
                default=(
                    "AVISO: plazo voluntario vencido. Presenta con recargo "
                    "Art. 27 LGT antes de recibir requerimiento de la AEAT."
                ),
            ),
        ]
    )
    return out


def calculation_revision_payload(rev) -> CalculationRevisionPayload:
    observations = tuple(
        ObservationPayload(
            casilla_id=obs.casilla_id,
            value=str(obs.value),
            formula_id=obs.formula_id,
            operand_refs=tuple(obs.operand_refs),
            operand_values=tuple(str(v) for v in obs.operand_values),
            legal_refs=tuple(obs.legal_refs),
            source_refs=tuple(obs.source_refs),
        )
        for obs in rev.observations
    )
    return CalculationRevisionPayload(
        calculation_revision_id=rev.calculation_revision_id,
        work_unit_id=rev.work_unit_id,
        state=rev.state.value,
        casilla_values={k: str(v) for k, v in rev.casilla_values.items()},
        observations=observations,
        result_summary=result_summary_payload(rev),
        binding_overrides={key: str(value) for key, value in rev.binding_overrides.items()},
        inputs_snapshot=dict(rev.inputs_snapshot),
        created_at=rev.created_at.isoformat(),
        updated_at=rev.updated_at.isoformat(),
        verified_at=rev.verified_at.isoformat() if rev.verified_at else None,
        verified_by=rev.verified_by,
        filed_at=rev.filed_at.isoformat() if rev.filed_at else None,
        filed_by=rev.filed_by,
        superseded_at=rev.superseded_at.isoformat() if rev.superseded_at else None,
    )


def result_summary_lines(rev) -> list[str]:
    """Return the headline-result summary block for a calculation revision."""
    summary = calculation_result_summary(rev)
    if summary is None or not summary.rows:
        return []
    header = tr(
        "cli.app.modelo.work.result_summary_header",
        default="result summary  %{modelo} %{year} %{period}",
        modelo=summary.modelo,
        year=summary.filing_year,
        period=summary.period,
    )
    lines = [header, "role\tcasilla\tvalue\tlabel"]
    for row in summary.rows:
        lines.append(f"{row.role}\t{row.casilla_id}\t{row.value}\t{row.label}")
    return lines


def result_summary_payload(rev) -> tuple[ResultSummaryRowPayload, ...]:
    """Return a tuple of :class:`ResultSummaryRowPayload` headline-result summary rows for the JSON payload."""
    summary = calculation_result_summary(rev)
    if summary is None:
        return ()
    return tuple(
        ResultSummaryRowPayload(
            role=row.role,
            casilla_id=row.casilla_id,
            value=str(row.value),
            label=row.label,
        )
        for row in summary.rows
    )


def calculation_revision_lines(rev) -> list[str]:
    lines = [
        f"calculation_revision_id\t{rev.calculation_revision_id}",
        f"work_unit_id\t{rev.work_unit_id}",
        f"state\t{rev.state.value}",
        f"created_at\t{rev.created_at.isoformat()}",
        f"updated_at\t{rev.updated_at.isoformat()}",
    ]
    if rev.verified_at is not None:
        lines.append(f"verified_at\t{rev.verified_at.isoformat()}")
        lines.append(f"verified_by\t{rev.verified_by}")
    if rev.filed_at is not None:
        lines.append(f"filed_at\t{rev.filed_at.isoformat()}")
        lines.append(f"filed_by\t{rev.filed_by}")
    if rev.superseded_at is not None:
        lines.append(f"superseded_at\t{rev.superseded_at.isoformat()}")
    summary_lines = result_summary_lines(rev)
    if summary_lines:
        lines.extend(summary_lines)
    for casilla, value in sorted(rev.casilla_values.items()):
        lines.append(f"casilla\t{casilla}\t{value}")
    for index, detail_row in enumerate(rev.detail_rows, start=1):
        fields = detail_row.model_dump(mode="json", exclude={"row_type"})
        field_str = " ".join(f"{key}={value}" for key, value in fields.items())
        lines.append(f"detail_row\t{index}\t{detail_row.row_type}\t{field_str}")
    return lines


def filing_record_payload(record) -> ModeloRecordPayload:
    external_evidence: ExternalEvidencePayload | None = None
    if record.external_evidence is not None:
        external_evidence = ExternalEvidencePayload(
            kind=record.external_evidence.kind.value,
            reference_id=record.external_evidence.reference_id,
            imported_at=record.external_evidence.imported_at.isoformat(),
        )
    return ModeloRecordPayload(
        filing_record_id=record.filing_record_id,
        work_unit_id=record.work_unit_id,
        calculation_revision_id=record.calculation_revision_id,
        bucket_id=record.bucket_id,
        modelo=str(record.modelo),
        filing_year=record.filing_year,
        period=record.period,
        filed_at=record.filed_at.isoformat(),
        filed_by=record.filed_by,
        notes=record.notes,
        aeat_accepted=record.aeat_accepted,
        status=record.status.value,
        superseded_at=record.superseded_at.isoformat() if record.superseded_at else None,
        superseded_by_filing_record_id=record.superseded_by_filing_record_id,
        external_evidence=external_evidence,
        amends_filing_record_id=record.amends_filing_record_id,
        kind="internal_filing",
        live_submission=False,
    )


def filing_record_lines(record) -> list[str]:
    lines = [
        f"filing_record_id\t{record.filing_record_id}",
        f"work_unit_id\t{record.work_unit_id}",
        f"calculation_revision_id\t{record.calculation_revision_id}",
        f"bucket_id\t{record.bucket_id}",
        f"modelo\t{record.modelo}",
        f"filing_year\t{record.filing_year}",
        f"period\t{record.period}",
        f"filed_at\t{record.filed_at.isoformat()}",
        f"filed_by\t{record.filed_by}",
        f"status\t{record.status.value}",
        f"aeat_accepted\t{str(record.aeat_accepted).lower()}",
    ]
    if record.notes is not None:
        lines.append(f"notes\t{record.notes}")
    if record.superseded_at is not None:
        lines.append(f"superseded_at\t{record.superseded_at.isoformat()}")
    if record.superseded_by_filing_record_id is not None:
        lines.append(f"superseded_by_filing_record_id\t{record.superseded_by_filing_record_id}")
    if record.external_evidence is not None:
        lines.append(f"external_evidence.kind\t{record.external_evidence.kind.value}")
        lines.append(f"external_evidence.reference_id\t{record.external_evidence.reference_id}")
        lines.append(f"external_evidence.imported_at\t{record.external_evidence.imported_at.isoformat()}")
    if record.amends_filing_record_id is not None:
        lines.append(f"amends_filing_record_id\t{record.amends_filing_record_id}")
    lines.append("kind\tinternal_filing")
    lines.append("live_submission\tfalse")
    return lines


def verification_report_payload(report) -> VerificationReportPayload:
    return VerificationReportPayload(
        verification_report_id=report.verification_report_id,
        calculation_revision_id=report.calculation_revision_id,
        completeness_status=report.completeness_status.value,
        granted_verificado_completo=report.granted_verificado_completo,
        resolved_casillas=list(report.resolved_casillas),
        missing_required_casillas=list(report.missing_required_casillas),
        run_at=report.run_at.isoformat(),
        verified_by=report.verified_by,
        findings=[
            FindingPayload(
                kind=f.kind.value,
                severity=f.severity.value,
                casilla_id=f.casilla_id,
                expectation_id=f.expectation_id,
                message=f.message,
                next_action=f.next_action,
                legal_refs=list(f.legal_refs),
                source_refs=list(f.source_refs),
            )
            for f in report.findings
        ],
    )


def verification_report_lines(report) -> list[str]:
    lines = [
        f"verification_report_id\t{report.verification_report_id}",
        f"calculation_revision_id\t{report.calculation_revision_id}",
        f"completeness_status\t{report.completeness_status.value}",
        f"granted_verificado_completo\t{str(report.granted_verificado_completo).lower()}",
        f"run_at\t{report.run_at.isoformat()}",
        f"verified_by\t{report.verified_by}",
        f"resolved_casilla_count\t{len(report.resolved_casillas)}",
        f"missing_required_casilla_count\t{len(report.missing_required_casillas)}",
        f"finding_count\t{len(report.findings)}",
    ]
    for casilla in report.missing_required_casillas:
        lines.append(f"missing_casilla\t{casilla}")
    for finding in report.findings:
        next_action = finding.next_action or ""
        casilla = finding.casilla_id or ""
        lines.append(
            "\t".join(
                (
                    "finding",
                    finding.kind.value,
                    finding.severity.value,
                    casilla,
                    finding.message,
                    next_action,
                )
            )
        )
        if finding.legal_refs:
            lines.append(f"finding_legal_refs\t{casilla}\t{', '.join(finding.legal_refs)}")
        if finding.source_refs:
            lines.append(f"finding_source_refs\t{casilla}\t{', '.join(finding.source_refs)}")
    if not report.granted_verificado_completo:
        lines.append(
            "next_action\taeat app modelo verification-report list "
            f"--calculation-revision-id {report.calculation_revision_id}"
        )
    return lines
