"""Text rendering helpers for live Cadrumo CLI command envelopes."""

from __future__ import annotations

from collections.abc import Sequence

from ...application.live.remote_state_models import (
    BulkFiledDataCaptureReport,
    FiledDataCaptureFailureRow,
    FiledDataCaptureReport,
    SourceFiledDataCaptureReport,
)
from ._app_live_auth_preflight import metric_line

type FiledCaptureReport = FiledDataCaptureReport | BulkFiledDataCaptureReport | SourceFiledDataCaptureReport


def _filed_capture_lines(
    report: FiledCaptureReport,
    *,
    mode: str,
    modelo: str | None = None,
    year: int | None = None,
    modelos: Sequence[str] = (),
    year_from: int | None = None,
    year_to: int | None = None,
    failures: Sequence[FiledDataCaptureFailureRow] = (),
) -> tuple[str, ...]:
    """Return text metrics for filed declaration capture reports."""
    lines: list[str] = [metric_line("mode", mode)]
    if modelo is not None:
        lines.append(metric_line("modelo", modelo))
    if year is not None:
        lines.append(metric_line("year", year))
    if modelos:
        lines.append(metric_line("modelo_count", len(modelos)))
    if year_from is not None:
        lines.append(metric_line("year_from", year_from))
    if year_to is not None:
        lines.append(metric_line("year_to", year_to))
    if getattr(report, "dry_run", False):
        # Text and JSON must agree on the one fact that decides whether anything
        # was written, so the metric rides both surfaces rather than JSON alone.
        lines.append(metric_line("dry_run", "true"))
    failed_count = getattr(report, "failed_count", len(failures))
    lines.extend(
        (
            metric_line("captured_count", report.captured_count),
            metric_line("failed_count", failed_count),
            metric_line("casilla_count", report.casilla_count),
            metric_line("justificante_metadata_count", report.justificante_metadata_count),
            metric_line("justificante_csvs", ",".join(report.justificante_csvs)),
            metric_line("filing_evidence_stamped_count", report.filing_evidence_stamped_count),
            metric_line("filing_record_ids", ",".join(report.filing_record_ids)),
            metric_line("filing_evidence_conflict_count", report.filing_evidence_conflict_count),
            metric_line(
                "filing_evidence_conflict_record_ids",
                ",".join(report.filing_evidence_conflict_record_ids),
            ),
            metric_line("calculation_observation_count", report.calculation_observation_count),
            metric_line("calculation_observation_keys", ",".join(report.calculation_observation_keys)),
            metric_line("observation_paths", ",".join(report.observation_paths)),
            metric_line("artefact_refs", ",".join(report.artefact_refs)),
        ),
    )
    lines.extend(_filed_capture_failure_lines(failures))
    return tuple(lines)


def _source_filed_capture_lines(report: SourceFiledDataCaptureReport) -> tuple[str, ...]:
    """Return text metrics for source-observation filed capture reports."""
    return (
        metric_line("target_modelo", report.target_modelo),
        metric_line("target_year", report.target_year),
        metric_line("target_period", report.target_period.registry_token),
        *_filed_capture_lines(report, mode="sources"),
    )


def _filed_capture_failure_lines(failures: Sequence[FiledDataCaptureFailureRow]) -> tuple[str, ...]:
    return tuple(
        metric_line(
            "failure",
            "\t".join(
                (
                    failure.modelo,
                    str(failure.year),
                    failure.period.registry_token if failure.period is not None else "",
                    failure.expediente_id or "",
                    failure.error_type,
                    failure.message,
                ),
            ),
        )
        for failure in failures
    )


__all__ = [
    "_filed_capture_failure_lines",
    "_filed_capture_lines",
    "_source_filed_capture_lines",
    "metric_line",
]
