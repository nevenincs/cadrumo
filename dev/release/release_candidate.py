"""The sealed release candidate and its machine-held soak window.

A release candidate must survive a wall-clock wait of 48 to 72 hours. No
workflow run spans that window, so the state cannot live in a job, in a job
output, or in the working tree: it has to be durable, external, and readable by
a later, unrelated process.

The transport is the draft release this repository already uses to carry
evidence rows. What is deliberately NOT reused is the evidence TAG namespace.
``dev.packaging.evidence_release.plan_evidence_gc`` collects drafts inside
``evidence-<lane>-<run_id>``, keeping only the newest K per lane, and a
candidate sits sealed for two to three days -- long enough for K later
campaigns to push it out of the retention window and delete the one artifact
the soak depends on. A candidate that is garbage-collected mid-window does not
publish late; it never publishes at all, and nothing reports why.

Candidates therefore live under ``release-candidate-<run_id>``, which
``EVIDENCE_TAG_RE`` does not match, so the GC ignores them by construction
rather than by configuration. That property is load-bearing and is pinned by a
test: enrolling this namespace as an ``EvidenceLane`` would silently make
in-flight soak state collectable.

The soak DURATION is not defined here. It is read from the release checklist,
which is the accepted authority for the window and its hotfix terms, so moving
the wait from a human to the pipeline does not quietly fork the policy.

See Also:
    :func:`seal_candidate`
        Mint a candidate and compute its deadline from the checklist window.
    :func:`candidate_tag`
        The reserved, GC-exempt tag namespace.
    :class:`ReleaseCandidate`
        The persisted record itself.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Final

import yaml
from pydantic import BaseModel, ConfigDict, Field

_UTF_8: Final[str] = "utf-8"
_SHA256_PATTERN: Final[str] = r"^[0-9a-f]{64}$"
_COMMIT_PATTERN: Final[str] = r"^[0-9a-f]{40}$"
_RUN_ID_PATTERN: Final[str] = r"^[1-9][0-9]*$"

#: The candidate record's asset name on its draft release.
CANDIDATE_ASSET_NAME: Final[str] = "release-candidate.json"

#: Reserved tag namespace for sealed candidates. Deliberately DISJOINT from
#: ``EVIDENCE_TAG_RE`` so the evidence GC cannot collect an in-soak candidate.
CANDIDATE_TAG_RE: Final[re.Pattern[str]] = re.compile(r"^release-candidate-([1-9][0-9]*)$")

_CHECKLIST_RELATIVE_PATH: Final[str] = "docs/_release_checklist.yaml"


class ReleaseCandidateError(ValueError):
    """A sealing, parsing, or window invariant failed; the message names the mismatch."""


class SoakWindow(BaseModel):
    """The release-candidate soak window, as declared by the release checklist."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    minimum_hours: int = Field(gt=0)
    maximum_hours: int = Field(gt=0)

    def deadline_from(self, opened_at: datetime) -> datetime:
        """Return the earliest instant at which a candidate opened then may publish."""
        return opened_at + timedelta(hours=self.minimum_hours)


def load_soak_window(repo_root: Path) -> SoakWindow:
    """Read the soak window from the release checklist.

    The checklist is the single authority for the duration and is validated in
    full elsewhere against the same file, so this reader deliberately parses
    only the two fields it needs and refuses rather than defaulting: a soak
    window that silently fell back to a literal would be a second authority
    over the policy this module exists to honour.
    """
    path = repo_root / _CHECKLIST_RELATIVE_PATH
    try:
        document = yaml.safe_load(path.read_text(encoding=_UTF_8))
    except OSError as error:
        raise ReleaseCandidateError(f"release checklist unreadable at {path}: {error}") from error
    if not isinstance(document, dict) or not isinstance(soak := document.get("soak"), dict):
        raise ReleaseCandidateError(f"release checklist at {path} declares no soak section")
    try:
        return SoakWindow(
            minimum_hours=soak["minimum_hours"],
            maximum_hours=soak["maximum_hours"],
        )
    except KeyError as error:
        raise ReleaseCandidateError(f"release checklist soak section is missing {error}") from error


class ReleaseCandidate(BaseModel):
    """One sealed, immutable release candidate awaiting its soak deadline.

    Every field the publication dispatch needs is recorded here, because the
    promoter that reads this record runs days later in a different process and
    has no other source for them. A candidate that recorded only its cohort
    would force the promoter to re-derive the run ids, which is the hand
    transcription this pipeline removed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    cohort_id: str = Field(pattern=_SHA256_PATTERN)
    version: str = Field(min_length=1)
    source_commit: str = Field(pattern=_COMMIT_PATTERN)
    packaging_run_id: str = Field(pattern=_RUN_ID_PATTERN)
    scoop_run_id: str = Field(default="")
    homebrew_run_id: str = Field(default="")
    claude_evidence_release: str = Field(default="")
    claimed_channels: tuple[str, ...]
    dry_run: bool
    soak_opened_at: datetime
    soak_deadline: datetime

    @property
    def tag(self) -> str:
        """Return this candidate's reserved draft tag."""
        return candidate_tag(self.packaging_run_id)

    def window_elapsed(self, *, now: datetime) -> bool:
        """Whether the soak window has closed at ``now``.

        The comparison is inclusive at the boundary: a candidate whose deadline
        is exactly ``now`` has served its full declared minimum, and refusing it
        would make the window silently longer than the policy states.
        """
        return now >= self.soak_deadline


def candidate_tag(run_id: str) -> str:
    """Return the reserved draft tag for one sealed candidate."""
    if re.fullmatch(_RUN_ID_PATTERN, run_id) is None:
        raise ReleaseCandidateError(f"run id must be one positive workflow run id, got {run_id!r}")
    return f"release-candidate-{run_id}"


def parse_candidate_tag(tag: str) -> str:
    """Return the run id carried by a reserved candidate tag, refusing anything else."""
    match = CANDIDATE_TAG_RE.fullmatch(tag)
    if match is None:
        raise ReleaseCandidateError(
            f"tag {tag!r} is outside the reserved candidate namespace {CANDIDATE_TAG_RE.pattern!r}",
        )
    return match.group(1)


def seal_candidate(
    *,
    cohort_id: str,
    version: str,
    source_commit: str,
    packaging_run_id: str,
    claimed_channels: tuple[str, ...],
    dry_run: bool,
    window: SoakWindow,
    opened_at: datetime,
    scoop_run_id: str = "",
    homebrew_run_id: str = "",
    claude_evidence_release: str = "",
) -> ReleaseCandidate:
    """Mint a sealed candidate whose deadline is COMPUTED from the checklist window.

    The deadline is stored rather than recomputed at read time. A promoter that
    recomputed it would silently re-date every in-flight candidate the moment
    the checklist changed, which would either publish a candidate early or
    extend one already served -- both by editing a documentation file.
    """
    if opened_at.tzinfo is None:
        raise ReleaseCandidateError("soak opened_at must be timezone-aware; a naive instant has no deadline")
    opened = opened_at.astimezone(UTC)
    return ReleaseCandidate(
        cohort_id=cohort_id,
        version=version,
        source_commit=source_commit,
        packaging_run_id=packaging_run_id,
        scoop_run_id=scoop_run_id,
        homebrew_run_id=homebrew_run_id,
        claude_evidence_release=claude_evidence_release,
        claimed_channels=claimed_channels,
        dry_run=dry_run,
        soak_opened_at=opened,
        soak_deadline=window.deadline_from(opened),
    )


def write_candidate(candidate: ReleaseCandidate, output: Path) -> Path:
    """Serialize a candidate to its asset file."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(candidate.model_dump_json(indent=2), encoding=_UTF_8)
    return output


def load_candidate(path: Path) -> ReleaseCandidate:
    """Load a candidate, refusing any payload that is not complete and well-typed.

    Strict and ``extra="forbid"``: a truncated or hand-edited record is a
    refusal, never a partially-populated candidate. The soak decision is made
    from this payload alone, so a missing deadline must not be reconstructable
    by a default.
    """
    try:
        return ReleaseCandidate.model_validate_json(path.read_text(encoding=_UTF_8))
    except OSError as error:
        raise ReleaseCandidateError(f"candidate record unreadable at {path}: {error}") from error


def candidate_tags_in(releases: list[dict[str, object]]) -> tuple[str, ...]:
    """Return every DRAFT release tag inside the reserved candidate namespace.

    Pure over an already-fetched payload so the selection is testable without a
    process. A published (non-draft) release sharing the shape is ignored: a
    sealed candidate is always a draft, and trusting a published one would let
    anything that can create a release inject a promotable candidate.
    """
    return tuple(
        str(record.get("tag_name", ""))
        for record in releases
        if record.get("draft") is True and CANDIDATE_TAG_RE.fullmatch(str(record.get("tag_name", ""))) is not None
    )


__all__ = [
    "CANDIDATE_ASSET_NAME",
    "CANDIDATE_TAG_RE",
    "ReleaseCandidate",
    "ReleaseCandidateError",
    "SoakWindow",
    "candidate_tag",
    "candidate_tags_in",
    "load_candidate",
    "load_soak_window",
    "parse_candidate_tag",
    "seal_candidate",
    "write_candidate",
]
