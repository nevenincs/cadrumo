"""All-or-nothing shard preservation and validated writes."""

from __future__ import annotations

import dataclasses

from cadrumo.core.toml import TomlDecodeError, parse_toml

from .casilla_shard_attestations import (
    _refuse_duplicate_ids,
    emitted_ids,
    harvest_attestations,
    reattach_attestations,
    refuse_dropped_attestations,
)
from .casilla_shard_toml_text import _KEY_LINE
from .casilla_shard_types import GenerationRefusedError, GenerationReport, WaveSpec


def _finalize_emission(spec: WaveSpec, report: GenerationReport, *, write: bool) -> None:
    _refuse_duplicate_ids(report)
    _preserve_attestations(spec, report)
    if write:
        _write_outcomes(spec, report)
    if report.refusals:
        raise GenerationRefusedError(
            f"{len(report.refusals)} row(s) need adjudication: " + "; ".join(report.refusals[:5])
        )


def _preserve_attestations(spec: WaveSpec, report: GenerationReport) -> None:
    harvested = harvest_attestations(spec.out_dir, spec.revision_id)
    if not harvested:
        return
    refuse_dropped_attestations(
        harvested,
        set(emitted_ids(report)),
        {outcome.filename for outcome in report.outcomes},
    )
    restored = 0
    for index, outcome in enumerate(report.outcomes):
        body, carried = reattach_attestations(outcome.body, harvested, spec.revision_id)
        restored += carried
        report.outcomes[index] = dataclasses.replace(outcome, body=body)
    report.attestations_restored = restored
    produced = {outcome.filename for outcome in report.outcomes}
    report.orphaned_shards = sorted(path.name for path in spec.out_dir.glob("*.toml") if path.name not in produced)


def _write_outcomes(spec: WaveSpec, report: GenerationReport) -> None:
    for outcome in report.outcomes:
        spec.out_dir.mkdir(parents=True, exist_ok=True)
        target = spec.out_dir / outcome.filename
        target.write_text(outcome.body, encoding="utf-8")
        back = target.read_text(encoding="utf-8")
        _validate_writeback(outcome.segmento, outcome.emitted, spec.revision_id, outcome.body, back)


def _validate_writeback(
    segmento: str,
    emitted: int,
    revision_id: str,
    body: str,
    back: str,
) -> None:
    if back != body:
        raise GenerationRefusedError(f"{segmento}: read-back differs from the write")
    _validate_toml_lines(segmento, back)
    try:
        parse_toml(back)
    except TomlDecodeError as error:
        raise GenerationRefusedError(f"{segmento}: the emitted shard does not parse: {error}") from error
    marker = f'[[revisions."{revision_id}".casillas]]'
    if back.count(marker) != emitted:
        raise GenerationRefusedError(f"{segmento}: read-back casilla count is wrong")


def _validate_toml_lines(segmento: str, text: str) -> None:
    for number, line in enumerate(text.splitlines(), start=1):
        if line and not (line.startswith(("#", "[")) or _KEY_LINE.match(line)):
            raise GenerationRefusedError(f"{segmento}: line {number} is neither comment nor key: {line[:60]!r}")
