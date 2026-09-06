"""The composed `audit-all` dashboard: aggregation, rendering, and persistence.

In-process checks over constructed ``AdvisoryDimension`` fixtures (plain
data, no mocking) cover overall-status precedence, JSON serialisation, text
rendering, and the disk-persistence round trip. The two dimension functions
cheap enough to run against the live tree per-test (dead code, checkout
drift) are exercised for real in ``test_advisory_dimensions_scan``; the
full six-dimension `build_advisory_report` composition -- which includes a
full-tree semgrep scan taking several minutes -- was verified manually
end-to-end rather than carried as an automated test that would routinely
time out this lane (see the module's own docstring in ``dev/audit/advisory.py``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.core.directory_scan import scan_directory

from ..advisory import (
    AdvisoryDimension,
    _overall,
    _total_findings,
    persist,
    render_text,
    to_json,
)
from ..report import DimensionReport, Status

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def _dim(
    name: str,
    status: Status,
    headline: str,
    details: list[str] | None = None,
    count_by_severity: dict[str, int] | None = None,
    findings: tuple[dict[str, object], ...] = (),
    raw_payload: str = "",
    raw_payload_filename: str = "",
) -> AdvisoryDimension:
    return AdvisoryDimension(
        DimensionReport(name=name, status=status, headline=headline, details=details or []),
        count_by_severity=count_by_severity or {},
        findings=findings,
        raw_payload=raw_payload,
        raw_payload_filename=raw_payload_filename,
    )


# ---------------------------------------------------------------------------
# Overall precedence
# ---------------------------------------------------------------------------


def test_overall_is_green_when_every_dimension_is_green() -> None:
    dimensions = (
        _dim("a", Status.GREEN, "clean"),
        _dim("b", Status.GREEN, "clean"),
    )

    assert _overall(dimensions) is Status.GREEN


def test_overall_is_amber_when_no_dimension_is_red_but_one_is_amber() -> None:
    dimensions = (
        _dim("a", Status.GREEN, "clean"),
        _dim("b", Status.AMBER, "3 clones"),
    )

    assert _overall(dimensions) is Status.AMBER


def test_overall_is_red_when_any_dimension_is_red_even_with_amber_present() -> None:
    dimensions = (
        _dim("a", Status.RED, "1 new hotspot"),
        _dim("b", Status.AMBER, "3 clones"),
    )

    assert _overall(dimensions) is Status.RED


# ---------------------------------------------------------------------------
# total_findings: structured count, or the headline's leading number
# ---------------------------------------------------------------------------


def test_total_findings_prefers_structured_findings() -> None:
    dimension = _dim(
        "security",
        Status.RED,
        "2 finding(s) (1 ERROR, 1 WARNING) across 5 scanned file(s)",
        findings=({"a": 1}, {"b": 2}),
    )

    assert _total_findings(dimension) == 2


def test_total_findings_falls_back_to_the_headlines_leading_count() -> None:
    """Duplication's own headline says "17 clone cluster(s)" while `details` carries one pointer line."""
    dimension = _dim(
        "duplication",
        Status.AMBER,
        "17 clone cluster(s), 0.08% duplicated lines across 1482 analysed file(s) (advisory debt)",
        details=["see `just audit-duplication` for the full clone report"],
    )

    assert _total_findings(dimension) == 17


def test_total_findings_is_zero_for_a_clean_headline_with_no_leading_number() -> None:
    dimension = _dim("complexity", Status.GREEN, "no complexity hotspots")

    assert _total_findings(dimension) == 0


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def test_render_text_caps_details_unless_full() -> None:
    many_details = [f"line {i}" for i in range(20)]
    dimensions = (_dim("dead_code", Status.AMBER, "20 findings", details=many_details),)

    capped = render_text(dimensions, Status.AMBER, full=False)
    uncapped = render_text(dimensions, Status.AMBER, full=True)

    assert "more (see persisted summary.md)" in capped
    assert "more (see persisted summary.md)" not in uncapped
    assert capped.count("\n") < uncapped.count("\n")


def test_render_text_reports_fail_only_on_red() -> None:
    red = render_text((_dim("x", Status.RED, "bad"),), Status.RED, full=False)
    amber = render_text((_dim("x", Status.AMBER, "debt"),), Status.AMBER, full=False)

    assert "FAIL" in red
    assert "FAIL" not in amber
    assert "PASS" in amber


def test_to_json_carries_every_field_uncapped() -> None:
    details = [f"line {i}" for i in range(15)]
    dimensions = (_dim("dead_code", Status.AMBER, "15 findings", details=details, count_by_severity={"high": 15}),)

    # Routed through a JSON round trip (rather than indexed on the returned
    # dict directly): `to_json`'s declared return type is `dict[str, object]`,
    # so a strict checker cannot see the nested shape without this -- the
    # same reason every other test here reads persisted output back through
    # `json.loads` rather than the in-memory payload.
    payload = json.loads(json.dumps(to_json(dimensions, Status.AMBER, "2026-01-01T00:00:00+00:00")))

    assert payload["overall"] == "amber"
    dimension_payload = payload["dimensions"][0]
    assert dimension_payload["name"] == "dead_code"
    assert len(dimension_payload["details"]) == 15, "to_json must never cap details -- that is the terminal's job"
    assert dimension_payload["count_by_severity"] == {"high": 15}


# ---------------------------------------------------------------------------
# Persistence round trip
# ---------------------------------------------------------------------------


def test_persist_writes_a_parseable_uncapped_summary(tmp_path: Path) -> None:
    details = [f"finding {i}" for i in range(30)]
    dimensions = (
        _dim("security", Status.RED, "30 finding(s)", details=details, count_by_severity={"ERROR": 30}),
        _dim("complexity", Status.GREEN, "no complexity hotspots"),
    )
    run_dir = tmp_path / ".runs"

    result_dir = persist(run_dir, dimensions, Status.RED)

    assert result_dir == run_dir
    payload = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    assert payload["overall"] == "red"
    assert len(payload["dimensions"][0]["details"]) == 30, "the persisted JSON must carry every detail, never capped"

    text = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert text.count("finding ") >= 30, "the persisted markdown must be the full, uncapped rendering"
    assert "generated at" in text


def test_persist_writes_a_raw_payload_when_a_dimension_carries_one(tmp_path: Path) -> None:
    dimensions = (
        AdvisoryDimension(
            DimensionReport(name="security", status=Status.GREEN, headline="clean"),
            raw_payload='{"results": []}',
            raw_payload_filename="security-findings.json",
        ),
    )
    run_dir = tmp_path / ".runs"

    persist(run_dir, dimensions, Status.GREEN)

    assert (run_dir / "security-findings.json").read_text(encoding="utf-8") == '{"results": []}'


def test_persist_writes_nothing_extra_when_no_dimension_carries_a_raw_payload(tmp_path: Path) -> None:
    dimensions = (_dim("complexity", Status.GREEN, "no complexity hotspots"),)
    run_dir = tmp_path / ".runs"

    persist(run_dir, dimensions, Status.GREEN)

    written = {p.name for p in scan_directory(run_dir)}
    assert written == {"summary.json", "summary.md"}
