"""Typed projection of the dated Lorca IVA reduction fact (0136)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from types import MappingProxyType
from typing import Final

from .errors import RegistryValidationError
from .facts.resolution import MappingFactQuery, ResolvedMappingFact, required_mapping_entry
from .governed_fact_scope import GovernedFactSource, governed_facts_in_scope
from .schema_base import DateAxis

_ENTRY_SUBJECT: Final = "Lorca reduction fact"

_FACT_ID = "liva-orden-lorca-reduction"
_EXERCISE_KEY = "reduction.ejercicio"
_MUNICIPALITY_KEY = "reduction.municipality"
_ANNEX_SCOPE_KEY = "reduction.annex_scope"
_PERCENTAGE_KEY = "reduction.percentage"
_CALCULATION_PERIODS_KEY = "reduction.calculation_periods"
_LEGAL_REF_KEY = "reduction.legal_ref"
_SOURCE_REF_KEY = "reduction.source_ref"
_SOURCE_CONTENT_DIGEST_KEY = "reduction.source_content_digest"
_ARTICLE_KEY = "reduction.article"
_SECTION_KEY = "reduction.section"


@dataclass(frozen=True, slots=True)
class LorcaReductionDefinition:
    """One fully evidenced annual-Orden Lorca reduction projection."""

    ejercicio: int
    municipality: str
    annex_scope: str
    percentage: Decimal
    calculation_periods: tuple[str, ...]
    legal_ref: str
    source_ref: str
    source_content_digest: str
    required_text: tuple[str, ...]
    article: str
    section: str


def _mapping_entries(resolved: ResolvedMappingFact) -> Mapping[str, str]:
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise RegistryValidationError("Lorca reduction entries must be string-to-string")
        if entry.key in entries:
            raise RegistryValidationError(f"duplicate Lorca reduction key {entry.key!r}")
        entries[entry.key] = entry.value
    return MappingProxyType(entries)


def _single_evidence(values: tuple[str, ...], label: str) -> str:
    if len(values) != 1 or not values[0].strip():
        raise RegistryValidationError(f"Lorca reduction fact must declare exactly one {label}")
    return str(values[0])


def _periods(entries: Mapping[str, str]) -> tuple[str, ...]:
    values = tuple(
        value.strip()
        for value in required_mapping_entry(entries, _CALCULATION_PERIODS_KEY, subject=_ENTRY_SUBJECT).split(",")
        if value.strip()
    )
    if not values or len(values) != len(set(values)):
        raise RegistryValidationError("Lorca reduction calculation periods must be unique non-empty tokens")
    return values


def _required_text(resolved: ResolvedMappingFact, *, source_ref: str) -> tuple[str, ...]:
    citations = tuple(citation for citation in resolved.source_citations if citation.source_ref == source_ref)
    if len(citations) != 1 or not citations[0].required_text:
        raise RegistryValidationError("Lorca reduction fact must declare exactly one source citation")
    return tuple(text.strip() for text in citations[0].required_text if text.strip())


def _decimal(entries: Mapping[str, str], key: str) -> Decimal:
    try:
        value = Decimal(required_mapping_entry(entries, key, subject=_ENTRY_SUBJECT))
    except InvalidOperation as exc:
        raise RegistryValidationError(f"Lorca reduction fact has a non-decimal {key!r}") from exc
    if value < 0:
        raise RegistryValidationError(f"Lorca reduction fact has a negative {key!r}")
    return value


def _resolve_entries(
    *,
    effective_date: date,
    authority: GovernedFactSource,
) -> tuple[Mapping[str, str], str, str, tuple[str, ...]]:
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id=_FACT_ID,
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise RegistryValidationError("Lorca reduction fact must resolve as a mapping fact")
    source_ref = _single_evidence(resolved.source_refs, "source reference")
    return (
        _mapping_entries(resolved),
        _single_evidence(resolved.legal_refs, "legal reference"),
        source_ref,
        _required_text(resolved, source_ref=source_ref),
    )


def resolve_lorca_reduction(
    *,
    effective_date: date,
    authority: GovernedFactSource | None = None,
) -> LorcaReductionDefinition:
    """Resolve the Lorca reduction through the selected facts authority."""
    selected = authority or governed_facts_in_scope()
    if selected is None:
        raise RegistryValidationError("Lorca reduction requires an explicit authority operation or scope")
    entries, legal_ref, source_ref, required_text = _resolve_entries(
        effective_date=effective_date,
        authority=selected,
    )
    try:
        ejercicio = int(required_mapping_entry(entries, _EXERCISE_KEY, subject=_ENTRY_SUBJECT))
    except ValueError as exc:
        raise RegistryValidationError("Lorca reduction fact has a non-integer ejercicio") from exc
    if effective_date.year != ejercicio:
        raise RegistryValidationError("Lorca reduction fact exercise does not match its query date")
    source_content_digest = required_mapping_entry(entries, _SOURCE_CONTENT_DIGEST_KEY, subject=_ENTRY_SUBJECT)
    if len(source_content_digest) != 64 or any(
        character not in "0123456789abcdef" for character in source_content_digest
    ):
        raise RegistryValidationError("Lorca reduction source content digest must be lowercase SHA-256")
    if required_mapping_entry(entries, _LEGAL_REF_KEY, subject=_ENTRY_SUBJECT) != legal_ref:
        raise RegistryValidationError("Lorca reduction payload legal reference disagrees with variant evidence")
    if required_mapping_entry(entries, _SOURCE_REF_KEY, subject=_ENTRY_SUBJECT) != source_ref:
        raise RegistryValidationError("Lorca reduction payload source reference disagrees with variant evidence")
    return LorcaReductionDefinition(
        ejercicio=ejercicio,
        municipality=required_mapping_entry(entries, _MUNICIPALITY_KEY, subject=_ENTRY_SUBJECT),
        annex_scope=required_mapping_entry(entries, _ANNEX_SCOPE_KEY, subject=_ENTRY_SUBJECT),
        percentage=_decimal(entries, _PERCENTAGE_KEY),
        calculation_periods=_periods(entries),
        legal_ref=legal_ref,
        source_ref=source_ref,
        source_content_digest=source_content_digest,
        required_text=required_text,
        article=required_mapping_entry(entries, _ARTICLE_KEY, subject=_ENTRY_SUBJECT),
        section=required_mapping_entry(entries, _SECTION_KEY, subject=_ENTRY_SUBJECT),
    )


__all__ = ["LorcaReductionDefinition", "resolve_lorca_reduction"]
