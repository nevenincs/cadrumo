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
from pydantic import ValidationError

from cadrumo.core.authority_grade import RegistryAuthorityGrade

from ...compiler.export_fragment_grammar import EXPORT_FRAGMENT_PROVENANCE_FILENAME
from ...pipeline.generated_tree_dispositions import disposition_ledger_from_path
from ..generated_tree_state import GeneratedTreeState
from ..registry_status import (
    GeneratedTreeDispositionRow,
    ProjectedTargets,
    RegistryStatus,
    _payload,
    project_target_states,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_SOURCE_REF = "aeat-dr-232-2016"
_SOURCE_SHA256 = "a" * 64
_FLOOR = 2022
_REVISION_YEARS = (2016, 2017)


def _below_floor_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": "below_floor",
        "modelo": "232",
        "revision": "2016-2017",
        "source_ref": _SOURCE_REF,
        "source_sha256": _SOURCE_SHA256,
        "supported_filing_years_floor": _FLOOR,
        "revision_last_filing_year": 2017,
        "reason": "every declared filing year lies below the floor",
        "reconsideration_condition": "the floor is lowered or the revision is retired",
    }
    row.update(overrides)
    return row


def _record_drift_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": "record_drift",
        "modelo": "232",
        "revision": "2016-2017",
        "source_ref": _SOURCE_REF,
        "source_sha256": _SOURCE_SHA256,
        "remedy": "repair_inputs",
        "differing_records": 2,
        "reason": "the shipped records are right and the inputs are not",
        "reconsideration_condition": "the inputs are repaired",
    }
    row.update(overrides)
    return row


def _below_publication_grade_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "kind": "below_publication_grade",
        "modelo": "232",
        "revision": "2016-2017",
        "source_ref": _SOURCE_REF,
        "source_sha256": _SOURCE_SHA256,
        "authority_grade": "applicability",
        "reason": "the revision grade lies below the static-publication floor",
        "reconsideration_condition": "the revision earns calculation authority",
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
        revision="2016-2017",
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
    grade: RegistryAuthorityGrade | None = RegistryAuthorityGrade.APPLICABILITY,
) -> ProjectedTargets:
    return project_target_states(
        (state,),
        (),
        dispositions=dispositions,
        declared_floor=floor,
        revision_filing_years=lambda _modelo, _revision: years,
        revision_authority_grade=lambda _modelo, _revision: grade,
        excluded_count=0,
    )


def _manifest_only_stale(**overrides: object) -> GeneratedTreeState:
    return _drifting(
        state="manifest_only_stale",
        differing=("0002-dr23201.toml", EXPORT_FRAGMENT_PROVENANCE_FILENAME),
        serialization_only=("0002-dr23201.toml",),
        detail="1 meaningful of 2 differing file(s)",
        **overrides,
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
        unreferenced_bindings=(),
        informational_bindings=(),
        details=projected.details,
    )
    lanes = _payload(status, blocking=True)["lanes"]
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
    assert [(modelo, revision) for modelo, revision, _ in explained] == [("232", "2016-2017")]
    assert "below the supported floor 2022" in explained[0][2]


def test_the_same_drift_without_a_row_fails(tmp_path: Path) -> None:
    projected = _project(_drifting(), _ledger(tmp_path), floor=_floor_never_read)

    assert dict(projected.counts)["drifted"] == 1
    assert dict(projected.counts)["explained"] == 0
    assert _currentness(projected) == "failed"


def test_a_row_keyed_to_another_target_explains_nothing(tmp_path: Path) -> None:
    other = _below_floor_row(revision="2015", revision_last_filing_year=2015)
    projected = _project(_drifting(), _ledger(tmp_path, other), floor=_floor_never_read)

    assert dict(projected.counts)["drifted"] == 1
    assert _currentness(projected) == "failed"


@pytest.mark.parametrize(
    ("state_overrides", "floor", "years", "reason"),
    [
        ({"committed_source": (_SOURCE_REF, "b" * 64)}, _FLOOR, _REVISION_YEARS, "committed tree attests"),
        ({"committed_source": None}, _FLOOR, _REVISION_YEARS, "no loadable manifest"),
        ({"provenance_fields": ("source_sha256",)}, _FLOOR, _REVISION_YEARS, "fresh render moved source_sha256"),
        ({}, 2021, _REVISION_YEARS, "the registry declares 2021"),
        ({}, _FLOOR, (2016, 2018), "revision declares [2016, 2018]"),
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
            "revision": "2016-2017",
            "source_ref": _SOURCE_REF,
            "source_sha256": _SOURCE_SHA256,
            "refusal_marker": "no revision for year",
            "reason": "the generator refuses to render this design",
            "reconsideration_condition": "the refusal is resolved",
        },
        {
            "kind": "type_column_contradiction",
            "modelo": "232",
            "revision": "2016-2017",
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


def test_below_publication_grade_row_explains_manifest_only_staleness(tmp_path: Path) -> None:
    projected = _project(_manifest_only_stale(), _ledger(tmp_path, _below_publication_grade_row()))

    assert dict(projected.counts)["explained"] == 1
    assert dict(projected.counts)["stale"] == 0
    assert _currentness(projected) == "passed"
    explained = dict(projected.findings)["explained"]
    assert "'applicability' authority lies below the static-publication grade" in explained[0][2]


def test_the_same_staleness_without_a_row_fails(tmp_path: Path) -> None:
    projected = _project(_manifest_only_stale(), _ledger(tmp_path), floor=_floor_never_read)

    assert dict(projected.counts)["stale"] == 1
    assert _currentness(projected) == "failed"


@pytest.mark.parametrize(
    ("state", "grade", "reason"),
    [
        (_drifting(), RegistryAuthorityGrade.APPLICABILITY, "comparison reports record drift"),
        (_manifest_only_stale(), RegistryAuthorityGrade.CALCULATION, "the revision declares 'calculation'"),
        (_manifest_only_stale(), None, "the revision declares no grade"),
        (
            _manifest_only_stale(committed_source=(_SOURCE_REF, "b" * 64)),
            RegistryAuthorityGrade.APPLICABILITY,
            "committed tree attests",
        ),
    ],
    ids=["record-drift", "grade-raised", "grade-undeclared", "design-digest-moved"],
)
def test_a_below_publication_grade_row_whose_evidence_no_longer_matches_fails(
    tmp_path: Path,
    state: GeneratedTreeState,
    grade: RegistryAuthorityGrade | None,
    reason: str,
) -> None:
    projected = _project(state, _ledger(tmp_path, _below_publication_grade_row()), grade=grade)

    assert dict(projected.counts)["explained"] == 0
    assert _currentness(projected) == "failed"
    (detail,) = projected.details
    assert "disposition not honoured" in detail
    assert reason in detail


def test_a_below_publication_grade_row_at_the_publication_grade_is_refused(tmp_path: Path) -> None:
    with pytest.raises(ValidationError, match="reaches the static-publication grade 'calculation'"):
        _ledger(tmp_path, _below_publication_grade_row(authority_grade="calculation"))
