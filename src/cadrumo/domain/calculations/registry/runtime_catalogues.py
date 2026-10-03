"""Canonical typed runtime tables published with the registry authority."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.frozen_mapping import FROZEN_MAPPING
from .errors import RegistryValidationError
from .runtime_catalogue_validation import (
    _require_catalogue_record_keys,
    _require_complete_recargo_bands,
    _require_place_of_supply_grounding,
    _require_postal_territory_keys,
    _require_tax_catalogue_keys,
    _require_unique_country_alpha3,
    _require_unique_country_names,
)
from .schema_base import RegistryModel


class PublishedIvaCitation(RegistryModel):
    """One dated legal citation embedded in an IVA operative rule."""

    legal_reference: str = Field(min_length=1)
    quoted_text: str = ""
    grounding: Literal["verified", "unresolved"] = "verified"
    unresolved_reason: str = ""
    retrieval_date: date
    valid_from: date
    valid_to: date

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _grounding_is_complete(self) -> Self:
        if self.valid_to < self.valid_from:
            raise RegistryValidationError(f"IVA citation {self.legal_reference!r} has an inverted validity window")
        if self.grounding == "verified":
            if not self.quoted_text.strip() or self.unresolved_reason.strip():
                raise RegistryValidationError("verified IVA citation requires quotation and no unresolved reason")
        elif self.quoted_text.strip() or not self.unresolved_reason.strip():
            raise RegistryValidationError("unresolved IVA citation requires reason and no quotation")
        return self


class PublishedIvaRegulation(RegistryModel):
    """One typed IVA category regulation and its legal grounding."""

    category: str = Field(min_length=1)
    requires_reverse_charge: bool
    requires_supplier_iva_id: bool
    manual_references: tuple[str, ...]
    citations: tuple[PublishedIvaCitation, ...]
    notes: str = ""
    legal_basis_exempt: bool = False

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _grounding_matches_disposition(self) -> Self:
        if self.legal_basis_exempt:
            if self.citations or not self.notes.strip():
                raise RegistryValidationError("legal-basis-exempt IVA regulation requires notes and no citations")
        elif not self.citations:
            raise RegistryValidationError(f"IVA regulation {self.category!r} requires citations")
        return self


class PublishedIvaPlaceOfSupplyRule(RegistryModel):
    """One dated place-of-supply rule published for runtime selection."""

    rule_id: str = Field(min_length=1)
    supply_nature: str | None = None
    legal_references: tuple[str, ...] = ()
    establishing_reference: str = ""
    notes: str = ""
    legal_basis_exempt: bool = False
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _grounding_matches_disposition(self) -> Self:
        _require_place_of_supply_grounding(self)
        return self


class PublishedRecargoBand(RegistryModel):
    """One contiguous late-filing surcharge band."""

    id: str = Field(min_length=1)
    min_completed_months: int = Field(ge=0)
    max_completed_months: int | None = Field(default=None, ge=0)
    surcharge_pct: Decimal
    interest_applies: bool = False
    legal_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _ordered_window(self) -> Self:
        if not self.surcharge_pct.is_finite():
            raise RegistryValidationError(f"recargo band {self.id!r} has a non-finite surcharge")
        if self.max_completed_months is not None and self.max_completed_months < self.min_completed_months:
            raise RegistryValidationError(f"recargo band {self.id!r} has an inverted completed-month window")
        return self


class CountryVocabularyRecord(RegistryModel):
    """One canonical country code and its accepted printed names."""

    code: str = Field(pattern=r"^[A-Z]{2}$")
    alpha3: str = Field(pattern=r"^[A-Z]{3}$")
    names: tuple[str, ...] = Field(min_length=1)
    notes: str = ""


class SpanishPostalTerritory(RegistryModel):
    """One Spanish postal-prefix classification for IVA territory."""

    postal_prefixes: tuple[str, ...] = Field(min_length=1)
    scope: str = Field(min_length=1)
    name: str = Field(min_length=1)
    legal_refs: tuple[str, ...] = Field(min_length=1)
    notes: str = ""


class TerritoryCarveOut(RegistryModel):
    """One special territory's explicit IVA disposition."""

    code: str = Field(pattern=r"^[A-Z]{2}$")
    name: str = Field(min_length=1)
    assimilated_to: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    scope: str | None = None
    establishes_nothing: bool = False
    legal_refs: tuple[str, ...] = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _require_one_disposition(self) -> Self:
        if sum((self.assimilated_to is not None, self.scope is not None, self.establishes_nothing)) != 1:
            raise RegistryValidationError(f"territory carve-out {self.code!r} must declare one disposition")
        return self


class ApoderamientoScopeRecord(RegistryModel):
    """One published authorization scope and its modelo coverage."""

    code: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    name_es: str = Field(min_length=1)
    name_en: str = Field(min_length=1)
    name_ca: str = Field(min_length=1)
    name_hu: str = Field(min_length=1)
    modelo_codes: tuple[str, ...] = ()


class RuntimeRegistryCatalogues(RegistryModel):
    """Every former raw runtime table, reconstructed without TOML access."""

    iva_regulations: Annotated[Mapping[str, PublishedIvaRegulation], FROZEN_MAPPING] = Field(default_factory=dict)
    iva_place_of_supply: Annotated[Mapping[str, PublishedIvaPlaceOfSupplyRule], FROZEN_MAPPING] = Field(
        default_factory=dict
    )
    countries: Annotated[Mapping[str, CountryVocabularyRecord], FROZEN_MAPPING] = Field(default_factory=dict)
    spanish_postal_territories: Annotated[Mapping[str, SpanishPostalTerritory], FROZEN_MAPPING] = Field(
        default_factory=dict
    )
    territory_carve_outs: Annotated[Mapping[str, TerritoryCarveOut], FROZEN_MAPPING] = Field(default_factory=dict)
    recargo_bands: Annotated[Mapping[str, PublishedRecargoBand], FROZEN_MAPPING] = Field(default_factory=dict)
    apoderamientos_version: str = ""
    apoderamientos_scopes: Annotated[Mapping[str, ApoderamientoScopeRecord], FROZEN_MAPPING] = Field(
        default_factory=dict
    )

    def require_complete(self) -> Self:
        """Refuse an authority publication missing any former runtime table."""
        tables = {
            "iva_regulations": self.iva_regulations,
            "iva_place_of_supply": self.iva_place_of_supply,
            "countries": self.countries,
            "spanish_postal_territories": self.spanish_postal_territories,
            "territory_carve_outs": self.territory_carve_outs,
            "recargo_bands": self.recargo_bands,
            "apoderamientos_scopes": self.apoderamientos_scopes,
        }
        missing = sorted(name for name, records in tables.items() if not records)
        if not self.apoderamientos_version.strip():
            missing.append("apoderamientos_version")
        if missing:
            raise RegistryValidationError(f"runtime authority catalogues are incomplete: {missing}")
        return self

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _keys_match_records(self) -> Self:
        _require_catalogue_record_keys(self)
        _require_postal_territory_keys(self)
        _require_tax_catalogue_keys(self)
        _require_unique_country_alpha3(self)
        _require_unique_country_names(self)
        _require_complete_recargo_bands(self)
        return self
