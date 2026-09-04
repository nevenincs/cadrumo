"""Frontend-neutral, intrinsically safe search projections for the workbench.

The service searches a private, ephemeral snapshot containing only closed
semantic codes and canonical natural addresses. Providers cannot attach free
text, raw search terms, token indexes, or an asserted result identity. The
service derives each result identity from the safe projection itself and owns
no repository, persistence, network, localization, or frontend dependency.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
import unicodedata
from collections.abc import Sequence
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, Field, NonNegativeInt, SecretStr, StringConstraints, field_validator, model_validator

from ...core.filing_year import FilingYear
from ...core.hex import Hex64Str
from ...core.identifier_grammar import NamespacedId
from ...core.identity import CalculationRevisionId, FilingRecordId
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.period import Period
from ...core.text_fold import fold_printed_phrase
from ...domain.modelos.codes import ModeloCode

_MAX_QUERY_LENGTH = 200
_MAX_SEARCH_RESULTS = 100
_WORD_PATTERN = re.compile(r"\w+", re.UNICODE)
_OPAQUE_IDENTITY_KEY = secrets.token_bytes(32)

_TransientQuery = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=_MAX_QUERY_LENGTH),
]


def _reject_control_characters(value: str) -> str:
    if any(unicodedata.category(character) == "Cc" for character in value):
        raise ValueError("workbench search query cannot contain control characters")
    return value


def _normalize_text(value: str) -> str:
    return fold_printed_phrase(value)


def _tokens(value: str) -> tuple[str, ...]:
    return tuple(match.group(0) for match in _WORD_PATTERN.finditer(_normalize_text(value)))


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


class WorkbenchSearchSource(StrEnum):
    """Closed application projection that supplied a search record."""

    LEDGER_ENTRY = "ledger.entry_projection"
    LEDGER_EVIDENCE = "ledger.evidence_projection"
    DECLARATION = "modelo.declaration_projection"
    MODELO = "modelo.catalogue_projection"
    REVISION = "modelo.calculation_history_projection"
    FILING = "filing.record_projection"
    HISTORY = "filing.history_projection"
    RECONCILIATION = "reconciliation.finding_projection"
    NOTIFICATION = "notification.aeat_projection"


class WorkbenchSearchStatus(StrEnum):
    """Closed source-native statuses admitted by the search boundary."""

    LEDGER_ENTRY_READY = "ledger.entry.ready"
    LEDGER_ENTRY_NEEDS_REVIEW = "ledger.entry.needs_review"
    LEDGER_ENTRY_CLASSIFIED = "ledger.entry.classified"
    LEDGER_EVIDENCE_CAPTURED = "ledger.evidence.captured"
    LEDGER_EVIDENCE_MISSING = "ledger.evidence.missing"
    LEDGER_EVIDENCE_STALE = "ledger.evidence.stale"
    DECLARATION_DRAFT = "declaration.draft"
    DECLARATION_IN_PROGRESS = "declaration.in_progress"
    DECLARATION_NEEDS_ATTENTION = "declaration.needs_attention"
    DECLARATION_READY = "declaration.ready"
    DECLARATION_FILED = "declaration.filed"
    MODELO_AVAILABLE = "modelo.available"
    MODELO_UNAVAILABLE = "modelo.unavailable"
    REVISION_CURRENT = "revision.current"
    REVISION_SUPERSEDED = "revision.superseded"
    FILING_SUBMITTED = "filing.submitted"
    FILING_ACCEPTED = "filing.accepted"
    FILING_REJECTED = "filing.rejected"
    HISTORY_OBSERVED = "history.observed"
    HISTORY_NOT_OBSERVED = "history.not_observed"
    RECONCILIATION_OPEN = "reconciliation.open"
    RECONCILIATION_RESOLVED = "reconciliation.resolved"
    NOTIFICATION_UNREAD = "notification.unread"
    NOTIFICATION_READ = "notification.read"


class WorkbenchSearchLabelKey(StrEnum):
    """Closed localization key; never provider-authored display text."""

    LEDGER_ENTRY = "search.ledger_entry"
    LEDGER_EVIDENCE = "search.ledger_evidence"
    DECLARATION = "search.declaration"
    MODELO = "search.modelo"
    REVISION = "search.revision"
    FILING = "search.filing"
    HISTORY = "search.history"
    RECONCILIATION = "search.reconciliation"
    NOTIFICATION = "search.notification"


_SOURCE_BY_KIND: dict[WorkbenchSearchKind, WorkbenchSearchSource] = {
    kind: WorkbenchSearchSource(kind_source)
    for kind, kind_source in (
        (WorkbenchSearchKind.LEDGER_ENTRY, WorkbenchSearchSource.LEDGER_ENTRY),
        (WorkbenchSearchKind.LEDGER_EVIDENCE, WorkbenchSearchSource.LEDGER_EVIDENCE),
        (WorkbenchSearchKind.DECLARATION, WorkbenchSearchSource.DECLARATION),
        (WorkbenchSearchKind.MODELO, WorkbenchSearchSource.MODELO),
        (WorkbenchSearchKind.REVISION, WorkbenchSearchSource.REVISION),
        (WorkbenchSearchKind.FILING, WorkbenchSearchSource.FILING),
        (WorkbenchSearchKind.HISTORY, WorkbenchSearchSource.HISTORY),
        (WorkbenchSearchKind.RECONCILIATION, WorkbenchSearchSource.RECONCILIATION),
        (WorkbenchSearchKind.NOTIFICATION, WorkbenchSearchSource.NOTIFICATION),
    )
}
_LABEL_BY_KIND: dict[WorkbenchSearchKind, WorkbenchSearchLabelKey] = {
    kind: WorkbenchSearchLabelKey(f"search.{kind.value}") for kind in WorkbenchSearchKind
}
_STATUSES_BY_SOURCE: dict[WorkbenchSearchSource, frozenset[WorkbenchSearchStatus]] = {
    WorkbenchSearchSource.LEDGER_ENTRY: frozenset(
        {
            WorkbenchSearchStatus.LEDGER_ENTRY_READY,
            WorkbenchSearchStatus.LEDGER_ENTRY_NEEDS_REVIEW,
            WorkbenchSearchStatus.LEDGER_ENTRY_CLASSIFIED,
        }
    ),
    WorkbenchSearchSource.LEDGER_EVIDENCE: frozenset(
        {
            WorkbenchSearchStatus.LEDGER_EVIDENCE_CAPTURED,
            WorkbenchSearchStatus.LEDGER_EVIDENCE_MISSING,
            WorkbenchSearchStatus.LEDGER_EVIDENCE_STALE,
        }
    ),
    WorkbenchSearchSource.DECLARATION: frozenset(
        {
            WorkbenchSearchStatus.DECLARATION_DRAFT,
            WorkbenchSearchStatus.DECLARATION_IN_PROGRESS,
            WorkbenchSearchStatus.DECLARATION_NEEDS_ATTENTION,
            WorkbenchSearchStatus.DECLARATION_READY,
            WorkbenchSearchStatus.DECLARATION_FILED,
        }
    ),
    WorkbenchSearchSource.MODELO: frozenset(
        {WorkbenchSearchStatus.MODELO_AVAILABLE, WorkbenchSearchStatus.MODELO_UNAVAILABLE}
    ),
    WorkbenchSearchSource.REVISION: frozenset(
        {WorkbenchSearchStatus.REVISION_CURRENT, WorkbenchSearchStatus.REVISION_SUPERSEDED}
    ),
    WorkbenchSearchSource.FILING: frozenset(
        {
            WorkbenchSearchStatus.FILING_SUBMITTED,
            WorkbenchSearchStatus.FILING_ACCEPTED,
            WorkbenchSearchStatus.FILING_REJECTED,
        }
    ),
    WorkbenchSearchSource.HISTORY: frozenset(
        {WorkbenchSearchStatus.HISTORY_OBSERVED, WorkbenchSearchStatus.HISTORY_NOT_OBSERVED}
    ),
    WorkbenchSearchSource.RECONCILIATION: frozenset(
        {WorkbenchSearchStatus.RECONCILIATION_OPEN, WorkbenchSearchStatus.RECONCILIATION_RESOLVED}
    ),
    WorkbenchSearchSource.NOTIFICATION: frozenset(
        {WorkbenchSearchStatus.NOTIFICATION_UNREAD, WorkbenchSearchStatus.NOTIFICATION_READ}
    ),
}
_OPAQUE_IDENTITY_KINDS = frozenset(
    {
        WorkbenchSearchKind.LEDGER_ENTRY,
        WorkbenchSearchKind.LEDGER_EVIDENCE,
        WorkbenchSearchKind.HISTORY,
        WorkbenchSearchKind.RECONCILIATION,
        WorkbenchSearchKind.NOTIFICATION,
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
    """Exact Modelo/year/period case address without a record identity."""

    model_config = STRICT_FROZEN_CONFIG

    address_kind: Literal["modelo_case"] = "modelo_case"
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period

    @model_validator(mode="after")
    def _period_year_matches_address(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("Modelo address filing_year must match period.filing_year")
        return self


class WorkbenchRevisionAddress(BaseModel):
    """Exact calculation-history revision address."""

    model_config = STRICT_FROZEN_CONFIG

    address_kind: Literal["calculation_revision"] = "calculation_revision"
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    calculation_revision_id: CalculationRevisionId

    @model_validator(mode="after")
    def _period_year_matches_address(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("revision address filing_year must match period.filing_year")
        return self


class WorkbenchFilingAddress(BaseModel):
    """Exact filing-record address."""

    model_config = STRICT_FROZEN_CONFIG

    address_kind: Literal["filing_record"] = "filing_record"
    modelo: ModeloCode
    filing_year: FilingYear
    period: Period
    filing_record_id: FilingRecordId

    @model_validator(mode="after")
    def _period_year_matches_address(self) -> Self:
        if self.period.filing_year != self.filing_year:
            raise ValueError("filing address filing_year must match period.filing_year")
        return self


type WorkbenchNaturalAddress = Annotated[
    WorkbenchModeloAddress | WorkbenchRevisionAddress | WorkbenchFilingAddress,
    Field(discriminator="address_kind"),
]


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


def _validate_projection(
    *,
    kind: WorkbenchSearchKind,
    source: WorkbenchSearchSource,
    status: WorkbenchSearchStatus,
    label_key: WorkbenchSearchLabelKey,
    address: WorkbenchNaturalAddress | None,
    admission: WorkbenchDestinationAdmission,
    action_candidate_id: str | None,
    identity_basis: SecretStr | None = None,
    validate_identity_basis: bool = False,
) -> None:
    if source is not _SOURCE_BY_KIND[kind]:
        raise ValueError(f"{kind.value} requires source {_SOURCE_BY_KIND[kind].value!r}")
    if status not in _STATUSES_BY_SOURCE[source]:
        raise ValueError(f"status {status.value!r} is not declared by source {source.value!r}")
    if label_key is not _LABEL_BY_KIND[kind]:
        raise ValueError(f"{kind.value} requires label_key {_LABEL_BY_KIND[kind].value!r}")
    expected_address_type: type[BaseModel] | None = {
        WorkbenchSearchKind.DECLARATION: WorkbenchModeloAddress,
        WorkbenchSearchKind.MODELO: WorkbenchModeloAddress,
        WorkbenchSearchKind.REVISION: WorkbenchRevisionAddress,
        WorkbenchSearchKind.FILING: WorkbenchFilingAddress,
        WorkbenchSearchKind.HISTORY: WorkbenchModeloAddress,
    }.get(kind)
    if expected_address_type is None and address is not None:
        raise ValueError(f"{kind.value} cannot carry a Modelo natural address")
    if expected_address_type is not None and type(address) is not expected_address_type:
        raise ValueError(f"{kind.value} requires exact {expected_address_type.__name__}")
    if admission.state is not WorkbenchDestinationAdmissionState.AVAILABLE and action_candidate_id is not None:
        raise ValueError("a non-available destination cannot carry an action candidate")
    if validate_identity_basis:
        if kind in _OPAQUE_IDENTITY_KINDS and identity_basis is None:
            raise ValueError(f"{kind.value} requires a private opaque identity basis")
        if kind not in _OPAQUE_IDENTITY_KINDS and identity_basis is not None:
            raise ValueError(f"{kind.value} derives identity from its natural address")


class WorkbenchSearchDocument(BaseModel):
    """Intrinsically safe source projection accepted by the query service.

    Structural fields are closed enums, canonical natural addresses, or
    technical namespaced action/admission tokens. Multi-record families carry a
    private source identity basis that is retained only in memory, excluded from
    serialization and representation, and converted to a process-keyed opaque
    result identity. There is no provider-authored label, caller-visible source
    identifier, or asserted stable identity. ``action_candidate_id`` remains
    unresolved until S369's catalogue admits it.

    ``content_terms`` carries the operator's own words -- a counterparty, a
    description, an amount -- so that searching for them finds the record they
    belong to. A search index over enum names alone can only answer questions
    the operator already knows the vocabulary for: they can find "ledger entry"
    but not "Suministros Delta", which is the only thing they actually
    remember. The session is authenticated against their own data, so the terms
    are theirs; the identity basis stays secret because it is machine
    addressing, and that distinction is the point.
    """

    model_config = STRICT_FROZEN_CONFIG

    kind: WorkbenchSearchKind
    source: WorkbenchSearchSource
    status: WorkbenchSearchStatus
    label_key: WorkbenchSearchLabelKey
    address: WorkbenchNaturalAddress | None = None
    admission: WorkbenchDestinationAdmission
    action_candidate_id: NamespacedId | None = None
    identity_basis: SecretStr | None = Field(default=None, exclude=True, repr=False, min_length=1, max_length=512)
    content_terms: tuple[str, ...] = ()
    """The operator's own words for this record, matched alongside the enums."""

    @field_validator("identity_basis")
    @classmethod
    def _identity_basis_has_no_control_characters(cls, value: SecretStr | None) -> SecretStr | None:
        if value is not None:
            _reject_control_characters(value.get_secret_value())
        return value

    @model_validator(mode="after")
    def _projection_is_consistent(self) -> Self:
        _validate_projection(
            kind=self.kind,
            source=self.source,
            status=self.status,
            label_key=self.label_key,
            address=self.address,
            admission=self.admission,
            action_candidate_id=self.action_candidate_id,
            identity_basis=self.identity_basis,
            validate_identity_basis=True,
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
    """One ranked result containing only intrinsically safe metadata."""

    model_config = STRICT_FROZEN_CONFIG

    stable_id: Hex64Str
    kind: WorkbenchSearchKind
    source: WorkbenchSearchSource
    status: WorkbenchSearchStatus
    label_key: WorkbenchSearchLabelKey
    address: WorkbenchNaturalAddress | None = None
    admission: WorkbenchDestinationAdmission
    action_candidate_id: NamespacedId | None = None
    rank: NonNegativeInt
    score: float = Field(gt=0.0, allow_inf_nan=False)

    @model_validator(mode="after")
    def _projection_is_consistent(self) -> Self:
        _validate_projection(
            kind=self.kind,
            source=self.source,
            status=self.status,
            label_key=self.label_key,
            address=self.address,
            admission=self.admission,
            action_candidate_id=self.action_candidate_id,
        )
        return self


class WorkbenchSearchResponse(BaseModel):
    """Bounded response carrying neither plaintext nor hashed query terms."""

    model_config = STRICT_FROZEN_CONFIG

    results: tuple[WorkbenchSearchResult, ...] = Field(default=(), max_length=_MAX_SEARCH_RESULTS)
    total_matches: NonNegativeInt = 0

    @model_validator(mode="after")
    def _result_page_is_canonical(self) -> Self:
        if self.total_matches < len(self.results):
            raise ValueError("total_matches cannot be smaller than the returned result count")
        if tuple(result.rank for result in self.results) != tuple(range(len(self.results))):
            raise ValueError("search result ranks must be contiguous and zero-based")
        return self


def _safe_search_terms(document: WorkbenchSearchDocument) -> tuple[str, ...]:
    terms: list[str] = [
        document.kind.value.replace("_", " "),
        document.label_key.value.removeprefix("search.").replace("_", " "),
    ]
    terms.extend(document.status.value.split("."))
    terms.extend(document.content_terms)
    if document.address is not None:
        terms.extend(
            (
                "modelo",
                str(document.address.modelo),
                str(document.address.filing_year),
                document.address.period.registry_token,
            )
        )
        if isinstance(document.address, WorkbenchRevisionAddress):
            terms.append(document.address.calculation_revision_id)
        elif isinstance(document.address, WorkbenchFilingAddress):
            terms.append(document.address.filing_record_id)
    return tuple(terms)


def _immutable_identity_coordinate(document: WorkbenchSearchDocument) -> tuple[str, ...]:
    if document.identity_basis is not None:
        return ("opaque", document.identity_basis.get_secret_value())
    if document.address is None:  # pragma: no cover - guarded by projection validation
        raise ValueError("a search projection requires an immutable identity coordinate")
    coordinate = (
        document.address.address_kind,
        str(document.address.modelo),
        str(document.address.filing_year),
        document.address.period.registry_token,
    )
    if isinstance(document.address, WorkbenchRevisionAddress):
        return (*coordinate, document.address.calculation_revision_id)
    if isinstance(document.address, WorkbenchFilingAddress):
        return (*coordinate, document.address.filing_record_id)
    return coordinate


def _derived_stable_id(document: WorkbenchSearchDocument) -> Hex64Str:
    canonical = "\x1f".join(
        (document.kind.value, document.source.value, *_immutable_identity_coordinate(document))
    ).encode("utf-8")
    return hmac.digest(_OPAQUE_IDENTITY_KEY, canonical, hashlib.sha256).hex()


def _score_document(document: WorkbenchSearchDocument, query: str) -> float | None:
    query_tokens = _tokens(query)
    safe_terms = _safe_search_terms(document)
    document_tokens = _tokens(" ".join(safe_terms))
    normalized_query = _normalize_text(query)
    title = _normalize_text(document.label_key.value.removeprefix("search.").replace("_", " "))
    if normalized_query not in title and not all(token in document_tokens for token in query_tokens):
        return None
    score = 200.0 if normalized_query == title else 100.0 if normalized_query in title else 0.0
    score += sum(20.0 if token in _tokens(title) else 5.0 for token in query_tokens)
    return score


class WorkbenchSearchService:
    """Pure search over one private, ephemeral, intrinsically safe snapshot."""

    def __init__(self, documents: Sequence[WorkbenchSearchDocument]) -> None:
        """Capture a private snapshot and refuse duplicate derived identities."""
        snapshot = tuple(documents)
        if any(not isinstance(document, WorkbenchSearchDocument) for document in snapshot):
            raise TypeError("workbench search requires WorkbenchSearchDocument projections")
        derived = tuple((_derived_stable_id(document), document) for document in snapshot)
        identities = tuple(identity for identity, _ in derived)
        if len(set(identities)) != len(identities):
            raise ValueError("workbench search projections require unique derived identities")
        self._documents = tuple(sorted(derived, key=lambda item: item[0]))

    def search(self, request: WorkbenchSearchRequest) -> WorkbenchSearchResponse:
        """Return deterministic matches capped by the request's result limit."""
        if not isinstance(request, WorkbenchSearchRequest):
            raise TypeError("workbench search requires WorkbenchSearchRequest")
        ranked: list[tuple[float, Hex64Str, WorkbenchSearchDocument]] = []
        for identity, document in self._documents:
            score = _score_document(document, request.query)
            if score is not None:
                ranked.append((score, identity, document))
        ranked.sort(key=lambda item: (-item[0], item[1]))
        results = tuple(
            WorkbenchSearchResult(
                stable_id=identity,
                kind=document.kind,
                source=document.source,
                status=document.status,
                label_key=document.label_key,
                address=document.address,
                admission=document.admission,
                action_candidate_id=document.action_candidate_id,
                rank=rank,
                score=score,
            )
            for rank, (score, identity, document) in enumerate(ranked[: request.limit])
        )
        return WorkbenchSearchResponse(results=results, total_matches=len(ranked))


__all__ = [
    "WorkbenchDestinationAdmission",
    "WorkbenchDestinationAdmissionState",
    "WorkbenchFilingAddress",
    "WorkbenchModeloAddress",
    "WorkbenchNaturalAddress",
    "WorkbenchRevisionAddress",
    "WorkbenchSearchDocument",
    "WorkbenchSearchKind",
    "WorkbenchSearchLabelKey",
    "WorkbenchSearchRequest",
    "WorkbenchSearchResponse",
    "WorkbenchSearchResult",
    "WorkbenchSearchService",
    "WorkbenchSearchSource",
    "WorkbenchSearchStatus",
]
