"""Classifiable output-volume memberships governed by LIVA arts. 94 and 104."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...iva.schema import IvaCategory, IvaExemptionArticle
from .errors import RegistryValidationError
from .facts.resolution import unique_mapping_tokens
from .facts.string_mapping import MappingValueWhitespace, StringMappingFact, StringMappingPolicy
from .governed_fact_scope import GovernedFactSource
from .iva_category_catalogue import resolve_iva_category_catalogue
from .iva_legal_vocabulary import resolve_iva_exemption_article_catalogue
from .schema_base import DateAxis

_FACT = StringMappingFact(
    fact_id="renta-iva-deduction-ratio-policy",
    date_axis=DateAxis.FILING_PERIOD,
    policy=StringMappingPolicy(subject="prorrata output volumes", value_whitespace=MappingValueWhitespace.PRESERVE),
)


@dataclass(frozen=True, slots=True)
class ProrrataVolumeCatalogue:
    """Known rights only; other categories keep their unresolved classification."""

    con_derecho: frozenset[IvaCategory]
    sin_derecho: frozenset[IvaCategory]
    sin_derecho_exemption_articles: frozenset[IvaExemptionArticle]


def resolve_prorrata_volume_catalogue(
    *, effective_date: date, authority: GovernedFactSource
) -> ProrrataVolumeCatalogue:
    """Resolve disjoint memberships against the same generation's category vocabulary."""
    entries = _FACT.resolve_entries(authority, effective_date=effective_date)
    categories = resolve_iva_category_catalogue(effective_date=effective_date, authority=authority)
    groups = tuple(
        frozenset(
            categories.require(token)
            for token in unique_mapping_tokens(
                entries,
                "prorrata.volume." + group + "_categories",
                subject="prorrata output volumes",
                requirement="must declare unique non-empty categories",
            )
        )
        for group in ("con_derecho", "sin_derecho")
    )
    if groups[0] & groups[1]:
        raise RegistryValidationError("prorrata output-volume rights must be disjoint")
    articles = resolve_iva_exemption_article_catalogue(effective_date=effective_date, authority=authority)
    sin_articles = frozenset(
        articles.require(token)
        for token in unique_mapping_tokens(
            entries,
            "prorrata.volume.sin_derecho_exemption_articles",
            subject="prorrata output volumes",
            requirement="must declare unique non-empty articles",
        )
    )
    return ProrrataVolumeCatalogue(
        con_derecho=groups[0], sin_derecho=groups[1], sin_derecho_exemption_articles=sin_articles
    )
