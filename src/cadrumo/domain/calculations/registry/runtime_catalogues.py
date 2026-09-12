"""Canonical typed runtime tables published with the registry authority."""

from __future__ import annotations

import unicodedata
from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from itertools import pairwise
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from ....core.frozen_mapping import FROZEN_MAPPING
from .errors import RegistryValidationError
from .schema_base import RegistryModel


class PublishedIvaCitation(RegistryModel):
    legal_reference: str = Field(min_length=1)
    quoted_text: str = ""
    grounding: Literal["verified", "unresolved"] = "verified"
    unresolved_reason: str = ""
    retrieval_date: date
    valid_from: date
    valid_to: date

    @model_validator(mode="after")
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
    category: str = Field(min_length=1)
    requires_reverse_charge: bool
    requires_supplier_iva_id: bool
    manual_references: tuple[str, ...]
    citations: tuple[PublishedIvaCitation, ...]
    notes: str = ""
    legal_basis_exempt: bool = False

    @model_validator(mode="after")
    def _grounding_matches_disposition(self) -> Self:
        if self.legal_basis_exempt:
            if self.citations or not self.notes.strip():
                raise RegistryValidationError("legal-basis-exempt IVA regulation requires notes and no citations")
        elif not self.citations:
            raise RegistryValidationError(f"IVA regulation {self.category!r} requires citations")
        return self


class PublishedIvaPlaceOfSupplyRule(RegistryModel):
    rule_id: str = Field(min_length=1)
    supply_nature: str | None = None
    legal_references: tuple[str, ...] = ()
    establishing_reference: str = ""
    notes: str = ""
    legal_basis_exempt: bool = False
    valid_from: date | None = None
    valid_to: date | None = None

    @model_validator(mode="after")
    def _grounding_matches_disposition(self) -> Self:
        if len(self.legal_references) != len(set(self.legal_references)):
            raise RegistryValidationError(f"place-of-supply rule {self.rule_id!r} repeats legal references")
        if self.legal_basis_exempt:
            if self.legal_references or self.establishing_reference or self.supply_nature is not None:
                raise RegistryValidationError("exempt place-of-supply rule must carry no legal disposition")
            if self.valid_from is not None or self.valid_to is not None:
                raise RegistryValidationError("exempt place-of-supply rule must carry no validity window")
        else:
            if self.valid_from is None or self.valid_to is None or self.valid_to < self.valid_from:
                raise RegistryValidationError("grounded place-of-supply rule requires an ordered closed window")
            if not self.legal_references or self.establishing_reference not in self.legal_references:
                raise RegistryValidationError("place-of-supply establishing reference must be among its legal refs")
        return self


class PublishedRecargoBand(RegistryModel):
    id: str = Field(min_length=1)
    min_completed_months: int = Field(ge=0)
    max_completed_months: int | None = Field(default=None, ge=0)
    surcharge_pct: Decimal
    interest_applies: bool = False
    legal_ref: str = Field(min_length=1)

    @model_validator(mode="after")
    def _ordered_window(self) -> Self:
        if not self.surcharge_pct.is_finite():
            raise RegistryValidationError(f"recargo band {self.id!r} has a non-finite surcharge")
        if self.max_completed_months is not None and self.max_completed_months < self.min_completed_months:
            raise RegistryValidationError(f"recargo band {self.id!r} has an inverted completed-month window")
        return self


class CountryVocabularyRecord(RegistryModel):
    code: str = Field(pattern=r"^[A-Z]{2}$")
    alpha3: str = Field(pattern=r"^[A-Z]{3}$")
    names: tuple[str, ...] = Field(min_length=1)
    notes: str = ""


class SpanishPostalTerritory(RegistryModel):
    postal_prefixes: tuple[str, ...] = Field(min_length=1)
    scope: str = Field(min_length=1)
    name: str = Field(min_length=1)
    legal_refs: tuple[str, ...] = Field(min_length=1)
    notes: str = ""


class TerritoryCarveOut(RegistryModel):
    code: str = Field(pattern=r"^[A-Z]{2}$")
    name: str = Field(min_length=1)
    assimilated_to: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")
    scope: str | None = None
    establishes_nothing: bool = False
    legal_refs: tuple[str, ...] = Field(min_length=1)
    notes: str = ""

    @model_validator(mode="after")
    def _require_one_disposition(self) -> Self:
        if sum((self.assimilated_to is not None, self.scope is not None, self.establishes_nothing)) != 1:
            raise RegistryValidationError(f"territory carve-out {self.code!r} must declare one disposition")
        return self


class ApoderamientoScopeRecord(RegistryModel):
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

    def legal_reference_ids(self) -> frozenset[str]:
        """Return every legal identity carried by a published runtime table."""
        return frozenset(
            ref
            for refs in (
                (
                    citation.legal_reference
                    for regulation in self.iva_regulations.values()
                    for citation in regulation.citations
                ),
                (ref for rule in self.iva_place_of_supply.values() for ref in rule.legal_references),
                (ref for territory in self.spanish_postal_territories.values() for ref in territory.legal_refs),
                (ref for carve_out in self.territory_carve_outs.values() for ref in carve_out.legal_refs),
                (band.legal_ref for band in self.recargo_bands.values()),
            )
            for ref in refs
        )

    @model_validator(mode="after")
    def _keys_match_records(self) -> Self:
        collections = (
            (self.countries, "code"),
            (self.territory_carve_outs, "code"),
            (self.recargo_bands, "id"),
            (self.apoderamientos_scopes, "code"),
        )
        for records, identity_name in collections:
            for key, record in records.items():
                if key != getattr(record, identity_name):
                    raise RegistryValidationError(f"runtime catalogue key {key!r} does not match record identity")
        for prefix, record in self.spanish_postal_territories.items():
            if prefix not in record.postal_prefixes:
                raise RegistryValidationError(f"postal-territory key {prefix!r} is not declared by its record")
        if any(key != record.category for key, record in self.iva_regulations.items()):
            raise RegistryValidationError("IVA regulation key does not match its category")
        if any(key != record.rule_id for key, record in self.iva_place_of_supply.items()):
            raise RegistryValidationError("place-of-supply key does not match its rule id")
        alpha3 = tuple(record.alpha3 for record in self.countries.values())
        if len(alpha3) != len(set(alpha3)):
            raise RegistryValidationError("country vocabulary repeats an alpha-3 code")
        names: dict[str, str] = {}
        for code, record in self.countries.items():
            for name in record.names:
                folded = " ".join(
                    "".join(
                        character
                        for character in unicodedata.normalize("NFKD", name.casefold())
                        if not unicodedata.combining(character)
                    ).split()
                )
                if not folded:
                    raise RegistryValidationError(f"country {code!r} carries a blank printed name")
                previous = names.setdefault(folded, code)
                if previous != code:
                    raise RegistryValidationError(f"printed country name {name!r} belongs to multiple countries")
        ordered_bands = sorted(self.recargo_bands.values(), key=lambda band: band.min_completed_months)
        if ordered_bands:
            if ordered_bands[0].min_completed_months != 0 or ordered_bands[-1].max_completed_months is not None:
                raise RegistryValidationError("recargo bands must cover from zero through one open-ended tail")
            for previous, current in pairwise(ordered_bands):
                if previous.max_completed_months is None:
                    raise RegistryValidationError("only the final recargo band may be open-ended")
                if current.min_completed_months != previous.max_completed_months + 1:
                    raise RegistryValidationError("recargo bands must be contiguous and non-overlapping")
        return self
