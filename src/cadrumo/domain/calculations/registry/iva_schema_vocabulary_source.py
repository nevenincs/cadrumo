"""Authority-resolved entry projection and cache for IVA schema vocabularies."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from threading import Lock
from typing import TYPE_CHECKING, Final
from weakref import ReferenceType, ref

from ....core.time.clock import today_madrid
from .facts.resolution import MappingFactQuery, ResolvedMappingFact
from .facts.string_mapping import (
    MappingValueWhitespace,
    StringMappingPolicy,
    require_resolved_mapping_fact,
    string_mapping_entries,
)
from .governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from .schema_base import DateAxis

if TYPE_CHECKING:
    from .iva_cash_accounting_vocabulary import IvaCashAccountingTreatmentCatalogue

SCHEMA_VOCABULARY_SUBJECT: Final = "IVA schema vocabulary"

UNIQUE_TOKENS_REQUIREMENT: Final = "must contain unique non-empty tokens"

_FACT_ID = "iva-statutory-schema-vocabulary"

_ENTRIES_POLICY = StringMappingPolicy(
    subject=SCHEMA_VOCABULARY_SUBJECT, value_whitespace=MappingValueWhitespace.PRESERVE
)


@dataclass(frozen=True, slots=True)
class SchemaVocabularyProjections:
    """The flattened entries of one resolved fact, and projections derived from them."""

    owner: ReferenceType[ResolvedMappingFact]
    entries: Mapping[str, str]
    cash_accounting: list[IvaCashAccountingTreatmentCatalogue]


_PROJECTIONS: dict[int, SchemaVocabularyProjections] = {}

_PROJECTIONS_LOCK = Lock()


def _entry_projections(resolved: ResolvedMappingFact) -> SchemaVocabularyProjections:
    key = id(resolved)
    with _PROJECTIONS_LOCK:
        cached = _PROJECTIONS.get(key)
        if cached is not None and cached.owner() is resolved:
            return cached
    entries = string_mapping_entries(resolved, policy=_ENTRIES_POLICY)

    def forget(dead: ReferenceType[ResolvedMappingFact]) -> None:
        with _PROJECTIONS_LOCK:
            current = _PROJECTIONS.get(key)
            if current is not None and current.owner is dead:
                del _PROJECTIONS[key]

    projections = SchemaVocabularyProjections(owner=ref(resolved, forget), entries=entries, cash_accounting=[])
    with _PROJECTIONS_LOCK:
        _PROJECTIONS[key] = projections
    return projections


_BY_AUTHORITY: dict[tuple[int, date], tuple[ReferenceType[GovernedFactSource], SchemaVocabularyProjections]] = {}

_BY_AUTHORITY_LIMIT = 1024


def _resolve_projections(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> SchemaVocabularyProjections:
    key = (id(authority), effective_date)
    with _PROJECTIONS_LOCK:
        cached = _BY_AUTHORITY.get(key)
        if cached is not None and cached[0]() is authority:
            return cached[1]
    projections = _resolve_projections_uncached(effective_date=effective_date, authority=authority)

    def forget(dead: ReferenceType[GovernedFactSource]) -> None:
        with _PROJECTIONS_LOCK:
            for stale in [held for held, (owner, _) in _BY_AUTHORITY.items() if owner is dead]:
                del _BY_AUTHORITY[stale]

    try:
        owner = ref(authority, forget)
    except TypeError:
        return projections
    with _PROJECTIONS_LOCK:
        if len(_BY_AUTHORITY) >= _BY_AUTHORITY_LIMIT:
            _BY_AUTHORITY.pop(next(iter(_BY_AUTHORITY)))
        _BY_AUTHORITY[key] = (owner, projections)
    return projections


def _resolve_projections_uncached(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> SchemaVocabularyProjections:
    resolved = require_resolved_mapping_fact(
        authority,
        MappingFactQuery(fact_id=_FACT_ID, date_axis=DateAxis.FILING_PERIOD, effective_date=effective_date),
        subject=_ENTRIES_POLICY.subject,
    )
    return _entry_projections(resolved)


def resolve_scoped_schema_projections(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> SchemaVocabularyProjections:
    """Resolve the shared schema-vocabulary projections from the explicit authority or the scope.

    Raises:
        InternalInvariantError: When no authority is supplied and no validation scope is active.
    """
    selected_date = effective_date or today_madrid()
    selected = require_governed_fact_authority(authority, subject=SCHEMA_VOCABULARY_SUBJECT)
    return _resolve_projections(effective_date=selected_date, authority=selected)


def resolve_scoped_schema_entries(
    *,
    effective_date: date | None,
    authority: GovernedFactSource | None,
) -> Mapping[str, str]:
    """Return the shared schema-vocabulary entries, resolved as the projections are."""
    return resolve_scoped_schema_projections(effective_date=effective_date, authority=authority).entries
