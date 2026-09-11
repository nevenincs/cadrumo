"""Generic parser and outcome mechanics for supply-nature citations.

Concrete citation rows, namespace qualifiers, category relationships, article
headings, ordering, and legal provenance are canonical registry data. This
module retains only typed outcomes, normalization/matching mechanics, and the
explicit projection boundary that accepts selected catalogue data.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum
from typing import TYPE_CHECKING, Final, Self

from pydantic import BaseModel, Field, model_validator

from ...core.models import STRICT_FROZEN_CONFIG
from ..calculations.registry.authority import bundled_authority
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.schema_base import DateAxis
from .errors import IvaValidationError
from .schema import IvaCategory

if TYPE_CHECKING:
    from ..calculations.registry.authority import ValidatedRegistryAuthority

__all__ = [
    "CitationCatalogue",
    "StatutoryCitation",
    "SupplyNature",
    "SupplyNatureDerivation",
    "SupplyNatureDerivationOutcome",
    "derive_supply_nature_from_citation",
    "match_statutory_citations",
    "registry_citation_catalogue",
    "supply_nature_implied_by_category",
]


class SupplyNature(StrEnum):
    """What an operation supplies."""

    GOODS = "goods"
    SERVICES = "services"


class StatutoryCitation(BaseModel):
    """One registry-projected citation row and its generic outcome."""

    model_config = STRICT_FROZEN_CONFIG

    article: str = Field(min_length=1)
    heading: str = Field(min_length=1)
    corpus_ref: str = Field(min_length=1)
    establishes: SupplyNature | None = None


@dataclass(frozen=True, slots=True)
class CitationCatalogue:
    """Registry-projected citation rows and namespace qualifiers."""

    citations: tuple[StatutoryCitation, ...]
    qualifiers: tuple[str, ...]
    category_citations: Mapping[IvaCategory, tuple[str, ...]] = field(default_factory=dict)


class SupplyNatureDerivationOutcome(StrEnum):
    """What the citation parser was able to conclude."""

    DERIVED = "derived"
    CONTRADICTED = "contradicted"
    ABSENT = "absent"


class SupplyNatureDerivation(BaseModel):
    """The citation parser's typed conclusion."""

    model_config = STRICT_FROZEN_CONFIG

    outcome: SupplyNatureDerivationOutcome
    nature: SupplyNature | None = None
    citations: tuple[StatutoryCitation, ...] = ()
    note: str = ""

    @model_validator(mode="after")
    def _each_outcome_carries_exactly_what_it_claims(self) -> Self:
        """Refuse a result whose payload does not match its outcome."""
        if self.outcome is SupplyNatureDerivationOutcome.DERIVED:
            if self.nature is None:
                raise ValueError("a derived outcome must carry its nature")
            if not self.citations:
                raise ValueError("a derived outcome must carry its citations")
        elif self.outcome is SupplyNatureDerivationOutcome.CONTRADICTED:
            if self.nature is not None:
                raise ValueError("a contradicted outcome must not carry a nature")
            if len(self.citations) < 2:
                raise ValueError("a contradicted outcome must carry disagreeing citations")
        elif self.nature is not None:
            raise ValueError("an absent outcome establishes no nature")
        return self


_NOTHING_DERIVED: Final = SupplyNatureDerivation(outcome=SupplyNatureDerivationOutcome.ABSENT)
_ARTICLE_REFERENCE_SEPARATOR: Final[str] = ":art-"


def _require_catalogue(catalogue: CitationCatalogue | None) -> CitationCatalogue:
    if catalogue is None:
        return registry_citation_catalogue(effective_date=date.today())
    return catalogue


# fact-relocation: selected IVA statutory citation catalogue is consumed through the governed mapping fact
def registry_citation_catalogue(
    *,
    effective_date: date,
    authority: ValidatedRegistryAuthority | None = None,
) -> CitationCatalogue:
    """Project the dated citation mapping fact into generic parser inputs."""
    selected_authority = authority or bundled_authority()
    resolved = selected_authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="iva-supply-nature-citation-catalogue",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise IvaValidationError("IVA statutory citation catalogue must resolve as a mapping fact")
    entries: dict[str, str] = {}
    for entry in resolved.payload.entries:
        if not isinstance(entry.key, str) or not isinstance(entry.value, str):
            raise IvaValidationError("IVA statutory citation mapping entries must be string-to-string")
        if entry.key in entries:
            raise IvaValidationError(f"duplicate IVA statutory citation mapping key {entry.key!r}")
        entries[entry.key] = entry.value

    def required(key: str) -> str:
        value = entries.get(key)
        if value is None or not value.strip():
            raise IvaValidationError(f"IVA statutory citation mapping is missing {key!r}")
        return value

    qualifier_order = tuple(token.strip() for token in required("qualifier_order").split(",") if token.strip())
    qualifiers = tuple(required(f"qualifier.{token}") for token in qualifier_order)
    citation_order = tuple(token.strip() for token in required("citation_order").split(",") if token.strip())
    citations: list[StatutoryCitation] = []
    for token in citation_order:
        prefix = f"citation.{token}"
        establishes = required(f"{prefix}.establishes")
        try:
            nature = None if establishes == "none" else SupplyNature(establishes)
        except ValueError as exc:
            raise IvaValidationError(f"unknown supply nature {establishes!r} in registry citation {token!r}") from exc
        citations.append(
            StatutoryCitation(
                article=required(f"{prefix}.article"),
                heading=required(f"{prefix}.heading"),
                corpus_ref=required(f"{prefix}.corpus_ref"),
                establishes=nature,
            ),
        )
    category_citations: dict[IvaCategory, tuple[str, ...]] = {}
    for key, value in entries.items():
        if not key.startswith("category."):
            continue
        try:
            category = IvaCategory(key.removeprefix("category."))
        except ValueError as exc:
            raise IvaValidationError(f"unknown IVA category {key!r} in statutory citation mapping") from exc
        category_citations[category] = tuple(reference.strip() for reference in value.split(",") if reference.strip())
    if not category_citations:
        raise IvaValidationError("IVA statutory citation mapping has no category projections")
    return CitationCatalogue(
        citations=tuple(citations),
        qualifiers=qualifiers,
        category_citations=category_citations,
    )


def _citation_pattern(article: str) -> re.Pattern[str]:
    """Compile the generic article-reference matcher for one projected row."""
    parts = article.split()
    number = re.escape(parts[0])
    tail = "".join(rf"\s+\b{re.escape(part)}\b" for part in parts[1:])
    return re.compile(
        rf"\bart(?:\.|s\.|ículos?|icles?)?\s*{number}\b{tail}",
        re.IGNORECASE,
    )


def match_statutory_citations(
    printed: str | None,
    *,
    catalogue: CitationCatalogue | None = None,
) -> tuple[StatutoryCitation, ...]:
    """Return every registry-projected citation row matched in ``printed``."""
    if printed is None:
        return ()
    folded = printed.casefold()
    if not folded.strip():
        return ()
    selected = _require_catalogue(catalogue)
    if not any(qualifier.casefold() in folded for qualifier in selected.qualifiers):
        return ()
    return tuple(citation for citation in selected.citations if _citation_pattern(citation.article).search(printed))


def derive_supply_nature_from_citation(
    *,
    printed_citation: str | None,
    catalogue: CitationCatalogue | None = None,
) -> SupplyNatureDerivation:
    """Parse a printed citation against a selected registry catalogue."""
    citations = match_statutory_citations(printed_citation, catalogue=catalogue)
    if not citations:
        return _NOTHING_DERIVED
    return _derive_from_citations(citations)


def supply_nature_implied_by_category(
    category: IvaCategory | None,
    *,
    catalogue: CitationCatalogue | None = None,
    category_citations: Mapping[IvaCategory, tuple[str, ...]] | None = None,
) -> SupplyNatureDerivation:
    """Join a registry-projected category grounding map to citation rows."""
    if category is None:
        return _NOTHING_DERIVED
    selected = _require_catalogue(catalogue)
    if category_citations is None:
        category_citations = selected.category_citations
    if not category_citations:
        raise IvaValidationError("IVA category citation map must be supplied by registry authority")
    articles = {
        reference.split(_ARTICLE_REFERENCE_SEPARATOR, 1)[1]
        for reference in category_citations.get(category, ())
        if _ARTICLE_REFERENCE_SEPARATOR in reference
    }
    citations = tuple(citation for citation in selected.citations if citation.article in articles)
    return _derive_from_citations(citations)


def _derive_from_citations(citations: tuple[StatutoryCitation, ...]) -> SupplyNatureDerivation:
    if not citations:
        return _NOTHING_DERIVED
    natures = {citation.establishes for citation in citations if citation.establishes is not None}
    if not natures:
        return SupplyNatureDerivation(
            outcome=SupplyNatureDerivationOutcome.ABSENT,
            citations=citations,
        )
    if len(natures) > 1:
        cited = ", ".join(f"article {citation.article}" for citation in citations)
        return SupplyNatureDerivation(
            outcome=SupplyNatureDerivationOutcome.CONTRADICTED,
            citations=citations,
            note=f"the document cites rows with different supply natures ({cited})",
        )
    return SupplyNatureDerivation(
        outcome=SupplyNatureDerivationOutcome.DERIVED,
        nature=natures.pop(),
        citations=citations,
    )
