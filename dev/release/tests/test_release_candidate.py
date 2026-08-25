"""Behavioural proof for the sealed release candidate and its soak window.

The load-bearing properties here are all about a record that must survive two
to three days outside any running process: it round-trips exactly, it refuses a
payload that lost a field rather than defaulting one back, its deadline comes
from the declared policy rather than a literal, and its tag namespace is one the
evidence garbage collector cannot reach.
"""

from __future__ import annotations

import json
import stat
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from ..._paths import REPO_ROOT
from .. import release_candidate
from ..release_candidate import (
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

_REPO_ROOT = REPO_ROOT
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
    # Deliberately a key no field claims. `soak_hours_override` was used here
    # before the hotfix carve-out landed and would now be ACCEPTED as a real
    # field - the test would still pass, via the carve-out validator rather
    # than via extra="forbid", asserting something it no longer means.
    payload["definitely_not_a_candidate_field"] = 1
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


def _write_recording_gh(bin_dir: Path, *, stdout: str = "", log: Path | None = None) -> Path:
    """Write a real `gh` stub that records its argv and emits fixed output.

    A recording stub rather than a mock: the transport's correctness is the
    exact argv it builds (draft, clobber, repo pin), so the test has to observe
    a real process invocation to assert anything meaningful about it.
    """
    bin_dir.mkdir(parents=True, exist_ok=True)
    if sys.platform.startswith("win"):
        script = bin_dir / "gh.bat"
        lines = ["@echo off"]
        if log is not None:
            lines.append(f'echo %* >> "{log}"')
        for line in stdout.splitlines():
            lines.append(f"echo {line}")
        script.write_text("\r\n".join(lines) + "\r\n", encoding="utf-8")
    else:
        script = bin_dir / "gh"
        body = ["#!/usr/bin/env bash"]
        if log is not None:
            body.append(f'echo "$@" >> "{log}"')
        body.append(f"cat <<'OUT'\n{stdout}\nOUT")
        script.write_text("\n".join(body) + "\n", encoding="utf-8")
        script.chmod(script.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return script


def test_publishing_a_new_candidate_creates_one_draft_in_the_reserved_namespace(tmp_path: Path) -> None:
    """A first seal creates a DRAFT release carrying the record as its asset."""
    log = tmp_path / "argv.log"
    script = _write_recording_gh(tmp_path / "bin", stdout="", log=log)
    candidate = _fully_populated()

    tag = release_candidate.publish_candidate(
        candidate,
        repository="nevenincs/cadrumo",
        staging_directory=tmp_path / "stage",
        gh_executable=str(script),
    )

    assert tag == "release-candidate-4242"
    recorded = log.read_text(encoding="utf-8")
    assert "release create release-candidate-4242" in recorded
    # A candidate is never a publishable release: it must be a draft, and it
    # must be pinned to this repository rather than the ambient default.
    assert "--draft" in recorded
    assert "--repo nevenincs/cadrumo" in recorded
    # The record itself rides as the asset; without it the draft is an empty
    # marker and the promoter has nothing to read days later.
    assert release_candidate.CANDIDATE_ASSET_NAME in recorded


def test_resealing_the_same_candidate_clobbers_rather_than_minting_a_second_draft(tmp_path: Path) -> None:
    """Idempotence against its own prior attempt.

    Two drafts sharing one tag make which assets a later download resolves
    undefined - the same hazard the evidence transport refuses on - so a
    re-seal must upload over the existing draft, never create another.
    """
    existing = json.dumps({"tag_name": "release-candidate-4242", "draft": True, "created_at": "2026-08-02T00:00:00Z"})
    log = tmp_path / "argv.log"
    script = _write_recording_gh(tmp_path / "bin", stdout=existing, log=log)

    release_candidate.publish_candidate(
        _fully_populated(),
        repository="nevenincs/cadrumo",
        staging_directory=tmp_path / "stage",
        gh_executable=str(script),
    )

    recorded = log.read_text(encoding="utf-8")
    assert "release upload release-candidate-4242" in recorded
    assert "--clobber" in recorded
    assert "release create" not in recorded


def test_listing_sealed_candidates_ignores_evidence_and_published_releases(tmp_path: Path) -> None:
    """The forge listing is filtered to drafts inside the reserved namespace."""
    payload = "\n".join(
        json.dumps(record)
        for record in (
            {"tag_name": "release-candidate-4242", "draft": True, "created_at": "2026-08-02T00:00:00Z"},
            {"tag_name": "evidence-smoke-4242", "draft": True, "created_at": "2026-08-02T00:00:00Z"},
            {"tag_name": "v1.2.3", "draft": False, "created_at": "2026-08-02T00:00:00Z"},
        )
    )
    script = _write_recording_gh(tmp_path / "bin", stdout=payload)

    tags = release_candidate.list_sealed_candidate_tags(
        repository="nevenincs/cadrumo",
        gh_executable=str(script),
    )

    assert tags == ("release-candidate-4242",)


def test_fetching_refuses_a_tag_outside_the_reserved_namespace(tmp_path: Path) -> None:
    """The namespace check happens BEFORE any download.

    Ordering matters: a promoter that downloaded first would treat any draft's
    asset as a candidate, so a foreign tag must be refused without a fetch.
    """
    script = _write_recording_gh(tmp_path / "bin", stdout="")

    with pytest.raises(ReleaseCandidateError):
        release_candidate.fetch_candidate(
            "evidence-smoke-4242",
            repository="nevenincs/cadrumo",
            download_directory=tmp_path / "dl",
            gh_executable=str(script),
        )
