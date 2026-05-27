"""Typed CLI row models for multi-row informational modelos.

Provides strictly-validated pydantic row shapes for operator-supplied
detail rows on modelos whose filing content is a list of repeating
records rather than a set of scalar casilla values.

Supported row types:

* ``Modelo184MemberRow`` — atribución member for modelo 184
  (``--row miembro nif=X share=Y importe=Z``)
* ``Modelo232VinculadaRow`` — operación vinculada for modelo 232
  (``--row vinculada nif=X tipo_vinculacion=Y importe=Z metodo=M pais=P``)

These models are the CLI boundary layer. They validate operator input
and carry enough fields to construct the matching
``AtributionMemberObservation`` / ``RelatedPartyOperationObservation``
that the registry row-resolver consumes.

Modelo 349 (operador intracomunitario) is NOT wired through this
mechanism: its per-operator rows are derived automatically from the
collectible-invoice ledger; there is no manual-entry path.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

# ---------------------------------------------------------------------------
# Shared type aliases
# ---------------------------------------------------------------------------

_NifStr = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20)]
_NameStr = Annotated[str, StringConstraints(strip_whitespace=True, max_length=200)]
_IsoCountryCode = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=2)]


# ---------------------------------------------------------------------------
# Modelo 184 - atribucion de rentas member row
#
# Legal authority: Orden HAP/2250/2015 art. 3; Ley 35/2006 arts. 86-89.
# One row per miembro (socio / comunero / partícipe) of the entity.
# ---------------------------------------------------------------------------


class Modelo184MemberRow(BaseModel):
    """One atribución member row for Modelo 184.

    Fields mirror the per-record Tipo-2 layout declared in the M184
    ``bindings/0001-bindings.toml`` atribucion_member source block.

    Parity assertions:
    * ``nif`` → ``member_tax_id`` (binding: modelo-184-member-row-nif)
    * ``nombre`` → ``member_legal_name`` (binding: modelo-184-member-row-name)
    * ``porcentaje`` → ``share_percentage`` (binding: modelo-184-member-row-share)
    * ``importe`` → ``base_imponible_assigned`` (binding: modelo-184-member-row-base-assigned)
    * ``pais`` → ``country_code`` (ES default)
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    row_type: Literal["miembro"] = "miembro"
    nif: _NifStr
    nombre: _NameStr = Field(default="")
    pais: _IsoCountryCode = Field(default="ES")
    porcentaje: Decimal = Field(description="Share percentage in the entity [0, 100]")
    importe: Decimal = Field(description="Attributed income/base imponible in EUR")

    @field_validator("pais")
    @classmethod
    def _pais_uppercase_alpha(cls, value: str) -> str:
        if value != value.upper() or not value.replace(" ", "").isalpha():
            raise ValueError("pais must be an uppercase two-letter ISO 3166-1 country code (e.g. ES, DE, FR)")
        return value

    @field_validator("porcentaje")
    @classmethod
    def _porcentaje_within_bounds(cls, value: Decimal) -> Decimal:
        if value < Decimal("0") or value > Decimal("100"):
            raise ValueError(f"porcentaje must be within [0, 100]; got {value}")
        return value

    @field_validator("nif")
    @classmethod
    def _nif_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nif cannot be blank")
        return value.upper()


# ---------------------------------------------------------------------------
# Modelo 232 - operacion vinculada row
#
# Legal authority: Orden HFP/816/2017 art. 3; Ley 27/2014 art. 18;
# RD 634/2015 art. 13 (LIS transfer pricing).
# One row per related-party transaction group.
# ---------------------------------------------------------------------------

# Closed catalogue of válid tipo_vinculacion codes per M232 form.
_M232_TIPO_VINCULACION = Literal[
    "1", "2", "3", "4", "5", "6", "7", "8",
    "9", "10", "11", "12", "13", "14", "15", "16",
]

# Closed catalogue of valid tipo_operacion codes per M232 form.
_M232_TIPO_OPERACION = Literal[
    "01", "02", "03", "04", "05", "06", "07", "08",
    "09", "10", "11", "12", "13", "14", "15", "16",
    "17", "18", "19", "20",
]

# Closed catalogue of transfer-pricing method codes per M232 / LIS art. 18.
_M232_METODO = Literal["CUP", "RPM", "CPM", "PS", "TNMM", ""]


class Modelo232VinculadaRow(BaseModel):
    """One operación vinculada row for Modelo 232.

    Fields mirror the related_party_operation binding source declared in
    ``232/revisions/2018-y-siguientes/bindings/0218…0223-*.toml``.

    Parity assertions:
    * ``nif`` → ``counterparty_tax_id`` (binding: modelo-232-related-party-row-nif)
    * ``nombre`` → ``counterparty_legal_name`` (binding: modelo-232-related-party-row-name)
    * ``pais`` → ``country_code`` (binding: modelo-232-related-party-row-country)
    * ``tipo_operacion`` → ``operation_kind_code`` (binding: modelo-232-related-party-row-operation-kind)
    * ``metodo`` → ``transfer_pricing_method_code`` (binding: modelo-232-related-party-row-tpr-method)
    * ``importe`` → ``amount`` (binding: modelo-232-related-party-row-amount)
    """

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    row_type: Literal["vinculada"] = "vinculada"
    nif: _NifStr
    nombre: _NameStr = Field(default="")
    pais: _IsoCountryCode = Field(default="ES")
    tipo_vinculacion: str = Field(default="1", min_length=1, max_length=2)
    tipo_operacion: str = Field(default="01", min_length=1, max_length=2)
    metodo: str = Field(default="", max_length=6)
    importe: Decimal

    @field_validator("pais")
    @classmethod
    def _pais_uppercase_alpha(cls, value: str) -> str:
        if value != value.upper() or not value.replace(" ", "").isalpha():
            raise ValueError("pais must be an uppercase two-letter ISO 3166-1 country code (e.g. ES, DE, FR)")
        return value

    @field_validator("nif")
    @classmethod
    def _nif_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("nif cannot be blank")
        return value.upper()

    @field_validator("metodo")
    @classmethod
    def _metodo_uppercase(cls, value: str) -> str:
        return value.upper()


# ---------------------------------------------------------------------------
# Discriminated union — single type accepted by the CLI --row argument
# ---------------------------------------------------------------------------

ModeloDetailRow = Modelo184MemberRow | Modelo232VinculadaRow

__all__ = [
    "Modelo184MemberRow",
    "Modelo232VinculadaRow",
    "ModeloDetailRow",
]
