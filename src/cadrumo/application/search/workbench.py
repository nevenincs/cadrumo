"""Frontend-neutral search contracts for the operator workbench.

The search service consumes safe records that an application composition root
has already read and projected.  It does not know about repositories, network
clients, persistence records, or a frontend.  Searchable text is deliberately
separate from the result: callers provide only redacted labels and terms, so a
result can preserve a useful identity without carrying a ledger payload or
secret source value.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, field_validator, model_validator

from ...core.filing_year import FilingYear
from ...core.identifier_grammar import NamespacedId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.text_fold import fold_diacritics
from ..operator_actions.models import ActionReference

_STRICT_FROZEN = STRICT_FROZEN_CONFIG

# Search records carry identifiers and presentation-safe labels, never raw
# financial prose.  The bounds also keep one malformed projection from making
# an otherwise bounded search consume an unbounded amount of memory.
_MAX_SEARCH_ID_LENGTH = 160
_MAX_LABEL_LENGTH = 200
_MAX_TERM_LENGTH = 200
_MAX_SEARCH_RESULTS = 100
_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)


def _reject_control_characters(value: str) -> str:
    """Refuse every Unicode control character on a displayed string boundary."""
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("workbench search text cannot contain control characters")
    return value

_SafeSearchId = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=_MAX_SEARCH_ID_LENGTH),
    Field(validate_default=True),
]
_SafeLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=_MAX_LABEL_LENGTH),
    Field(validate_default=True),
]
_SafeSearchTerm = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=_MAX_TERM_LENGTH),
    Field(validate_default=True),
]


class WorkbenchSearchKind(StrEnum):
    """Human-facing family shown for one cross-domain search result."""

    DECLARATION = "declaration"
    MODELO = "modelo"
    REVISION = "revision"
    LEDGER = "ledger"
    MESSAGE = "message"
    FILING = "filing"
    HISTORY = "history"
    RECONCILIATION = "reconciliation"


class WorkbenchSearchStatus(StrEnum):
    """Closed status vocabulary preserved from an injected source projection."""

    UNKNOWN = "unknown"
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    NEEDS_ATTENTION = "needs_attention"
    NEEDS_REVIEW = "needs_review"
    READY = "ready"
    FILED = "filed"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    SUPERSEDED = "superseded"
    UNREAD = "unread"
    READ = "read"
    OPEN = "open"
    RESOLVED = "resolved"
    STALE = "stale"
    NOT_OBSERVED = "not_observed"
    LOCKED = "locked"
    UNAVAILABLE = "unavailable"


class WorkbenchDestinationAdmissionState(StrEnum):
    """Whether a result's owning destination can currently be opened."""

    AVAILABLE = "available"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


class WorkbenchModeloAddress(BaseModel):
    """Natural address for a declaration or filing when one exists."""

    model_config = _STRICT_FROZEN

    modelo: Annotated[str, StringConstraints(pattern=r"^\d{3}$")]
    filing_year: FilingYear
    period: Period

    @model_validator(mode="after")
    def _period_year_matches_address(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("Modelo address filing_year must match period.filing_year")
        return self


class WorkbenchDestinationAdmission(BaseModel):
    """Destination identity and truthful availability for a search result."""

    model_config = _STRICT_FROZEN

    destination: NamespacedId
    state: WorkbenchDestinationAdmissionState
    reason_code: NamespacedId | None = None

    @model_validator(mode="after")
    def _reason_matches_state(self) -> Self:
        if self.state is WorkbenchDestinationAdmissionState.AVAILABLE and self.reason_code is not None:
            raise ValueError("an available destination cannot carry an admission reason")
        if self.state is not WorkbenchDestinationAdmissionState.AVAILABLE and self.reason_code is None:
            raise ValueError("a non-available destination requires an admission reason")
        return self


class WorkbenchSearchDocument(BaseModel):
    """Safe, already-loaded projection accepted by the pure query service.

    ``search_terms`` are caller-supplied, presentation-safe terms.  They are
    not a request to load or inspect source data.  In particular, this record
    has no amount, account, raw description, secret, or arbitrary payload
    field; only stable identity and metadata cross into search results.
    """

    model_config = _STRICT_FROZEN

    stable_id: _SafeSearchId
    kind: WorkbenchSearchKind
    source: NamespacedId
    label: _SafeLabel
    search_terms: tuple[_SafeSearchTerm, ...] = ()
    address: WorkbenchModeloAddress | None = None
    status: WorkbenchSearchStatus
    admission: WorkbenchDestinationAdmission
    action: ActionReference | None = None

    @field_validator("stable_id", "label", mode="after")
    @classmethod
    def _reject_control_characters(cls, value: str) -> str:
        return _reject_control_characters(value)

    @field_validator("search_terms")
    @classmethod
    def _canonicalize_terms(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if any(_reject_control_characters(term) != term for term in value):
            raise AssertionError("control-character validation changed a search term")
        folded: dict[str, str] = {}
        for term in value:
            folded.setdefault(_normalize_text(term), term)
        return tuple(folded[key] for key in sorted(folded))

    @model_validator(mode="after")
    def _search_document_is_addressable(self) -> Self:
        addressed_kinds = {
            WorkbenchSearchKind.DECLARATION,
            WorkbenchSearchKind.MODELO,
            WorkbenchSearchKind.REVISION,
            WorkbenchSearchKind.FILING,
            WorkbenchSearchKind.HISTORY,
        }
        if self.kind in addressed_kinds and self.address is None:
            raise ValueError(f"{self.kind.value} search documents require a Modelo address")
        if self.admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE and self.action is not None:
            raise ValueError("a non-available destination cannot carry an actionable reference")
        return self


class WorkbenchSearchRequest(BaseModel):
    """Strict immutable request for one bounded workbench search."""

    model_config = _STRICT_FROZEN

    query: _SafeSearchTerm
    limit: Annotated[int, Field(gt=0, le=_MAX_SEARCH_RESULTS)] = 20

    @field_validator("query")
    @classmethod
    def _query_has_searchable_content(cls, value: str) -> str:
        _reject_control_characters(value)
        normalized = _normalize_text(value)
        if not normalized:
            raise ValueError("search query must contain searchable text")
        return value


class WorkbenchSearchResult(BaseModel):
    """One ranked result containing only safe cross-domain metadata."""

    model_config = _STRICT_FROZEN

    stable_id: _SafeSearchId
    kind: WorkbenchSearchKind
    source: NamespacedId
    label: _SafeLabel
    address: WorkbenchModeloAddress | None = None
    status: WorkbenchSearchStatus
    admission: WorkbenchDestinationAdmission
    action: ActionReference | None = None
    rank: NonNegativeInt
    score: float = Field(gt=0.0, allow_inf_nan=False)

    @field_validator("stable_id", "label")
    @classmethod
    def _result_text_has_no_control_characters(cls, value: str) -> str:
        return _reject_control_characters(value)

    @model_validator(mode="after")
    def _action_matches_admission(self) -> Self:
        if self.admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE and self.action is not None:
            raise ValueError("a non-available destination cannot carry an actionable reference")
        return self


class WorkbenchSearchResponse(BaseModel):
    """Bounded, immutable response from :class:`WorkbenchSearchService`."""

    model_config = _STRICT_FROZEN

    query: _SafeSearchTerm
    results: tuple[WorkbenchSearchResult, ...] = ()
    total_matches: NonNegativeInt = 0

    @field_validator("query")
    @classmethod
    def _response_query_has_no_control_characters(cls, value: str) -> str:
        return _reject_control_characters(value)

    @model_validator(mode="after")
    def _result_page_is_canonical(self) -> Self:
        if self.total_matches < len(self.results):
            raise ValueError("total_matches cannot be smaller than the returned result count")
        ranks = tuple(result.rank for result in self.results)
        if ranks != tuple(range(len(self.results))):
            raise ValueError("search result ranks must be contiguous and zero-based")
        return self


def _normalize_text(value: str) -> str:
    """Fold case, accents and whitespace into one deterministic match form."""
    return " ".join(fold_diacritics(value).casefold().split())


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(_WORD_PATTERN.findall(_normalize_text(value)))


def _document_search_text(document: WorkbenchSearchDocument) -> tuple[str, str, tuple[str, ...]]:
    """Return normalized phrase, title and term tokens used by the scorer."""
    title = _normalize_text(document.label)
    terms = tuple(_normalize_text(term) for term in document.search_terms)
    if document.address is not None:
        terms += (
            _normalize_text(document.address.modelo),
            str(document.address.filing_year),
            _normalize_text(document.address.period.registry_token),
        )
    return " ".join((title, *terms)), title, _tokens(" ".join((title, *terms)))


def _score_document(document: WorkbenchSearchDocument, query: str) -> float | None:
    """Return a deterministic relevance score, or ``None`` when unmatched."""
    normalized_query = _normalize_text(query)
    query_tokens = _tokens(normalized_query)
    if not query_tokens:
        return None
    phrase, title, document_tokens = _document_search_text(document)
    if normalized_query not in phrase and not all(token in document_tokens for token in query_tokens):
        return None

    title_tokens = _tokens(title)
    score = 0.0
    if normalized_query == title:
        score += 200.0
    elif normalized_query in title:
        score += 100.0
    elif normalized_query in phrase:
        score += 40.0
    for token in query_tokens:
        if token in title_tokens:
            score += 20.0
        elif any(candidate.startswith(token) for candidate in title_tokens):
            score += 10.0
        elif token in document_tokens:
            score += 5.0
        else:
            score += 1.0
    return score


class WorkbenchSearchService:
    """Pure cross-domain search over injected safe projections."""

    def __init__(self, documents: Sequence[WorkbenchSearchDocument]) -> None:
        """Capture an immutable document snapshot and refuse duplicate identities."""
        snapshot = tuple(documents)
        if any(not isinstance(document, WorkbenchSearchDocument) for document in snapshot):
            raise TypeError("workbench search requires WorkbenchSearchDocument projections")
        stable_ids = tuple(document.stable_id for document in snapshot)
        if len(set(stable_ids)) != len(stable_ids):
            raise ValueError("workbench search projections require unique stable identities")
        self._documents = tuple(sorted(snapshot, key=lambda document: document.stable_id))

    @property
    def documents(self) -> tuple[WorkbenchSearchDocument, ...]:
        """Return the isolated injected projection snapshot."""
        return self._documents

    def search(self, request: WorkbenchSearchRequest) -> WorkbenchSearchResponse:
        """Return deterministic ranked results capped by ``request.limit``."""
        if not isinstance(request, WorkbenchSearchRequest):
            raise TypeError("workbench search requires WorkbenchSearchRequest")
        ranked: list[tuple[float, WorkbenchSearchDocument]] = []
        for document in self._documents:
            score = _score_document(document, request.query)
            if score is not None:
                ranked.append((score, document))
        ranked.sort(key=lambda item: (-item[0], item[1].stable_id))
        results = tuple(
            WorkbenchSearchResult(
                stable_id=document.stable_id,
                kind=document.kind,
                source=document.source,
                label=document.label,
                address=document.address,
                status=document.status,
                admission=document.admission,
                action=document.action,
                rank=rank,
                score=score,
            )
            for rank, (score, document) in enumerate(ranked[: request.limit])
        )
        return WorkbenchSearchResponse(query=request.query, results=results, total_matches=len(ranked))


__all__ = [
    "WorkbenchDestinationAdmission",
    "WorkbenchDestinationAdmissionState",
    "WorkbenchModeloAddress",
    "WorkbenchSearchDocument",
    "WorkbenchSearchKind",
    "WorkbenchSearchRequest",
    "WorkbenchSearchResponse",
    "WorkbenchSearchResult",
    "WorkbenchSearchService",
    "WorkbenchSearchStatus",
]
