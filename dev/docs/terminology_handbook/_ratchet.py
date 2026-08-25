"""Curation-backlog ratchet for the Terminology Handbook.

The ratchet turns the audit report's backlog counters into a standing gate:
draft concepts and uncurated short descriptions may stay flat or shrink, but
they may not grow without an explicit baseline update in the committed data
file. This mirrors the locale translation-honesty discipline while keeping the
terminology backlog honest during incremental curation.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from cadrumo.core.external_constants import UTF_8_ENCODING

from ._curation import AuditReport, audit_handbook
from .errors import TerminologyLoadError

__all__ = [
    "CurationBacklogRatchetBaseline",
    "CurationBacklogRatchetResult",
    "check_curation_backlog_ratchet",
    "load_curation_backlog_ratchet_baseline",
    "terminology_ratchet_baseline_path",
]


@dataclass(frozen=True, slots=True)
class CurationBacklogRatchetBaseline:
    """Committed ceiling for the terminology curation backlog."""

    draft_count: int
    empty_short_description_count: int
    recorded_at: str
    review_cadence: str
    source: str


@dataclass(frozen=True, slots=True)
class CurationBacklogRatchetResult:
    """Comparison between the current audit report and the committed baseline."""

    report: AuditReport
    baseline: CurationBacklogRatchetBaseline

    @property
    def draft_delta(self) -> int:
        """Current draft count minus the committed draft-count ceiling."""
        return self.report.draft_count - self.baseline.draft_count

    @property
    def empty_short_description_delta(self) -> int:
        """Current uncurated-short-description count minus the committed ceiling."""
        return len(self.report.empty_short_description) - self.baseline.empty_short_description_count

    @property
    def violations(self) -> tuple[str, ...]:
        """Human-readable ratchet violations; empty means the gate passed."""
        found: list[str] = []
        if self.draft_delta > 0:
            found.append(
                f"draft_count grew from {self.baseline.draft_count} to {self.report.draft_count}",
            )
        if self.empty_short_description_delta > 0:
            found.append(
                "empty_short_description count grew from "
                f"{self.baseline.empty_short_description_count} to {len(self.report.empty_short_description)}",
            )
        return tuple(found)

    @property
    def passed(self) -> bool:
        """Whether the current backlog is flat or improved against the baseline."""
        return not self.violations


def terminology_ratchet_baseline_path() -> Path:
    """Return the dev-local curation-ratchet baseline path.

    A curation-backlog gate baseline read by this harness and by no runtime
    consumer - so it lives beside the harness under ``dev/`` rather than in
    the shipped ``_data`` tree.
    """
    return Path(__file__).resolve().parent / "curation-ratchet.json"


def load_curation_backlog_ratchet_baseline(
    baseline_path: Path | None = None,
) -> CurationBacklogRatchetBaseline:
    """Load the committed terminology curation-backlog baseline.

    Args:
        baseline_path: Optional path for tests or staged reviews. Defaults to
            the bundled baseline.

    Raises:
        TerminologyLoadError: The baseline file is missing, malformed, or
            carries invalid counter values.
    """
    path = baseline_path if baseline_path is not None else terminology_ratchet_baseline_path()
    try:
        raw = json.loads(path.read_text(encoding=UTF_8_ENCODING))
    except OSError as exc:
        raise TerminologyLoadError(f"{path}: curation ratchet baseline cannot be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TerminologyLoadError(f"{path}: curation ratchet baseline is not valid JSON: {exc}") from exc

    required = ("draft_count", "empty_short_description_count", "recorded_at", "review_cadence", "source")
    missing = [key for key in required if key not in raw]
    if missing:
        raise TerminologyLoadError(f"{path}: curation ratchet baseline missing key(s): {', '.join(missing)}")
    draft_count = _non_negative_int(path, raw["draft_count"], "draft_count")
    empty_short_description_count = _non_negative_int(
        path,
        raw["empty_short_description_count"],
        "empty_short_description_count",
    )
    return CurationBacklogRatchetBaseline(
        draft_count=draft_count,
        empty_short_description_count=empty_short_description_count,
        recorded_at=_non_empty_string(path, raw["recorded_at"], "recorded_at"),
        review_cadence=_non_empty_string(path, raw["review_cadence"], "review_cadence"),
        source=_non_empty_string(path, raw["source"], "source"),
    )


def check_curation_backlog_ratchet(
    *,
    concepts_dir: Path | None = None,
    baseline_path: Path | None = None,
) -> CurationBacklogRatchetResult:
    """Compare the current curation backlog against the committed baseline."""
    baseline = load_curation_backlog_ratchet_baseline(baseline_path)
    report = audit_handbook(concepts_dir)
    return CurationBacklogRatchetResult(report=report, baseline=baseline)


def _non_negative_int(path: Path, value: object, key: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise TerminologyLoadError(f"{path}: {key} must be a non-negative integer")
    return value


def _non_empty_string(path: Path, value: object, key: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise TerminologyLoadError(f"{path}: {key} must be a non-empty string")
    return value
