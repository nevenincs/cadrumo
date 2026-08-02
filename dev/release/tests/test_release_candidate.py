"""Behavioural proof for the sealed release candidate and its soak window.

The load-bearing properties here are all about a record that must survive two
to three days outside any running process: it round-trips exactly, it refuses a
payload that lost a field rather than defaulting one back, its deadline comes
from the declared policy rather than a literal, and its tag namespace is one the
evidence garbage collector cannot reach.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from dev.packaging.evidence_release import EVIDENCE_TAG_RE, plan_evidence_gc
from dev.release import release_candidate
from dev.release.release_candidate import (
    CANDIDATE_TAG_RE,
    ReleaseCandidate,
    ReleaseCandidateError,
    SoakWindow,
    candidate_tag,
    candidate_tags_in,
    load_candidate,
    load_soak_window,
    parse_candidate_tag,
    seal_candidate,
    write_candidate,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_REPO_ROOT = Path(__file__).resolve().parents[3]
_COHORT = "a" * 64
_COMMIT = "b" * 40
_OPENED = datetime(2026, 8, 2, 12, 0, tzinfo=UTC)


def _fully_populated() -> ReleaseCandidate:
    """Return a candidate with EVERY defaultable field set to a non-default value.

    Roundtrip discipline: a fixture that leaves optionals at their defaults
    cannot detect a save-drops-field / load-re-defaults-field regression,
    because the dropped value and the default are the same bytes.
    """
    return seal_candidate(
        cohort_id=_COHORT,
        version="1.2.3",
        source_commit=_COMMIT,
        packaging_run_id="4242",
        scoop_run_id="4243",
        homebrew_run_id="4244",
        claude_evidence_release="evidence-claude-manual-2026-08-02",
        claimed_channels=("python", "scoop", "homebrew"),
        dry_run=True,
        window=SoakWindow(minimum_hours=48, maximum_hours=72),
        opened_at=_OPENED,
    )


def test_the_candidate_round_trips_through_its_asset_file_exactly(tmp_path: Path) -> None:
    """Save, load, and assert strict equality with every optional field populated."""
    original = _fully_populated()

    path = write_candidate(original, tmp_path / "release-candidate.json")
    reloaded = load_candidate(path)

    assert reloaded == original
    # Named explicitly: these are the fields a promoter needs days later and
    # cannot re-derive, so a silent drop would surface as a failed dispatch.
    assert reloaded.scoop_run_id == "4243"
    assert reloaded.homebrew_run_id == "4244"
    assert reloaded.claude_evidence_release == "evidence-claude-manual-2026-08-02"
    assert reloaded.claimed_channels == ("python", "scoop", "homebrew")
    assert reloaded.dry_run is True


def test_a_record_that_lost_its_deadline_refuses_to_load(tmp_path: Path) -> None:
    """Anti-tautology proof: delete the deadline on disk and prove the load fails.

    If this ever passes with the field removed, every roundtrip assertion above
    is worthless - the model would be reconstructing a soak deadline that the
    stored evidence does not contain, which is precisely how a candidate could
    publish against a window nobody recorded.
    """
    path = write_candidate(_fully_populated(), tmp_path / "release-candidate.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    del payload["soak_deadline"]
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_candidate(path)


def test_a_record_carrying_an_unknown_field_refuses_to_load(tmp_path: Path) -> None:
    """`extra="forbid"` in both directions: an unexpected key is a refusal, not a shrug."""
    path = write_candidate(_fully_populated(), tmp_path / "release-candidate.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["soak_hours_override"] = 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValidationError):
        load_candidate(path)


def test_the_deadline_is_computed_from_the_declared_window() -> None:
    """The window comes from policy; sealing applies it rather than choosing one."""
    window = SoakWindow(minimum_hours=48, maximum_hours=72)

    candidate = seal_candidate(
        cohort_id=_COHORT,
        version="1.2.3",
        source_commit=_COMMIT,
        packaging_run_id="4242",
        claimed_channels=("python",),
        dry_run=False,
        window=window,
        opened_at=_OPENED,
    )

    assert candidate.soak_opened_at == _OPENED
    assert candidate.soak_deadline == _OPENED + timedelta(hours=48)


def test_the_window_is_read_from_the_real_release_checklist() -> None:
    """The shipped checklist is the authority, and it is read rather than mirrored.

    Bound to the real file, not a fixture: the point of the requirement is that
    exactly one artifact declares the duration, so a test against a synthetic
    window would pass while the two silently diverged.
    """
    window = load_soak_window(_REPO_ROOT)

    assert window.minimum_hours == 48
    assert window.maximum_hours == 72


def test_a_checklist_without_a_soak_section_refuses_rather_than_defaulting(tmp_path: Path) -> None:
    """No fallback literal. A missing policy is a refusal.

    A default here would be a second authority over the soak duration, which is
    the exact failure the "read it from the checklist" requirement exists to
    prevent.
    """
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "_release_checklist.yaml").write_text("schema_version: 1\n", encoding="utf-8")

    with pytest.raises(ReleaseCandidateError, match="no soak section"):
        load_soak_window(tmp_path)


def test_a_naive_opened_at_is_refused() -> None:
    """A timezone-naive instant has no defensible deadline, so sealing refuses it."""
    with pytest.raises(ReleaseCandidateError, match="timezone-aware"):
        seal_candidate(
            cohort_id=_COHORT,
            version="1.2.3",
            source_commit=_COMMIT,
            packaging_run_id="4242",
            claimed_channels=("python",),
            dry_run=False,
            window=SoakWindow(minimum_hours=48, maximum_hours=72),
            opened_at=datetime(2026, 8, 2, 12, 0),
        )


def test_the_window_boundary_is_inclusive() -> None:
    """A candidate at exactly its deadline has served the full declared minimum.

    Pinned because both mistakes are silent. An exclusive comparison makes every
    window imperceptibly longer than policy; comparing against `opened_at`
    instead of the deadline publishes immediately.
    """
    candidate = _fully_populated()

    assert candidate.window_elapsed(now=candidate.soak_deadline) is True
    assert candidate.window_elapsed(now=candidate.soak_deadline - timedelta(seconds=1)) is False
    assert candidate.window_elapsed(now=candidate.soak_deadline + timedelta(seconds=1)) is True


def test_the_candidate_namespace_is_unreachable_by_the_evidence_gc() -> None:
    """The soak state must outlive evidence retention, and does so by construction.

    A candidate sits sealed for two to three days. The evidence GC keeps only
    the newest K drafts per lane, so a candidate inside that namespace could be
    deleted by later campaigns mid-window - and a collected candidate does not
    publish late, it never publishes at all.

    This asserts the real GC planner ignores the namespace, so enrolling
    candidates as an EvidenceLane would red here rather than silently making
    in-flight soak state collectable.
    """
    tag = candidate_tag("101")
    assert EVIDENCE_TAG_RE.fullmatch(tag) is None
    assert CANDIDATE_TAG_RE.fullmatch(tag) is not None

    releases = [
        {"tag_name": "evidence-smoke-101", "draft": True, "created_at": "2026-08-01T00:00:00Z"},
        {"tag_name": "evidence-smoke-102", "draft": True, "created_at": "2026-08-02T00:00:00Z"},
        {"tag_name": tag, "draft": True, "created_at": "2026-08-01T00:00:00Z"},
    ]
    plan = plan_evidence_gc(releases, keep_per_lane=1)

    assert tag not in plan.delete
    assert tag not in plan.kept, "the candidate must be invisible to the GC, not merely spared by retention"
    # Control: the GC is genuinely running and deleting in this scenario, so the
    # candidate's absence is exemption rather than an inert planner.
    assert "evidence-smoke-101" in plan.delete


def test_only_draft_releases_in_the_reserved_namespace_are_candidates() -> None:
    """A published release is never a candidate, whatever its tag looks like."""
    releases = [
        {"tag_name": "release-candidate-101", "draft": True},
        {"tag_name": "release-candidate-102", "draft": False},
        {"tag_name": "v1.2.3", "draft": False},
        {"tag_name": "evidence-smoke-103", "draft": True},
    ]

    assert candidate_tags_in(releases) == ("release-candidate-101",)


def test_tag_helpers_refuse_anything_outside_the_reserved_namespace() -> None:
    """Round-trip the tag grammar and refuse a foreign or malformed tag."""
    assert parse_candidate_tag(candidate_tag("4242")) == "4242"

    with pytest.raises(ReleaseCandidateError):
        parse_candidate_tag("evidence-smoke-4242")
    with pytest.raises(ReleaseCandidateError):
        candidate_tag("not-a-run-id")
    with pytest.raises(ReleaseCandidateError):
        candidate_tag("0")


def test_the_module_exports_its_public_surface() -> None:
    """Everything a consumer needs is public, so no caller reaches into a private name."""
    for name in ("ReleaseCandidate", "seal_candidate", "load_candidate", "candidate_tag", "load_soak_window"):
        assert name in release_candidate.__all__
