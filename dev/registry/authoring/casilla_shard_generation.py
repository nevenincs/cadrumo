"""Registry casilla shard generation orchestration."""

from __future__ import annotations

from collections.abc import Mapping

from dev.registry.compiler.record_design_schema import (
    RecordDesignSheet,
)

from .casilla_shard_design import (
    cross_check_sidecar,
    read_design,
    verify_design_hash,
)
from .casilla_shard_emission import _emit_record
from .casilla_shard_types import GenerationReport, WaveSpec
from .casilla_shard_writer import _finalize_emission


def generate(spec: WaveSpec, *, write: bool = False) -> GenerationReport:
    """Emit one revision's shards, refusing anything that needs a judgement."""
    verify_design_hash(spec.design_path, spec.declared_sha256)
    sheets = read_design(spec.design_path)
    cross_check_sidecar(spec.design_path, sheets)
    return emit_records(spec, sheets, write=write)


def emit_records(
    spec: WaveSpec,
    sheets: Mapping[str, RecordDesignSheet],
    *,
    write: bool = False,
) -> GenerationReport:
    """Emit already-read sheets through the real refusal and preservation path."""
    report = GenerationReport()
    for segmento in spec.records:
        _emit_record(spec, sheets, segmento, report)
    _finalize_emission(spec, report, write=write)
    return report
