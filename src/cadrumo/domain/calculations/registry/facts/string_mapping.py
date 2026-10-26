"""String-to-string projection of resolved governed mapping facts.

Many governed catalogues author their vocabulary as one mapping fact whose keys
and values are all text, then read it through ``required_mapping_entry`` and
``unique_mapping_tokens``. This module owns the shared payload-shape steps: it
resolves the mapping fact, refuses any entry that is not string-to-string,
returns an immutable view, and reads the boolean and legal-reference entries
those catalogues share. Whether surrounding whitespace in a value is kept, and
whether a boolean token is matched case-sensitively, are part of each
catalogue's contract, so the caller states them rather than this module
choosing one.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from enum import StrEnum
from types import MappingProxyType

from .....core.time.clock import today_madrid
from ..errors import RegistryValidationError
from ..governed_fact_scope import GovernedFactSource, require_governed_fact_authority
from ..schema_base import DateAxis
from .resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry, unique_mapping_tokens
from .variants import FactSelector

_LEGAL_REFS_REQUIREMENT = "must contain unique legal references"


class MappingValueWhitespace(StrEnum):
    """How a string mapping projection treats whitespace around each value."""

    PRESERVE = "preserve"
    STRIP = "strip"


class BooleanTokenCase(StrEnum):
    """Whether a boolean mapping entry must be spelled in lower case."""

    EXACT = "exact"
    CASE_INSENSITIVE = "case_insensitive"


@dataclass(frozen=True, slots=True)
class StringMappingPolicy:
    """How one catalogue projects its mapping fact into string entries.

    ``subject`` names the catalogue in every refusal so each consumer keeps its
    own diagnostic wording.
    """

    subject: str
    value_whitespace: MappingValueWhitespace


@dataclass(frozen=True, slots=True)
class StringMappingFact:
    """One catalogue's governed mapping fact, its date axis and its projection policy.

    The effective date is the only coordinate a caller supplies; the fact, the
    axis and any selectors are fixed by the catalogue that owns the fact.
    """

    fact_id: str
    date_axis: DateAxis
    policy: StringMappingPolicy
    selectors: tuple[FactSelector, ...] = ()

    def resolve_entries(self, authority: GovernedFactSource, *, effective_date: date) -> Mapping[str, str]:
        """Resolve this fact at ``effective_date`` and project it under its policy.

        Raises:
            RegistryValidationError: When the fact does not resolve as a mapping
                or its payload is not string-to-string.
        """
        query = MappingFactQuery(
            fact_id=self.fact_id,
            date_axis=self.date_axis,
            effective_date=effective_date,
            selectors=self.selectors,
        )
        return resolve_string_mapping_entries(authority, query, policy=self.policy)

    def resolve_scoped_entries(
        self,
        *,
        effective_date: date | None,
        authority: GovernedFactSource | None,
    ) -> Mapping[str, str]:
        """Resolve this fact from the explicit authority or the validation scope.

        An absent ``effective_date`` is today's date in Madrid. The published
        bundle is never read: with neither an authority nor a scope the
        catalogue refuses.

        Raises:
            InternalInvariantError: When no authority is supplied and no
                validation scope is active.
            RegistryValidationError: When the fact does not resolve as a mapping
                or its payload is not string-to-string.
        """
        selected = require_governed_fact_authority(authority, subject=self.policy.subject)
        return self.resolve_entries(selected, effective_date=effective_date or today_madrid())


def require_resolved_mapping_fact(
    authority: GovernedFactSource,
    query: MappingFactQuery,
    *,
    subject: str,
) -> ResolvedMappingFact:
    """Resolve ``query`` and return it only when it resolved as a mapping fact.

    Raises:
        RegistryValidationError: When the authority returns another family.
    """
    resolved = authority.resolve_governed_fact(query)
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError(f"{subject} must resolve as a mapping fact")
    return resolved


def string_mapping_entries(resolved: ResolvedMappingFact, *, policy: StringMappingPolicy) -> Mapping[str, str]:
    """Return the resolved mapping fact as an immutable string-to-string view.

    Raises:
        RegistryValidationError: When an entry key or value is not text, or a
            key repeats.
    """
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError(f"{policy.subject} entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate {policy.subject} key {entry.key!r}")
        value = entry.value.strip() if policy.value_whitespace is MappingValueWhitespace.STRIP else entry.value
        entries[entry.key] = value
    return MappingProxyType(entries)


def resolve_string_mapping_entries(
    authority: GovernedFactSource,
    query: MappingFactQuery,
    *,
    policy: StringMappingPolicy,
) -> Mapping[str, str]:
    """Resolve ``query`` as a mapping fact and project it under ``policy``.

    Raises:
        RegistryValidationError: When the fact does not resolve as a mapping or
            its payload is not string-to-string.
    """
    resolved = require_resolved_mapping_fact(authority, query, subject=policy.subject)
    return string_mapping_entries(resolved, policy=policy)


def required_mapping_boolean(
    entries: Mapping[str, str],
    key: str,
    *,
    subject: str,
    case: BooleanTokenCase,
) -> bool:
    """Return one required ``true``/``false`` entry as a boolean.

    Raises:
        RegistryValidationError: When the entry is absent, blank or not a
            boolean token under ``case``.
    """
    value = required_mapping_entry(entries, key, subject=subject)
    if case is BooleanTokenCase.CASE_INSENSITIVE:
        value = value.lower()
    if value not in {"true", "false"}:
        raise RegistryValidationError(f"{subject} {key!r} must be true or false")
    return value == "true"


def unique_mapping_legal_refs(entries: Mapping[str, str], key: str, *, subject: str) -> tuple[str, ...]:
    """Return the non-empty, unique comma-separated legal references of one entry.

    Raises:
        RegistryValidationError: When the entry is absent or blank, names no
            reference, or repeats one.
    """
    return unique_mapping_tokens(entries, key, subject=subject, requirement=_LEGAL_REFS_REQUIREMENT)


__all__ = [
    "BooleanTokenCase",
    "MappingValueWhitespace",
    "StringMappingFact",
    "StringMappingPolicy",
    "require_resolved_mapping_fact",
    "required_mapping_boolean",
    "resolve_string_mapping_entries",
    "string_mapping_entries",
    "unique_mapping_legal_refs",
]
