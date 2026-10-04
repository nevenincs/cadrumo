"""Typed business-premises lease facts captured on an issued invoice."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from .errors import InvoiceValidationError


class SituacionInmueble(StrEnum):
    """Modelo 347 situation codes for the leased premises."""

    SPAIN_OTHER_THAN_BASQUE_NAVARRE = "1"
    BASQUE_COUNTRY_OR_NAVARRE = "2"
    SPAIN_WITHOUT_CATASTRAL_REFERENCE = "3"
    ABROAD = "4"


SITUACIONES_CON_REFERENCIA_CATASTRAL = frozenset(
    {SituacionInmueble.SPAIN_OTHER_THAN_BASQUE_NAVARRE, SituacionInmueble.BASQUE_COUNTRY_OR_NAVARRE}
)


def require_situacion_inmueble(value: object) -> SituacionInmueble:
    """Normalize one of the four situation codes, otherwise refuse it."""
    if isinstance(value, SituacionInmueble):
        return value
    if isinstance(value, str):
        try:
            return SituacionInmueble(value.strip())
        except ValueError as exc:
            raise InvoiceValidationError("situacion_inmueble must be 1, 2, 3 or 4") from exc
    raise InvoiceValidationError("situacion_inmueble must be 1, 2, 3 or 4")


class BusinessPremisesLease(BaseModel):
    """The lessor's captured lease facts; missing premises detail stays explicit."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    situacion_inmueble: SituacionInmueble | None = None
    referencia_catastral: str | None = Field(default=None, max_length=25)

    @field_validator("situacion_inmueble", mode="before")
    @classmethod
    @pydantic_validation_boundary
    def _normalize_situation(cls, value: object) -> object:
        if value is None:
            return None
        return require_situacion_inmueble(value)

    @field_validator("referencia_catastral", mode="before")
    @classmethod
    def _normalize_reference(cls, value: object) -> object:
        if not isinstance(value, str):
            return value
        return value.strip().upper() or None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_reference_situation(self) -> BusinessPremisesLease:
        if self.referencia_catastral is not None and self.situacion_inmueble in {
            SituacionInmueble.SPAIN_WITHOUT_CATASTRAL_REFERENCE,
            SituacionInmueble.ABROAD,
        }:
            raise InvoiceValidationError("situaciones 3 and 4 cannot carry one")
        return self


def business_premises_lease_from_inputs(
    *,
    lease_selected: bool,
    situacion_inmueble: object = None,
    referencia_catastral: object = None,
) -> BusinessPremisesLease | None:
    """Convert existing CLI/TUI fields into the one typed aggregate value."""
    if type(lease_selected) is not bool:
        raise InvoiceValidationError("lease_selected must be a boolean")
    candidate = BusinessPremisesLease.model_validate(
        {
            "situacion_inmueble": situacion_inmueble,
            "referencia_catastral": referencia_catastral,
        }
    )
    if not lease_selected:
        if candidate.situacion_inmueble is not None or candidate.referencia_catastral is not None:
            raise InvoiceValidationError("premises facts require the business-premises lease choice")
        return None
    return candidate


def normalise_legacy_business_premises_lease(payload: dict[str, object]) -> dict[str, object]:
    """Hydrate historical flat invoice facts into the sole nested lease family.

    Older encrypted catalogues carry these three fields on the invoice. Keep
    their recorded facts, refuse contradictions with a concurrently supplied
    nested family, and emit only the current canonical representation.
    """
    legacy_fields = ("arrendamiento_local_negocio", "situacion_inmueble", "referencia_catastral")
    if not any(field in payload for field in legacy_fields):
        return payload
    migrated = dict(payload)
    selected = migrated.pop("arrendamiento_local_negocio", False)
    if type(selected) is not bool:
        raise InvoiceValidationError("arrendamiento_local_negocio must be a boolean")
    legacy = business_premises_lease_from_inputs(
        lease_selected=selected,
        situacion_inmueble=migrated.pop("situacion_inmueble", None),
        referencia_catastral=migrated.pop("referencia_catastral", None),
    )
    if "business_premises_lease" in migrated:
        nested = migrated["business_premises_lease"]
        if nested is not None and not isinstance(nested, BusinessPremisesLease):
            nested = BusinessPremisesLease.model_validate(nested)
        if nested != legacy:
            raise InvoiceValidationError("historical and nested business-premises lease facts disagree")
    migrated["business_premises_lease"] = legacy
    return migrated


__all__ = [
    "SITUACIONES_CON_REFERENCIA_CATASTRAL",
    "BusinessPremisesLease",
    "SituacionInmueble",
    "business_premises_lease_from_inputs",
    "normalise_legacy_business_premises_lease",
    "require_situacion_inmueble",
]
