"""The status report carries the fixed-width placement census as its own lane.

The compiler refuses an overlap and only advises a gap, so without a reported
line the gap population is visible to nobody: an advisory nothing prints is
indistinguishable from an advisory nothing raises. These tests pin that the
census reaches the payload, that its denominators travel with its findings, and
that a real planted gap moves the count.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.domain.calculations.registry.schema import ModeloDefinition

from ...compiler.loader import load_modelo_directory
from ...conformance.stamp import bundled_registry_root
from ..registry_status import (
    EXPORT_PLACEMENT_POPULATION,
    ExportPlacementCensus,
    RegistryStatus,
    _payload,
    _render_export_placement,
    export_placement_census,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_REVISION = "2024-y-siguientes"
_PERCEPTOR_RECORD = Path("revisions") / _REVISION / "export" / "0002-record-m296-perceptor.toml"
_SHIPPED_SECOND_FIELD = "id = 'm296-2024.perceptor.f002'\noffset = 2\nlength = 3\n"


def _status(*, export_placement: ExportPlacementCensus) -> RegistryStatus:
    """Build a status whose only varying axis is the placement census."""
    return RegistryStatus(
        valid=True,
        oracles=True,
        targets=(("current", 1), ("stale", 0), ("drifted", 0), ("never-committed", 0), ("unreadable", 0)),
        target_findings=(),
        authority="current",
        authority_recorded_digest=None,
        authority_candidate_digest=None,
        loadable=True,
        unreferenced_bindings=(),
        informational_bindings=(),
        details=(),
        export_placement=export_placement,
    )


def _modelo_296(tmp_path: Path, *, second_field_length: int | None = None) -> ModeloDefinition:
    """Load a copy of the shipped Modelo 296 tree, optionally re-declaring one field."""
    modelo_dir = tmp_path / "296"
    shutil.copytree(bundled_registry_root() / "modelos" / "296", modelo_dir)
    if second_field_length is not None:
        record = modelo_dir / _PERCEPTOR_RECORD
        text = record.read_text(encoding="utf-8")
        assert _SHIPPED_SECOND_FIELD in text
        record.write_text(
            text.replace(
                _SHIPPED_SECOND_FIELD,
                _SHIPPED_SECOND_FIELD.replace("length = 3", f"length = {second_field_length}"),
            ),
            encoding="utf-8",
        )
    return load_modelo_directory(modelo_dir)


def test_a_planted_gap_raises_the_reported_count(tmp_path: Path) -> None:
    """Shortening one field by two positions must move the census, not just the check.

    The whole point of the lane is that a gap the compiler declines to refuse
    still arrives somewhere an operator reads. Measured as a delta against the
    same tree unmodified, so the assertion survives the shipped corpus changing
    its gap population.
    """
    clean = export_placement_census((_modelo_296(tmp_path / "clean"),))
    planted = export_placement_census((_modelo_296(tmp_path / "planted", second_field_length=1),))

    assert planted.gaps == clean.gaps + 1
    assert planted.overlaps == clean.overlaps
    assert planted.records == clean.records
    assert planted.fields == clean.fields
    assert ("296", 1) in planted.by_modelo
    assert planted.by_modelo != clean.by_modelo


def test_a_planted_overlap_fails_the_lane(tmp_path: Path) -> None:
    """An overlap is a build refusal, so observing one must fail the lane, not soften it."""
    census = export_placement_census((_modelo_296(tmp_path / "planted", second_field_length=5),))

    assert census.overlaps == 1
    lanes = _payload(_status(export_placement=census), blocking=False)["lanes"]
    assert isinstance(lanes, dict)
    assert lanes["export_placement_coverage"] == "failed"


def test_a_binding_derived_record_is_not_counted_as_an_unwritten_head(tmp_path: Path) -> None:
    """Modelo 720's census must be silent: its head is declared by bindings, not missing.

    The record whose first inline field sits at position 181 is the case that
    would put two phantom findings into the operator's report if the census
    read only inline fields.
    """
    modelo_dir = tmp_path / "720"
    shutil.copytree(bundled_registry_root() / "modelos" / "720", modelo_dir)
    census = export_placement_census((load_modelo_directory(modelo_dir),))

    assert census.overlaps == 0
    assert census.gaps == 0
    assert census.records > 0
    assert census.by_modelo == ()


def test_the_shipped_carrier_walks_records_and_finds_neither_defect(tmp_path: Path) -> None:
    """The unmodified tree is silent AND non-empty, so the plant is what the teeth measure."""
    census = export_placement_census((_modelo_296(tmp_path),))

    assert census.overlaps == 0
    assert census.gaps == 0
    assert census.records > 0
    assert census.fields > 0


def test_the_payload_carries_the_findings_with_their_denominators() -> None:
    """Counts alone cannot be read: zero findings over zero records is not health."""
    payload = _payload(
        _status(export_placement=ExportPlacementCensus(overlaps=0, gaps=115, records=415, fields=27639)),
        blocking=False,
    )

    assert payload["export_placement"] == {
        "population": EXPORT_PLACEMENT_POPULATION,
        "overlaps": 0,
        "gaps": 115,
        "records": 415,
        "fields": 27639,
        "by_modelo": {},
    }


def test_a_gap_only_census_is_partial_and_does_not_fail_the_report() -> None:
    """The lane mirrors the compiler's posture: a gap is advisory, not a failure."""
    payload = _payload(_status(export_placement=ExportPlacementCensus(gaps=115, records=415)), blocking=False)

    lanes = payload["lanes"]
    assert isinstance(lanes, dict)
    partial_lanes = payload["partial_lanes"]
    assert lanes["export_placement_coverage"] == "partial"
    assert isinstance(partial_lanes, list)
    assert "export_placement_coverage" in partial_lanes
    assert payload["result"] == "passed"


def test_a_status_assembled_without_a_census_reports_walking_nothing() -> None:
    """The default census must not read as a clean sweep of the whole corpus."""
    payload = _payload(_status(export_placement=ExportPlacementCensus()), blocking=False)

    assert payload["export_placement"] == {
        "population": EXPORT_PLACEMENT_POPULATION,
        "overlaps": 0,
        "gaps": 0,
        "records": 0,
        "fields": 0,
        "by_modelo": {},
    }


def test_the_rendered_line_names_the_population_it_counted(capsys: pytest.CaptureFixture[str]) -> None:
    """A bare count invites comparison against lanes that walk files, and must not.

    The placement census counts materialised records per revision from two
    declaration sites; every neighbouring lane counts files. Printing four
    numbers without saying which population they belong to is how a reader
    concludes the registry lost a few hundred records.
    """
    _render_export_placement(ExportPlacementCensus(overlaps=0, gaps=115, records=415, fields=27639))

    rendered = capsys.readouterr().out.strip()
    assert rendered.startswith(f"export_placement({EXPORT_PLACEMENT_POPULATION}): ")
    assert rendered.endswith("overlaps=0 gaps=115 records=415 fields=27639")
