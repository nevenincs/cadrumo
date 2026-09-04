"""Synonym-candidate mining and ratification queue gates.

The live embedding pass is intentionally outside CI: it can run on the dev GPU
box and export cosine observations. This module owns the deterministic part that
CI can enforce forever:

* relative-cosine validation over mined observations,
* a committed human-review queue with explicit reasons,
* gates proving ratified candidates are landed in the Handbook, and
* gates proving proposed/rejected candidates never reach the shipped query
  vocabulary.

Only plain strings, cosine numbers, decisions, and reasons are persisted. No
vectors, sparse weights, SPLADE data, raw paths, or snippets are accepted.
"""

from __future__ import annotations

import json
import re
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Final

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from cadrumo.core.external_constants import OutputLanguage

from ..._paths import UTF_8
from ..terminology_handbook import TerminologyHandbook, load_terminology_handbook
from ..terminology_handbook.enums import TermStatus
from ..terminology_handbook.errors import TerminologyLoadError
from ._sweep import enumerate_query_vocabulary

_UTF_8: Final[str] = UTF_8

__all__ = [
    "DEFAULT_RELATIVE_COSINE_THRESHOLDS",
    "RatificationAction",
    "RatificationStatus",
    "RatificationValidationResult",
    "RatificationViolation",
    "RelativeCosineThresholds",
    "SynonymCandidateEntry",
    "SynonymCandidateObservation",
    "SynonymRatificationQueue",
    "load_synonym_ratification_queue",
    "mine_synonym_candidates",
    "synonym_ratification_queue_path",
    "validate_ratification_queue",
]

_ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
_ConceptId = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=64)]
_Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=12, max_length=800)]
_Whitespace = re.compile(r"\s+")


class RatificationAction(StrEnum):
    """How a ratified candidate must land in the Handbook."""

    ADMITTED_TERM = "admitted_term"
    HIDDEN_SEARCH_FORM = "hidden_search_form"


class RatificationStatus(StrEnum):
    """Human-review state for a mined synonym candidate."""

    PROPOSED = "proposed"
    RATIFIED = "ratified"
    REJECTED = "rejected"


class RelativeCosineThresholds(BaseModel):
    """Relative-cosine thresholds used to screen mined candidates."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    minimum_cosine: float = Field(default=0.78, ge=0.0, le=1.0)
    minimum_margin: float = Field(default=0.05, ge=0.0, le=1.0)
    minimum_ratio: float = Field(default=1.08, ge=1.0)


DEFAULT_RELATIVE_COSINE_THRESHOLDS = RelativeCosineThresholds()


class SynonymCandidateObservation(BaseModel):
    """One raw mined candidate from an embedding run, without review state."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    concept_id: _ConceptId
    source_term: _ShortText
    candidate: _ShortText
    language: OutputLanguage
    action: RatificationAction
    cosine: float = Field(ge=0.0, le=1.0)
    nearest_competing_cosine: float = Field(ge=0.0, le=1.0)
    competing_concept_id: _ConceptId | None = None

    @field_validator("language", mode="before")
    @classmethod
    def _parse_language(cls, value: object) -> object:
        if isinstance(value, OutputLanguage):
            return value
        if isinstance(value, str):
            return OutputLanguage(value)
        return value

    @field_validator("action", mode="before")
    @classmethod
    def _parse_action(cls, value: object) -> object:
        if isinstance(value, RatificationAction):
            return value
        if isinstance(value, str):
            return RatificationAction(value)
        return value

    @property
    def relative_margin(self) -> float:
        """Candidate cosine minus the nearest competing concept cosine."""
        return self.cosine - self.nearest_competing_cosine

    @property
    def relative_ratio(self) -> float:
        """Candidate cosine divided by the nearest competing concept cosine."""
        if self.nearest_competing_cosine == 0.0:
            return float("inf")
        return self.cosine / self.nearest_competing_cosine


class SynonymCandidateEntry(SynonymCandidateObservation):
    """One committed ratification-queue row."""

    status: RatificationStatus
    review_reason: _Reason | None = None
    reviewed_at: date | None = None

    @field_validator("status", mode="before")
    @classmethod
    def _parse_status(cls, value: object) -> object:
        if isinstance(value, RatificationStatus):
            return value
        if isinstance(value, str):
            return RatificationStatus(value)
        return value

    @field_validator("reviewed_at", mode="before")
    @classmethod
    def _parse_reviewed_at(cls, value: object) -> object:
        if isinstance(value, date) or value is None:
            return value
        if isinstance(value, str):
            return date.fromisoformat(value)
        return value

    @model_validator(mode="after")
    def _review_state_is_consistent(self) -> SynonymCandidateEntry:
        if self.status in (RatificationStatus.RATIFIED, RatificationStatus.REJECTED) and (
            self.review_reason is None or self.reviewed_at is None
        ):
            raise ValueError(f"{self.concept_id}:{self.candidate}: reviewed decisions require reason and date")
        if self.status is RatificationStatus.PROPOSED and (
            self.review_reason is not None or self.reviewed_at is not None
        ):
            raise ValueError(f"{self.concept_id}:{self.candidate}: proposed candidates must not carry review fields")
        return self


class SynonymRatificationQueue(BaseModel):
    """Committed queue of mined synonym candidates and human decisions."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    schema_version: int = Field(default=1, ge=1)
    generated_by: _ShortText
    thresholds: RelativeCosineThresholds = Field(default=DEFAULT_RELATIVE_COSINE_THRESHOLDS)
    entries: tuple[SynonymCandidateEntry, ...] = Field(default=())

    @field_validator("entries", mode="before")
    @classmethod
    def _parse_entries(cls, value: object) -> object:
        if isinstance(value, list):
            return tuple(value)
        return value

    @model_validator(mode="after")
    def _unique_candidate_rows(self) -> SynonymRatificationQueue:
        keys = [(entry.concept_id, _normalise(entry.candidate), entry.action, entry.language) for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("synonym ratification queue contains duplicate candidate rows")
        return self


class RatificationViolation(BaseModel):
    """One queue validation failure."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    concept_id: _ConceptId
    candidate: _ShortText
    reason: _ShortText


class RatificationValidationResult(BaseModel):
    """Validation result for a ratification queue."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    violations: tuple[RatificationViolation, ...] = Field(default=())

    @property
    def passed(self) -> bool:
        """Whether the queue is valid."""
        return not self.violations


def synonym_ratification_queue_path() -> Path:
    """Return the dev-local synonym-ratification queue path.

    A build-time review queue read by this harness and by no runtime
    consumer - so it lives beside the harness under ``dev/`` rather than in
    the shipped ``_data`` tree.
    """
    return Path(__file__).resolve().parent / "ratification" / "synonym-candidates.json"


def load_synonym_ratification_queue(path: Path | None = None) -> SynonymRatificationQueue:
    """Load and strictly validate the committed synonym-ratification queue."""
    target = path if path is not None else synonym_ratification_queue_path()
    try:
        payload = json.loads(target.read_text(encoding=_UTF_8))
    except OSError as exc:
        raise TerminologyLoadError(f"{target}: synonym ratification queue cannot be read: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise TerminologyLoadError(f"{target}: synonym ratification queue is not valid JSON: {exc}") from exc
    try:
        return SynonymRatificationQueue.model_validate(payload)
    except ValueError as exc:
        raise TerminologyLoadError(f"{target}: synonym ratification queue is invalid: {exc}") from exc


def mine_synonym_candidates(
    observations: tuple[SynonymCandidateObservation, ...],
    *,
    handbook: TerminologyHandbook | None = None,
    thresholds: RelativeCosineThresholds = DEFAULT_RELATIVE_COSINE_THRESHOLDS,
) -> SynonymRatificationQueue:
    """Filter raw mined observations into a proposed ratification queue.

    Observations must pass the absolute cosine floor and the relative-cosine
    margin/ratio checks. Existing Handbook terms and hidden forms are skipped,
    because they are already shipped vocabulary rather than new candidates.
    """
    resolved = handbook if handbook is not None else load_terminology_handbook()
    entries: list[SynonymCandidateEntry] = []
    for row in observations:
        if row.concept_id not in resolved.by_id:
            continue
        if not _passes_relative_cosine(row, thresholds):
            continue
        if _already_shipped(row, resolved):
            continue
        if _normalise(row.source_term) == _normalise(row.candidate):
            continue
        entries.append(
            SynonymCandidateEntry(
                concept_id=row.concept_id,
                source_term=row.source_term,
                candidate=row.candidate,
                language=row.language,
                action=row.action,
                cosine=row.cosine,
                nearest_competing_cosine=row.nearest_competing_cosine,
                competing_concept_id=row.competing_concept_id,
                status=RatificationStatus.PROPOSED,
            ),
        )
    entries.sort(key=lambda entry: (entry.concept_id, entry.candidate.casefold(), entry.action.value))
    return SynonymRatificationQueue(
        generated_by="dev.docs.terminology._synonym_mining.mine_synonym_candidates",
        thresholds=thresholds,
        entries=tuple(entries),
    )


def validate_ratification_queue(
    queue: SynonymRatificationQueue,
    *,
    handbook: TerminologyHandbook | None = None,
) -> RatificationValidationResult:
    """Validate the queue against the current Handbook and shipped vocabulary."""
    resolved = handbook if handbook is not None else load_terminology_handbook()
    shipped = {(query.concept_id, _normalise(query.query)) for query in enumerate_query_vocabulary(resolved)}
    violations: list[RatificationViolation] = []
    for entry in queue.entries:
        concept = resolved.by_id.get(entry.concept_id)
        if concept is None:
            violations.append(_violation(entry, "concept is not enrolled in the Handbook"))
            continue
        if entry.status is not RatificationStatus.REJECTED and not _passes_relative_cosine(entry, queue.thresholds):
            violations.append(_violation(entry, "candidate does not pass relative-cosine thresholds"))
        if entry.status is RatificationStatus.RATIFIED:
            if not _ratified_landed(entry, resolved):
                violations.append(_violation(entry, f"ratified {entry.action.value} has not landed in the Handbook"))
            if (entry.concept_id, _normalise(entry.candidate)) not in shipped:
                violations.append(_violation(entry, "ratified candidate is absent from the shipped query vocabulary"))
        else:
            if (entry.concept_id, _normalise(entry.candidate)) in shipped:
                violations.append(_violation(entry, "unratified candidate is present in the shipped query vocabulary"))
    return RatificationValidationResult(violations=tuple(violations))


def _passes_relative_cosine(
    row: SynonymCandidateObservation,
    thresholds: RelativeCosineThresholds,
) -> bool:
    return (
        row.cosine >= thresholds.minimum_cosine
        and row.relative_margin >= thresholds.minimum_margin
        and row.relative_ratio >= thresholds.minimum_ratio
    )


def _already_shipped(row: SynonymCandidateObservation, handbook: TerminologyHandbook) -> bool:
    return _candidate_in_query_vocabulary(row.concept_id, row.candidate, handbook)


def _candidate_in_query_vocabulary(concept_id: str, candidate: str, handbook: TerminologyHandbook) -> bool:
    normalised = _normalise(candidate)
    return any(
        query.concept_id == concept_id and _normalise(query.query) == normalised
        for query in enumerate_query_vocabulary(handbook, concept_ids={concept_id})
    )


def _ratified_landed(entry: SynonymCandidateEntry, handbook: TerminologyHandbook) -> bool:
    concept = handbook.concept(entry.concept_id)
    candidate = _normalise(entry.candidate)
    for section in concept.languages:
        if section.language is not entry.language:
            continue
        for term in section.terms:
            if entry.action is RatificationAction.ADMITTED_TERM:
                if term.term_status is TermStatus.ADMITTED and _normalise(term.label) == candidate:
                    return True
            elif _normalise(entry.candidate) in {_normalise(form) for form in term.hidden_search_forms}:
                return True
    return False


def _violation(entry: SynonymCandidateEntry, reason: str) -> RatificationViolation:
    return RatificationViolation(concept_id=entry.concept_id, candidate=entry.candidate, reason=reason)


def _normalise(value: str) -> str:
    return _Whitespace.sub(" ", value.strip()).casefold()
