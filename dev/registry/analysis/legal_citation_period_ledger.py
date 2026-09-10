"""Read the legal-citation period ledger's classified per-citation exceptions.

Each ``[[exception]]`` entry names one modelo, one edition and one cited
reference, lists every casilla of that edition whose citation it excepts, and
classifies why the citation does not govern the edition. Every casilla is named
explicitly; there is no wildcard, prefix or count. Reading refuses a malformed
entry, an unknown category, and a citation named twice rather than letting any
of them quietly widen the exception set.
"""

from __future__ import annotations

import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from cadrumo.domain.calculations.registry.casilla_legal_citation_period import (
    CasillaCitationKey,
    CitationPeriodRefusal,
)

__all__ = [
    "LEDGER_PATH",
    "CitationException",
    "CitationExceptionCategory",
    "category_disagreements",
    "load_citation_exceptions",
]

LEDGER_PATH = Path(__file__).with_name("legal_citation_period_ledger.toml")

_REQUIRED = ("modelo", "revision", "reference", "category", "reason")


class CitationExceptionCategory(StrEnum):
    """Why an excepted casilla citation does not govern its edition."""

    SUPERSEDED_ROW_CITED = "superseded_row_cited"
    """Another catalogue row of the same article governs the edition; the casilla cites a different redaction."""
    NO_GOVERNING_ROW_CATALOGUED = "no_governing_row_catalogued"
    """No catalogue row of the cited article governs the edition."""


@dataclass(frozen=True, slots=True)
class CitationException:
    """One excepted citation and the classified reason it stands."""

    key: CasillaCitationKey
    category: CitationExceptionCategory
    reason: str


def load_citation_exceptions(path: Path = LEDGER_PATH) -> Mapping[CasillaCitationKey, CitationException]:
    """Load every excepted citation keyed by the citation it names."""
    document = tomllib.loads(path.read_text(encoding="utf-8"))
    exceptions: dict[CasillaCitationKey, CitationException] = {}
    for index, entry in enumerate(document.get("exception", ())):
        blank = [name for name in _REQUIRED if not isinstance(entry.get(name), str) or not entry[name].strip()]
        if blank:
            raise ValueError(f"{path.name}: exception #{index} has no {', '.join(blank)}")
        try:
            category = CitationExceptionCategory(entry["category"])
        except ValueError as exc:
            raise ValueError(f"{path.name}: exception #{index} has unknown category {entry['category']!r}") from exc
        casillas = entry.get("casillas")
        if not isinstance(casillas, list) or not casillas:
            raise ValueError(f"{path.name}: exception #{index} names no casillas")
        for casilla in casillas:
            if not isinstance(casilla, str) or not casilla.strip():
                raise ValueError(f"{path.name}: exception #{index} names a blank casilla")
            key = CasillaCitationKey(
                modelo=entry["modelo"],
                revision=entry["revision"],
                casilla=casilla,
                reference=entry["reference"],
            )
            if key in exceptions:
                raise ValueError(f"{path.name}: exception #{index} names {key} a second time")
            exceptions[key] = CitationException(key=key, category=category, reason=entry["reason"])
    return exceptions


def category_disagreements(
    exceptions: Mapping[CasillaCitationKey, CitationException],
    refusals: Mapping[CasillaCitationKey, CitationPeriodRefusal],
) -> tuple[CasillaCitationKey, ...]:
    """Return excepted citations whose category contradicts the refusal the rule computes.

    A citation is ``superseded_row_cited`` exactly when the rule finds another
    row of the same article that governs the edition. Citations the rule does
    not refuse are stale, which the rule itself reports, and are skipped here.
    """
    disagreeing: list[CasillaCitationKey] = []
    for key, exception in exceptions.items():
        refusal = refusals.get(key)
        if refusal is None:
            continue
        superseded = bool(refusal.alternatives)
        if superseded != (exception.category is CitationExceptionCategory.SUPERSEDED_ROW_CITED):
            disagreeing.append(key)
    return tuple(sorted(disagreeing))
