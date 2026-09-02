"""Frontend-neutral, redacted search contracts for the operator workbench.

The service searches an ephemeral in-memory snapshot injected by an application
composition root. It owns no repository, persistence, network, or frontend
dependency. Providers supply redacted display labels and SHA-256 token digests;
raw filing references, taxpayer identifiers, ledger descriptions, and other
source terms are therefore never retained in the snapshot or returned in a
result.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Sequence
from enum import StrEnum
from typing import Annotated, Self, cast

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, field_validator, model_validator

from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identifier_grammar import NamespacedId
from ...core.identity import FilingRecordId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.text_fold import fold_printed_phrase
from ...domain.calculations.registry.ids import RevisionId
from ...domain.modelos.codes import ModeloCode

_MAX_LABEL_LENGTH = 200
_MAX_OPERATOR_TERM_LENGTH = 200
_MAX_SEARCH_RESULTS = 100
_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)

_RedactedLabel = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=_MAX_LABEL_LENGTH),
]
_TransientQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=_MAX_OPERATOR_TERM_LENGTH),
]


def _reject_control_characters(value: str) -> str:
    """Refuse every Unicode control character on a human-readable boundary."""
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("workbench search text cannot contain control characters")
    return value


def _normalize_text(value: str) -> str:
    """Use the canonical case-before-accent printed-phrase normalization."""
    return fold_printed_phrase(value)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in _WORD_PATTERN.finditer(_normalize_text(value)))


def digest_operator_safe_tokens(*values: str) -> tuple[Hex64Str, ...]:
    """Hash caller-declared operator-safe terms into canonical search tokens.

    The helper normalizes case, accents, and whitespace with the canonical core
    printed-phrase primitive, then hashes individual word tokens. Callers must
    pass only terms approved for operator search. The returned tuple is sorted
    and deduplicated and retains none of the supplied plaintext.
    """
    digests: set[Hex64Str] = set()
    for value in values:
        if not isinstance(value, str):
            raise TypeError("operator-safe search terms must be strings")
        if len(value) > _MAX_OPERATOR_TERM_LENGTH:
            raise ValueError(f"operator-safe search terms cannot exceed {_MAX_OPERATOR_TERM_LENGTH} characters")
        _reject_control_characters(value)
        for token in _tokens(value):
            digests.add(cast(Hex64Str, hashlib.sha256(token.encode("utf-8")).hexdigest()))
    return tuple(sorted(digests))


class WorkbenchSearchKind(StrEnum):
    """Complete human-facing family for one cross-domain result."""

    LEDGER_ENTRY = "ledger_entry"
    LEDGER_EVIDENCE = "ledger_evidence"
    DECLARATION = "declaration"
    MODELO = "modelo"
    REVISION = "revision"
    FILING = "filing"
    HISTORY = "history"
    RECONCILIATION = "reconciliation"
    NOTIFICATION = "notification"


_STATUS_PREFIX_BY_KIND: dict[WorkbenchSearchKind, str] = {
    WorkbenchSearchKind.LEDGER_ENTRY: "ledger.entry.",
    WorkbenchSearchKind.LEDGER_EVIDENCE: "ledger.evidence.",
    WorkbenchSearchKind.DECLARATION: "declaration.",
    WorkbenchSearchKind.MODELO: "modelo.",
    WorkbenchSearchKind.REVISION: "revision.",
    WorkbenchSearchKind.FILING: "filing.",
    WorkbenchSearchKind.HISTORY: "history.",
    WorkbenchSearchKind.RECONCILIATION: "reconciliation.",
    WorkbenchSearchKind.NOTIFICATION: "notification.",
}
_ADDRESS_REQUIRED_KINDS = frozenset(
    {
        WorkbenchSearchKind.DECLARATION,
        WorkbenchSearchKind.MODELO,
        WorkbenchSearchKind.REVISION,
        WorkbenchSearchKind.FILING,
        WorkbenchSearchKind.HISTORY,
    }
)


class WorkbenchDestinationAdmissionState(StrEnum):
    """Whether a result's owning destination can currently be opened."""

    AVAILABLE = "available"
    LOCKED = "locked"
    STALE = "stale"
    NEVER_CAPTURED = "never_captured"
    UNAVAILABLE = "unavailable"


class WorkbenchModeloAddress(BaseModel):
    """Canonical natural address for one Modelo-related search result."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    revision_id: RevisionId | None = None
    filing_record_id: FilingRecordId | None = None

    @model_validator(mode="after")
    def _period_year_matches_address(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("Modelo address filing_year must match period.filing_year")
        return self


class WorkbenchDestinationAdmission(BaseModel):
    """Destination identity and truthful availability for a search result."""

    model_config = STRICT_FROZEN_CONFIG

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


def _validate_kind_contract(
    *,
    kind: WorkbenchSearchKind,
    status_code: str,
    address: WorkbenchModeloAddress | None,
    admission: WorkbenchDestinationAdmission,
    action_candidate_id: str | None,
    noun: str,
) -> None:
    expected_prefix = _STATUS_PREFIX_BY_KIND[kind]
    if not status_code.startswith(expected_prefix):
        raise ValueError(f"{kind.value} status_code must start with {expected_prefix!r}")
    if kind in _ADDRESS_REQUIRED_KINDS and address is None:
        raise ValueError(f"{kind.value} search {noun} require a Modelo address")
    if kind is WorkbenchSearchKind.REVISION and (address is None or address.revision_id is None):
        raise ValueError(f"revision search {noun} require a revision_id")
    if kind is WorkbenchSearchKind.FILING and (address is None or address.filing_record_id is None):
        raise ValueError(f"filing search {noun} require a filing_record_id")
    if admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE and action_candidate_id is not None:
        raise ValueError("a non-available destination cannot carry an action candidate")


class WorkbenchSearchDocument(BaseModel):
    """Safe provider projection accepted by the pure query service.

    ``label`` is explicitly redacted display text. ``token_digests`` are
    caller-produced with :func:`digest_operator_safe_tokens`; the document
    cannot serialize the source terms from which they were derived.
    ``action_candidate_id`` is only an unresolved catalogue candidate. S369's
    destination catalogue remains the authority that admits and resolves it.
    """

    model_config = STRICT_FROZEN_CONFIG

    stable_id: Hex64Str
    kind: WorkbenchSearchKind
    source: NamespacedId
    label: _RedactedLabel
    token_digests: tuple[Hex64Str, ...] = ()
    address: WorkbenchModeloAddress | None = None
    status_code: NamespacedId
    admission: WorkbenchDestinationAdmission
    action_candidate_id: NamespacedId | None = None

    @field_validator("label")
    @classmethod
    def _label_has_no_control_characters(cls, value: str) -> str:
        return _reject_control_characters(value)

    @field_validator("token_digests")
    @classmethod
    def _canonicalize_token_digests(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def _document_contract_is_consistent(self) -> Self:
        _validate_kind_contract(
            kind=self.kind,
            status_code=self.status_code,
            address=self.address,
            admission=self.admission,
            action_candidate_id=self.action_candidate_id,
            noun="documents",
        )
        return self


class WorkbenchSearchRequest(BaseModel):
    """Strict request whose plaintext query is transient and never serialized."""

    model_config = STRICT_FROZEN_CONFIG

    query: _TransientQuery = Field(exclude=True, repr=False)
    limit: Annotated[int, Field(gt=0, le=_MAX_SEARCH_RESULTS)] = 20

    @field_validator("query")
    @classmethod
    def _query_has_searchable_content(cls, value: str) -> str:
        _reject_control_characters(value)
        if not _tokens(value):
            raise ValueError("search query must contain searchable text")
        return value


class WorkbenchSearchResult(BaseModel):
    """One ranked result containing only redacted cross-domain metadata."""

    model_config = STRICT_FROZEN_CONFIG

    stable_id: Hex64Str
    kind: WorkbenchSearchKind
    source: NamespacedId
    label: _RedactedLabel
    address: WorkbenchModeloAddress | None = None
    status_code: NamespacedId
    admission: WorkbenchDestinationAdmission
    action_candidate_id: NamespacedId | None = None
    rank: NonNegativeInt
    score: float = Field(gt=0.0, allow_inf_nan=False)

    @field_validator("label")
    @classmethod
    def _label_has_no_control_characters(cls, value: str) -> str:
        return _reject_control_characters(value)

    @model_validator(mode="after")
    def _result_contract_is_consistent(self) -> Self:
        _validate_kind_contract(
            kind=self.kind,
            status_code=self.status_code,
            address=self.address,
            admission=self.admission,
            action_candidate_id=self.action_candidate_id,
            noun="results",
        )
        return self


class WorkbenchSearchResponse(BaseModel):
    """Bounded response that identifies its query only by token digests."""

    model_config = STRICT_FROZEN_CONFIG

    query_token_digests: tuple[Hex64Str, ...] = ()
    results: tuple[WorkbenchSearchResult, ...] = Field(default=(), max_length=_MAX_SEARCH_RESULTS)
    total_matches: NonNegativeInt = 0

    @field_validator("query_token_digests")
    @classmethod
    def _canonicalize_query_token_digests(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(set(value)))

    @model_validator(mode="after")
    def _result_page_is_canonical(self) -> Self:
        if self.total_matches < len(self.results):
            raise ValueError("total_matches cannot be smaller than the returned result count")
        ranks = tuple(result.rank for result in self.results)
        if ranks != tuple(range(len(self.results))):
            raise ValueError("search result ranks must be contiguous and zero-based")
        return self


def _document_token_digests(document: WorkbenchSearchDocument) -> frozenset[str]:
    safe_terms = [document.label]
    if document.address is not None:
        safe_terms.extend(
            (
                str(document.address.modelo),
                str(document.address.filing_year),
                document.address.period.registry_token,
            )
        )
    return frozenset((*document.token_digests, *digest_operator_safe_tokens(*safe_terms)))


def _score_document(document: WorkbenchSearchDocument, query: str) -> float | None:
    """Return a deterministic relevance score, or ``None`` when unmatched."""
    normalized_query = _normalize_text(query)
    query_tokens = _tokens(query)
    query_digests = digest_operator_safe_tokens(query)
    document_digests = _document_token_digests(document)
    title = _normalize_text(document.label)
    title_tokens = _tokens(document.label)
    if normalized_query not in title and not all(digest in document_digests for digest in query_digests):
        return None

    score = 0.0
    if normalized_query == title:
        score += 200.0
    elif normalized_query in title:
        score += 100.0
    for token in query_tokens:
        if token in title_tokens:
            score += 20.0
        elif any(candidate.startswith(token) for candidate in title_tokens):
            score += 10.0
        elif digest_operator_safe_tokens(token)[0] in document_digests:
            score += 5.0
    return score


class WorkbenchSearchService:
    """Pure search over one private, ephemeral in-memory projection snapshot."""

    def __init__(self, documents: Sequence[WorkbenchSearchDocument]) -> None:
        """Capture a private immutable snapshot and refuse duplicate identities."""
        snapshot = tuple(documents)
        if any(not isinstance(document, WorkbenchSearchDocument) for document in snapshot):
            raise TypeError("workbench search requires WorkbenchSearchDocument projections")
        stable_ids = tuple(document.stable_id for document in snapshot)
        if len(set(stable_ids)) != len(stable_ids):
            raise ValueError("workbench search projections require unique stable identities")
        self._documents = tuple(sorted(snapshot, key=lambda document: document.stable_id))

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
                status_code=document.status_code,
                admission=document.admission,
                action_candidate_id=document.action_candidate_id,
                rank=rank,
                score=score,
            )
            for rank, (score, document) in enumerate(ranked[: request.limit])
        )
        return WorkbenchSearchResponse(
            query_token_digests=digest_operator_safe_tokens(request.query),
            results=results,
            total_matches=len(ranked),
        )


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
    "digest_operator_safe_tokens",
]
