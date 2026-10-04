"""Modelo 720 foreign-asset register: persisted asset identity and declaration entries.

The type 2 record of Modelo 720 (Orden HAP/72/2013 Anexo) is one record per
asset, per declarant condition (position 76) and per incorporation date
(positions 415-422). Official identifiers do not identify every asset: real
estate (B) carries only an address, insurance (S) only the insurer, and a
security without an ISIN is coded ``ZXX`` by issuer country (positions 132-143).
The row-carrier decision therefore joins ledger-sourced observations and the
operator's declaration on an explicit persisted asset identity, with the
official identifier kept as a cross-check.

This module holds the register document and its invariants only. It reads no
store, converts no currency and resolves no binding; the persistence adapter
stores the document and the 720 resolver joins on :class:`M720AssetRef`.

See Also:
    :mod:`adapters.persistence.profile.foreign_assets`
        FINANCIAL secure-object repository for this document.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Final

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from ...core.country_code import CountryCodeAlpha2
from ...core.errors.hierarchy import CadrumoError, pydantic_validation_boundary
from ...core.foreign_asset_obligation import M720AssetClassCode
from ...core.iban import IBAN_SHAPE_RE, iban_mod_97, normalise_iban
from ...core.isin import is_valid_isin
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.percentage import Percentage

FOREIGN_ASSET_REGISTER_SCHEMA_VERSION: Final = "1"
"""Schema version stamped on the register document and every entry."""


class ForeignAssetRegisterError(CadrumoError):
    """Raised when the foreign-asset register refuses an operation."""


class ForeignAssetRegisterValidationError(ForeignAssetRegisterError):
    """Raised when a register document or entry fails its invariants."""


M720AssetRef = Annotated[
    str,
    StringConstraints(pattern=r"^m720a_[0-9a-f]{32}$"),
]
"""Opaque persisted asset identity; different assets carry different references."""


class M720IdentifierScheme(StrEnum):
    """How an asset's official identifier is expressed (type 2 positions 131-189)."""

    IBAN = "iban"
    """Account identified by IBAN: clave identificación de cuenta ``I`` (pos. 144)."""

    ACCOUNT_CODE = "account_code"
    """Account identified by the bank's own code: clave ``O`` (pos. 144)."""

    ISIN = "isin"
    """Security or IIC share with an ISIN: clave de identificación ``1`` (pos. 131)."""

    NO_ISIN_ISSUER_COUNTRY = "no_isin_issuer_country"
    """Foreign security without an ISIN: clave ``2``, written ``Z`` + issuer country."""

    NONE = "none"
    """No identifier field exists for the class (S and B)."""


#: The identifier schemes the record design admits for each position-102 class.
_SCHEMES_BY_CLASS: Final[dict[M720AssetClassCode, frozenset[M720IdentifierScheme]]] = {
    M720AssetClassCode.CUENTA: frozenset({M720IdentifierScheme.IBAN, M720IdentifierScheme.ACCOUNT_CODE}),
    M720AssetClassCode.VALOR: frozenset({M720IdentifierScheme.ISIN, M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY}),
    M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA: frozenset(
        {M720IdentifierScheme.ISIN, M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY},
    ),
    M720AssetClassCode.SEGURO: frozenset({M720IdentifierScheme.NONE}),
    M720AssetClassCode.BIEN_INMUEBLE: frozenset({M720IdentifierScheme.NONE}),
}

#: Schemes whose official value identifies one asset, so a duplicate is a collision.
_UNIQUE_SCHEMES: Final = frozenset(
    {M720IdentifierScheme.IBAN, M720IdentifierScheme.ACCOUNT_CODE, M720IdentifierScheme.ISIN},
)

#: Position-103 subclaves per class; ``I`` is written as zero (no subclave).
_SUBCLAVES_BY_CLASS: Final[dict[M720AssetClassCode, frozenset[int]]] = {
    M720AssetClassCode.CUENTA: frozenset({1, 2, 3, 4, 5}),
    M720AssetClassCode.VALOR: frozenset({1, 2, 3}),
    M720AssetClassCode.INSTITUCION_INVERSION_COLECTIVA: frozenset(),
    M720AssetClassCode.SEGURO: frozenset({1, 2}),
    M720AssetClassCode.BIEN_INMUEBLE: frozenset({1, 2, 3, 4, 5}),
}


def _validate_iban_identifier(value: str) -> None:
    if value != normalise_iban(value) or not IBAN_SHAPE_RE.match(value):
        raise ForeignAssetRegisterValidationError("IBAN must be canonical: uppercase, no separators")
    if iban_mod_97(value) != 1:
        raise ForeignAssetRegisterValidationError("IBAN check digits do not verify")


def _validate_issuer_country_identifier(value: str) -> None:
    # Positions 132-143: "se reflejará la clave ZXX, siendo XX el código del país emisor".
    if len(value) != 3 or not value.startswith("Z") or not value[1:].isalpha():
        raise ForeignAssetRegisterValidationError(
            "a security without ISIN is written Z plus the issuer country",
        )
    if value != value.upper():
        raise ForeignAssetRegisterValidationError("issuer country code must be uppercase")


class M720AssetIdentifier(BaseModel):
    """An asset's official identifier and the scheme it is written under."""

    model_config = STRICT_FROZEN_CONFIG

    scheme: M720IdentifierScheme
    value: str = Field(default="", max_length=34)

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _value_matches_scheme(self) -> M720AssetIdentifier:
        if self.scheme is M720IdentifierScheme.NONE:
            if self.value:
                raise ForeignAssetRegisterValidationError("an asset class without an identifier carries no value")
            return self
        if not self.value:
            raise ForeignAssetRegisterValidationError(f"identifier scheme {self.scheme.value!r} requires a value")
        if self.scheme is M720IdentifierScheme.IBAN:
            _validate_iban_identifier(self.value)
        elif self.scheme is M720IdentifierScheme.ISIN:
            if not is_valid_isin(self.value):
                raise ForeignAssetRegisterValidationError("ISIN shape or check digit does not verify")
        elif self.scheme is M720IdentifierScheme.NO_ISIN_ISSUER_COUNTRY:
            _validate_issuer_country_identifier(self.value)
        return self


class ForeignAssetRegisterEntry(BaseModel):
    """One foreign asset known to the declarant, identified by its :data:`M720AssetRef`.

    ``held_since`` and ``ceased_on`` bound the period in which the declarant
    held the asset in any position-76 condition. RD 1065/2007 art. 42 bis.1
    reaches what is held "a 31 de diciembre de cada año", and art. 42 bis.3 and
    .5 make a holder who ceased during the year report it in that year's
    declaration; outside that period the asset belongs to no declaration.
    """

    model_config = STRICT_FROZEN_CONFIG

    asset_ref: M720AssetRef
    asset_class: M720AssetClassCode
    subclave: int | None = None
    country_code: CountryCodeAlpha2
    identifier: M720AssetIdentifier
    description: str = Field(min_length=1, max_length=200)
    held_since: date
    ceased_on: date | None = None
    schema_version: str = FOREIGN_ASSET_REGISTER_SCHEMA_VERSION

    @field_validator("schema_version")
    @classmethod
    @pydantic_validation_boundary
    def _schema_version_supported(cls, value: str) -> str:
        if value != FOREIGN_ASSET_REGISTER_SCHEMA_VERSION:
            raise ForeignAssetRegisterValidationError(f"unsupported foreign-asset entry schema_version {value!r}")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _class_invariants(self) -> ForeignAssetRegisterEntry:
        allowed_subclaves = _SUBCLAVES_BY_CLASS[self.asset_class]
        if not allowed_subclaves:
            if self.subclave is not None:
                raise ForeignAssetRegisterValidationError("clave I carries no subclave (position 103 is zero)")
        elif self.subclave not in allowed_subclaves:
            raise ForeignAssetRegisterValidationError(
                f"subclave {self.subclave!r} is not defined for clave {self.asset_class.value!r}",
            )
        if self.identifier.scheme not in _SCHEMES_BY_CLASS[self.asset_class]:
            raise ForeignAssetRegisterValidationError(
                f"identifier scheme {self.identifier.scheme.value!r} is not admitted for clave "
                f"{self.asset_class.value!r}",
            )
        if self.ceased_on is not None and self.ceased_on < self.held_since:
            raise ForeignAssetRegisterValidationError("an asset cannot cease before it was first held")
        return self

    def held_in(self, filing_year: int) -> bool:
        """Whether the declarant held the asset at any time in ``filing_year``."""
        return self.held_since <= date(filing_year, 12, 31) and (
            self.ceased_on is None or self.ceased_on >= date(filing_year, 1, 1)
        )

    def ceased_in(self, filing_year: int) -> bool:
        """Whether the declarant stopped holding the asset during ``filing_year``."""
        return self.ceased_on is not None and self.ceased_on.year == filing_year

    @property
    def identity_key(self) -> tuple[str, str, str] | None:
        """The official key that must not repeat, or ``None`` when the scheme is not unique."""
        if self.identifier.scheme not in _UNIQUE_SCHEMES:
            return None
        return (self.asset_class.value, self.identifier.scheme.value, self.identifier.value)


class M720DeclarantCondition(StrEnum):
    """Position 76 clave de condición del declarante."""

    TITULAR = "1"
    REPRESENTANTE = "2"
    AUTORIZADO = "3"
    BENEFICIARIO = "4"
    USUFRUCTUARIO = "5"
    TOMADOR = "6"
    PODER_DISPOSICION = "7"
    OTRAS_TITULARIDAD_REAL = "8"


class ForeignAssetDeclarationEntry(BaseModel):
    """The operator-owned facts of one type 2 record, keyed by asset and condition.

    Carries only fields the source observation cannot supply (amendment, slot
    ownership). Source-owned slots (class, country, identifier, incorporation
    date, valuation 1) never appear here.
    """

    model_config = STRICT_FROZEN_CONFIG

    asset_ref: M720AssetRef
    condition: M720DeclarantCondition
    titularidad_detail: str | None = Field(default=None, min_length=1, max_length=25)
    participation_pct: Percentage
    """Position 476-480: the declarant's share, two decimals; 100 for a sole declarant."""
    schema_version: str = FOREIGN_ASSET_REGISTER_SCHEMA_VERSION

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _titularidad_only_for_condition_8(self) -> ForeignAssetDeclarationEntry:
        # Position 77-101: informed only when position 76 is "8".
        is_other = self.condition is M720DeclarantCondition.OTRAS_TITULARIDAD_REAL
        if is_other and self.titularidad_detail is None:
            raise ForeignAssetRegisterValidationError("condition 8 requires the tipo de titularidad (pos. 77-101)")
        if not is_other and self.titularidad_detail is not None:
            raise ForeignAssetRegisterValidationError("tipo de titularidad is informed only for condition 8")
        if self.participation_pct <= Decimal("0") or self.participation_pct != self.participation_pct.quantize(
            Decimal("0.01"),
        ):
            raise ForeignAssetRegisterValidationError("participation is positive with at most two decimals")
        return self

    @property
    def key(self) -> tuple[str, str]:
        """The declaration key ``(asset_ref, condition)``."""
        return (self.asset_ref, self.condition.value)


class ForeignAssetRegister(BaseModel):
    """Encrypted register document: the declarant's foreign assets and declarations."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: str = FOREIGN_ASSET_REGISTER_SCHEMA_VERSION
    assets: tuple[ForeignAssetRegisterEntry, ...] = ()
    declarations: tuple[ForeignAssetDeclarationEntry, ...] = ()

    @field_validator("schema_version")
    @classmethod
    @pydantic_validation_boundary
    def _schema_version_supported(cls, value: str) -> str:
        if value != FOREIGN_ASSET_REGISTER_SCHEMA_VERSION:
            raise ForeignAssetRegisterValidationError(f"unsupported foreign-asset register schema_version {value!r}")
        return value

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _register_invariants(self) -> ForeignAssetRegister:
        refs = [asset.asset_ref for asset in self.assets]
        if len(refs) != len(set(refs)):
            raise ForeignAssetRegisterValidationError("register carries a repeated asset_ref")
        keys = [key for asset in self.assets if (key := asset.identity_key) is not None]
        if len(keys) != len(set(keys)):
            raise ForeignAssetRegisterValidationError("register carries two assets with the same official identifier")
        known = set(refs)
        declaration_keys = [declaration.key for declaration in self.declarations]
        if len(declaration_keys) != len(set(declaration_keys)):
            raise ForeignAssetRegisterValidationError("register carries two declarations for one asset and condition")
        unknown = sorted({declaration.asset_ref for declaration in self.declarations} - known)
        if unknown:
            raise ForeignAssetRegisterValidationError(f"declarations name unregistered assets: {unknown}")
        return self

    def asset(self, asset_ref: str) -> ForeignAssetRegisterEntry:
        """Return the entry for ``asset_ref`` or refuse."""
        for asset in self.assets:
            if asset.asset_ref == asset_ref:
                return asset
        raise ForeignAssetRegisterError(f"asset {asset_ref!r} is not registered")


__all__ = [
    "FOREIGN_ASSET_REGISTER_SCHEMA_VERSION",
    "ForeignAssetDeclarationEntry",
    "ForeignAssetRegister",
    "ForeignAssetRegisterEntry",
    "ForeignAssetRegisterError",
    "ForeignAssetRegisterValidationError",
    "M720AssetIdentifier",
    "M720AssetRef",
    "M720DeclarantCondition",
    "M720IdentifierScheme",
]
