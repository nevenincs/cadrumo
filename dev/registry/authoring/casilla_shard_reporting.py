"""Human-readable reports for casilla shard generation."""

from __future__ import annotations

from collections.abc import Sequence

from dev.registry.compiler.record_design_schema import (
    RecordDesignSheet,
)

from .casilla_shard_types import GenerationReport


def format_report(report: GenerationReport) -> str:
    """Render a run for a human, drift and all."""
    lines = [
        f"OK {outcome.segmento}: emit={outcome.emitted} carried={outcome.carried} "
        f"adjudicated={outcome.adjudicated} out-of-scope={outcome.out_of_scope} "
        f"tiled={outcome.tiled}=={outcome.declared_total} -> {outcome.filename}"
        for outcome in report.outcomes
    ]
    lines.append(f"\nDEFERRED pending adjudication: {len(report.deferred)}")
    lines.extend(f"  {entry}" for entry in report.deferred)
    lines.append(f"\nCAPTION DRIFT on position-stable rows: {len(report.drift)}")
    lines.extend(f"  {entry}" for entry in report.drift)
    if report.orphaned_shards:
        lines.append(f"\nSHARDS IN out_dir THIS RUN DOES NOT PRODUCE: {len(report.orphaned_shards)}")
        lines.extend(f"  {name}" for name in report.orphaned_shards)
    lines.append(f"\nATTESTATIONS carried forward from disk: {report.attestations_restored}")
    lines.append(f"\nTOTAL casillas: {report.total_emitted}")
    return "\n".join(lines)


def sections_of(sheets: Sequence[RecordDesignSheet]) -> dict[str, int]:
    """Field counts per sheet, for asserting a run against a measured shape."""
    return {sheet.name.strip(): len(sheet.fields) for sheet in sheets}
