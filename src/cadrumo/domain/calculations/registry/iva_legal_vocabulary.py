"""Typed authority projections for IVA legal-reference vocabularies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from ...iva.schema import IvaArt69DosService, IvaExemptionArticle
from .errors import RegistryValidationError
from .facts.resolution import required_mapping_entry, unique_mapping_tokens
from .governed_fact_scope import GovernedFactSource
from .iva_schema_vocabulary_source import (
    SCHEMA_VOCABULARY_SUBJECT,
    UNIQUE_TOKENS_REQUIREMENT,
    csv_legal_references,
    resolve_scoped_schema_entries,
)
from .iva_schema_vocabulary_tokens import _require_token

_EXEMPTION_ORDER_KEY = "exemption_article.order"

_SERVICE_ORDER_KEY = "art_69_dos_service.order"

_EXEMPTION_PREFIX = "exemption_article."

_SERVICE_PREFIX = "art_69_dos_service."


@dataclass(frozen=True, slots=True)
class IvaExemptionArticleDefinition:
    """One registry-declared IVA exemption article token and semantics."""

    token: IvaExemptionArticle
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaExemptionArticleCatalogue:
    """Typed projection of the dated exemption-article vocabulary."""

    definitions: tuple[IvaExemptionArticleDefinition, ...]

    @property
    def all_articles(self) -> frozenset[IvaExemptionArticle]:
        """Return every IVA exemption article declared by the registry."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> IvaExemptionArticle:
        """Validate and return one registry-declared IVA exemption article."""
        return _require_token(value, IvaExemptionArticle, self.all_articles, "exemption article")

    def definition(self, value: object) -> IvaExemptionArticleDefinition:
        """Return the registry definition for one IVA exemption article."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


@dataclass(frozen=True, slots=True)
class IvaArt69DosServiceDefinition:
    """One registry-declared Art. 69.Dos service token and semantics."""

    token: IvaArt69DosService
    description: str
    legal_refs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class IvaArt69DosServiceCatalogue:
    """Typed projection of the dated Art. 69.Dos service vocabulary."""

    definitions: tuple[IvaArt69DosServiceDefinition, ...]

    @property
    def all_services(self) -> frozenset[IvaArt69DosService]:
        """Return every Art. 69.Dos service declared by the registry."""
        return frozenset(definition.token for definition in self.definitions)

    def require(self, value: object) -> IvaArt69DosService:
        """Validate and return one registry-declared Art. 69.Dos service."""
        return _require_token(value, IvaArt69DosService, self.all_services, "Art. 69.Dos service")

    def definition(self, value: object) -> IvaArt69DosServiceDefinition:
        """Return the registry definition for one Art. 69.Dos service."""
        token = self.require(value)
        return next(definition for definition in self.definitions if definition.token == token)


def resolve_iva_exemption_article_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaExemptionArticleCatalogue:
    """Resolve the dated IVA exemption-article vocabulary from governed facts."""
    entries = resolve_scoped_schema_entries(effective_date=effective_date, authority=authority)
    definitions: list[IvaExemptionArticleDefinition] = []
    for raw_token in unique_mapping_tokens(
        entries, _EXEMPTION_ORDER_KEY, subject=SCHEMA_VOCABULARY_SUBJECT, requirement=UNIQUE_TOKENS_REQUIREMENT
    ):
        token = IvaExemptionArticle(raw_token)
        prefix = f"{_EXEMPTION_PREFIX}{raw_token}"
        if required_mapping_entry(entries, f"{prefix}.value", subject=SCHEMA_VOCABULARY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"exemption article token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaExemptionArticleDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=SCHEMA_VOCABULARY_SUBJECT),
                legal_refs=csv_legal_references(entries, f"{prefix}.legal_refs", required=True),
            ),
        )
    return IvaExemptionArticleCatalogue(definitions=tuple(definitions))


def resolve_iva_art69_dos_service_catalogue(
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaArt69DosServiceCatalogue:
    """Resolve the dated Art. 69.Dos service vocabulary from governed facts."""
    entries = resolve_scoped_schema_entries(effective_date=effective_date, authority=authority)
    definitions: list[IvaArt69DosServiceDefinition] = []
    for raw_token in unique_mapping_tokens(
        entries, _SERVICE_ORDER_KEY, subject=SCHEMA_VOCABULARY_SUBJECT, requirement=UNIQUE_TOKENS_REQUIREMENT
    ):
        token = IvaArt69DosService(raw_token)
        prefix = f"{_SERVICE_PREFIX}{raw_token}"
        if required_mapping_entry(entries, f"{prefix}.value", subject=SCHEMA_VOCABULARY_SUBJECT) != raw_token:
            raise RegistryValidationError(f"Art. 69.Dos service token {raw_token!r} declares a mismatched value")
        definitions.append(
            IvaArt69DosServiceDefinition(
                token=token,
                description=required_mapping_entry(entries, f"{prefix}.description", subject=SCHEMA_VOCABULARY_SUBJECT),
                legal_refs=csv_legal_references(entries, f"{prefix}.legal_refs", required=True),
            ),
        )
    return IvaArt69DosServiceCatalogue(definitions=tuple(definitions))


def require_iva_exemption_article(
    value: object,
    *,
    effective_date: date | None = None,
    authority: GovernedFactSource | None = None,
) -> IvaExemptionArticle:
    """Validate one value against the dated IVA exemption-article vocabulary."""
    return resolve_iva_exemption_article_catalogue(
        effective_date=effective_date,
        authority=authority,
    ).require(value)


__all__ = [
    "IvaArt69DosServiceCatalogue",
    "IvaArt69DosServiceDefinition",
    "IvaExemptionArticleCatalogue",
    "IvaExemptionArticleDefinition",
    "require_iva_exemption_article",
    "resolve_iva_art69_dos_service_catalogue",
    "resolve_iva_exemption_article_catalogue",
]
