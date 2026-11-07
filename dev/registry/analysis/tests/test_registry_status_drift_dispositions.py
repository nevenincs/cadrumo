"""A generated-target drift is explained only by a live, evidence-matching ledger row.

The status report reads the same disposition ledger the reproduction gate and the
publisher read, through the same loader. A row keyed to exactly one target moves
that target's drift to ``explained`` and out of the currentness failure; a row
whose recorded evidence no longer describes the observed drift leaves the
failure standing and names why. Every ledger here is an isolated fixture file.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest
import rtoml

from cadrumo.domain.calculations.registry.tests.authored_editions import (
    authored_revisions,
    filing_year_envelope,
    open_ended_revision,
)

from ...compiler.authority import compiled_bundled_authority
from ...compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ...pipeline.generated_tree_dispositions import disposition_ledger_from_path
from ..generated_tree_state import GeneratedTreeState
from ..registry_status import (
    GeneratedTreeDispositionRow,
    ProjectedTargets,
    RegistryStatus,
    declared_revision_filing_years,
    project_target_states,
    registry_status_payload,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_REF = "aeat-dr-232-2016"
_SOURCE_SHA256 = "a" * 64
# A revision whose every declared filing year lies below the support floor.
_FLOOR = filing_year_envelope().floor
_FIRST_YEAR = _FLOOR - 6
_LAST_YEAR = _FLOOR - 5
_REVISION = f"{_FIRST_YEAR}-{_LAST_YEAR}"
_REVISION_YEARS = (_FIRST_YEAR, _LAST_YEAR)


def _below_floor_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": "below_floor",
        "modelo": "232",
        "revision": _REVISION,
        "source_ref": _SOURCE_REF,
        "source_sha256": _SOURCE_SHA256,
        "supported_filing_years_floor": _FLOOR,
        "revision_last_filing_year": _LAST_YEAR,
        "reason": "every declared filing year lies below the floor",
        "reconsideration_condition": "the floor is lowered or the revision is retired",
    }
    row.update(overrides)
    return row


def _record_drift_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": "record_drift",
        "modelo": "232",
        "revision": _REVISION,
        "source_ref": _SOURCE_REF,
        "source_sha256": _SOURCE_SHA256,
        "remedy": "repair_inputs",
        "differing_records": 2,
        "reason": "the shipped records are right and the inputs are not",
        "reconsideration_condition": "the inputs are repaired",
    }
    row.update(overrides)
    return row


def _ledger(tmp_path: Path, *rows: dict[str, object]) -> tuple[GeneratedTreeDispositionRow, ...]:
    """Write an isolated ledger and load it through the canonical loader."""
    path = tmp_path / "generated_tree_dispositions.toml"
    path.write_text(rtoml.dumps({"schema_version": 4, "dispositions": list(rows)}, pretty=True), encoding="utf-8")
    return disposition_ledger_from_path(path)


def _drifting(**overrides: object) -> GeneratedTreeState:
    base = GeneratedTreeState(
        modelo="232",
        revision=_REVISION,
        state="record_drift",
        differing=("0002-dr23201.toml", "0003-dr23202.toml", EXPORT_FRAGMENT_PROVENANCE_FILENAME),
        serialization_only=(),
        detail="2 meaningful of 3 differing file(s)",
        provenance_fields=("field_derivations",),
        committed_source=(_SOURCE_REF, _SOURCE_SHA256),
    )
    return replace(base, **overrides)


def _project(
    state: GeneratedTreeState,
    dispositions: tuple[GeneratedTreeDispositionRow, ...],
    *,
    floor: Callable[[], int] = lambda: _FLOOR,
    years: tuple[int, ...] = _REVISION_YEARS,
) -> ProjectedTargets:
    return project_target_states(
        (state,),
        (),
        dispositions=dispositions,
        declared_floor=floor,
        revision_filing_years=lambda _modelo, _revision: years,
        excluded_count=0,
    )


def _currentness(projected: ProjectedTargets) -> str:
    status = RegistryStatus(
        valid=True,
        oracles=True,
        targets=projected.counts,
        target_findings=projected.findings,
        authority="current",
        authority_recorded_digest=None,
        authority_candidate_digest=None,
        loadable=True,
        informational_bindings=(),
        details=projected.details,
    )
    lanes = registry_status_payload(status, blocking=True)["lanes"]
    assert isinstance(lanes, dict)
    return str(lanes["target_currentness"])


def _floor_never_read() -> int:
    raise AssertionError("the declared floor was read although no row names the target")


def test_below_floor_row_explains_the_drift_of_its_own_target(tmp_path: Path) -> None:
    projected = _project(_drifting(), _ledger(tmp_path, _below_floor_row()))

    counts = dict(projected.counts)
    assert counts["explained"] == 1
    assert counts["drifted"] == 0
    assert _currentness(projected) == "passed"
    explained = dict(projected.findings)["explained"]
    assert [(modelo, revision) for modelo, revision, _ in explained] == [("232", _REVISION)]
    assert f"below the supported floor {_FLOOR}" in explained[0][2]


def test_the_same_drift_without_a_row_fails(tmp_path: Path) -> None:
    projected = _project(_drifting(), _ledger(tmp_path), floor=_floor_never_read)

    assert dict(projected.counts)["drifted"] == 1
    assert dict(projected.counts)["explained"] == 0
    assert _currentness(projected) == "failed"


def test_a_row_keyed_to_another_target_explains_nothing(tmp_path: Path) -> None:
    other = _below_floor_row(revision=str(_FIRST_YEAR - 1), revision_last_filing_year=_FIRST_YEAR - 1)
    projected = _project(_drifting(), _ledger(tmp_path, other), floor=_floor_never_read)

    assert dict(projected.counts)["drifted"] == 1
    assert _currentness(projected) == "failed"


@pytest.mark.parametrize(
    ("state_overrides", "floor", "years", "reason"),
    [
        ({"committed_source": (_SOURCE_REF, "b" * 64)}, _FLOOR, _REVISION_YEARS, "committed tree attests"),
        ({"committed_source": None}, _FLOOR, _REVISION_YEARS, "no loadable manifest"),
        ({"provenance_fields": ("source_sha256",)}, _FLOOR, _REVISION_YEARS, "fresh render moved source_sha256"),
        ({}, _FLOOR - 1, _REVISION_YEARS, f"the registry declares {_FLOOR - 1}"),
        ({}, _FLOOR, (_FIRST_YEAR, _LAST_YEAR + 1), f"revision declares [{_FIRST_YEAR}, {_LAST_YEAR + 1}]"),
        ({}, _FLOOR, (), "revision declares []"),
    ],
    ids=[
        "design-digest-moved",
        "manifest-unloadable",
        "render-moved-source",
        "declared-floor-moved",
        "revision-years-moved",
        "revision-years-absent",
    ],
)
def test_a_below_floor_row_whose_evidence_no_longer_matches_fails(
    tmp_path: Path,
    state_overrides: dict[str, object],
    floor: int,
    years: tuple[int, ...],
    reason: str,
) -> None:
    projected = _project(
        _drifting(**state_overrides),
        _ledger(tmp_path, _below_floor_row()),
        floor=lambda: floor,
        years=years,
    )

    assert dict(projected.counts)["drifted"] == 1
    assert dict(projected.counts)["explained"] == 0
    assert _currentness(projected) == "failed"
    (detail,) = projected.details
    assert "disposition not honoured" in detail
    assert reason in detail


def test_a_record_drift_row_explains_only_the_record_count_it_states(tmp_path: Path) -> None:
    matching = _project(_drifting(), _ledger(tmp_path, _record_drift_row()))
    assert dict(matching.counts)["explained"] == 1
    assert _currentness(matching) == "passed"

    widened = _project(
        _drifting(differing=("0002-dr23201.toml", "0003-dr23202.toml", "0004-extra.toml")),
        _ledger(tmp_path, _record_drift_row()),
    )
    assert dict(widened.counts)["drifted"] == 1
    assert _currentness(widened) == "failed"
    assert "comparison reports 3" in widened.details[0]


def test_a_record_drift_row_does_not_explain_manifest_only_staleness(tmp_path: Path) -> None:
    stale = _drifting(state="manifest_only_stale", differing=(EXPORT_FRAGMENT_PROVENANCE_FILENAME,))
    projected = _project(stale, _ledger(tmp_path, _record_drift_row()))

    assert dict(projected.counts)["stale"] == 1
    assert _currentness(projected) == "failed"
    assert "only the generation manifest differs" in projected.details[0]


@pytest.mark.parametrize(
    "row",
    [
        {
            "kind": "render_refusal",
            "modelo": "232",
            "revision": _REVISION,
            "source_ref": _SOURCE_REF,
            "source_sha256": _SOURCE_SHA256,
            "refusal_marker": "no revision for year",
            "reason": "the generator refuses to render this design",
            "reconsideration_condition": "the refusal is resolved",
        },
        {
            "kind": "type_column_contradiction",
            "modelo": "232",
            "revision": _REVISION,
            "source_ref": _SOURCE_REF,
            "source_sha256": _SOURCE_SHA256,
            "derivation_code": "literal-exact-v1",
            "field_count": 2,
            "reason": "the inputs contradict the official type column",
            "reconsideration_condition": "the schema can express both readings",
        },
    ],
    ids=["render-refusal", "type-column-contradiction"],
)
def test_classes_that_describe_no_drift_do_not_explain_one(tmp_path: Path, row: dict[str, object]) -> None:
    projected = _project(_drifting(), _ledger(tmp_path, row))

    assert dict(projected.counts)["drifted"] == 1
    assert _currentness(projected) == "failed"


def test_a_revision_declared_as_a_year_range_reports_the_end_of_its_range() -> None:
    """A range selector lists no years, yet its last declared year decides whether it is below the floor."""
    modelo = compiled_bundled_authority().modelo("341")

    ranged = next(
        revision
        for revision in authored_revisions("341")
        if revision.valid_to is not None and revision.valid_from.year != revision.valid_to.year
    )
    assert ranged.valid_to is not None
    assert declared_revision_filing_years(modelo, ranged.id) == (ranged.valid_to.year,)
    assert declared_revision_filing_years(modelo, open_ended_revision("341").id) == ()
