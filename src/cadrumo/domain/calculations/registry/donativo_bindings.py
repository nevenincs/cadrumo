"""Donativo (donor) detail-record registry binding helpers.

Modelo 182 (Orden EHA/3021/2007; Ley 49/2002 de mecenazgo) is the annual
informativa an entity that receives donativos, donaciones, or aportaciones
files to declare, per donor, the amounts it received during the year. This is
the "registro tipo 2" per-donor detail row: the entity enrolls one row per
donor naming the donor's tax id, the amount donated, the applicable deducción
percentage (LIRPF art. 68.3 / LIS art. 20), and whether the donation is
recurrent (donativo plurianual a la misma entidad receptora).

The family follows the established detail-record shape (
:mod:`domain.calculations.registry._detail_record_bindings`): a typed
per-row observation model, a strict frozen selector model requiring the
``row_field`` fact with the ``rows`` aggregation op, a build-time validator
registered in the binding validator dispatch table. No production
calculation-route resolver owns this source, so a calculate request carrying
one of these bindings is refused rather than silently blanked.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, BeforeValidator, Field, field_validator

from ....core.aggregation import BindingAggregationOp
from ....core.country_code import CountryCodeAlpha2
from ....core.identity import TaxIdIdentityToken
from ....core.models import STRICT_FROZEN_CONFIG
from .binding_aggregation import binding_aggregation_op
from .binding_selector_utils import (
    BindingExportDataType,
    invariant_diagnostics,
    selector_against_model,
    uppercase_alpha_code,
)
from .binding_selector_utils import selector_as_dict as _selector_as_dict
from .errors import RegistryValidationError
from .schema import DataBindingDefinition
from .schema_base import coerce_enum_member

__all__ = [
    "DonativoDonorObservation",
    "validate_donativo_binding",
]


def _validate_donativo_row_field(
    binding: DataBindingDefinition,
    selector_fact: object,
    selector_row_field: object,
) -> None:
    """Op/fact invariant for the donativo detail-record family.

    Mirrors the shared invariant the four sibling detail-record families
    enforce (:func:`domain.calculations.registry._detail_record_bindings._validate_detail_record_row_field`):
    the donativo family declares exactly the ``row_field`` fact, requires the
    ``rows`` aggregation op, and must name a ``row_field`` selector key.
    """
    if selector_fact != "row_field":
        raise RegistryValidationError(
            f"binding {binding.id!r} declares unsupported donativo fact {selector_fact!r}",
        )
    if binding_aggregation_op(binding) != BindingAggregationOp.ROWS:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires aggregation op 'rows'")
    if selector_row_field is None:
        raise RegistryValidationError(f"binding {binding.id!r} fact 'row_field' requires a 'row_field' selector key")


# ---------------------------------------------------------------------------
# Donativo donor source bindings (modelo 182).
#
# Legal authority: Ley 49/2002 (mecenazgo) establishes the entity's donor
# recordkeeping and certification duties that this informativa discharges;
# Ley 35/2006 art. 68.3 fixes the donor's IRPF deducción percentage; Ley
# 58/2003 art. 93 is the substantive informativa-obligation base; Orden
# EHA/3021/2007 art. 1 approves the modelo 182 form itself, naming the
# donativos/donaciones/aportaciones it declares.
# ---------------------------------------------------------------------------


class DonativoRowField(StrEnum):
    """A field of one donativo detail row."""

    DONOR_TAX_ID = "donor_tax_id"
    DONOR_LEGAL_NAME = "donor_legal_name"
    AMOUNT_DONATED = "amount_donated"
    DEDUCTION_PERCENTAGE = "deduction_percentage"
    IS_RECURRENT = "is_recurrent"


_DonativoRowField = Annotated[DonativoRowField, BeforeValidator(coerce_enum_member(DonativoRowField))]
"""Registry token hydrated into a DonativoRowField member."""


class DonativoDonorObservation(BaseModel):
    """One per-donor donativo observation for modelo 182 (registro tipo 2)."""

    model_config = STRICT_FROZEN_CONFIG

    source_id: str = Field(min_length=1, max_length=128)
    donor_tax_id: TaxIdIdentityToken
    donor_legal_name: str = Field(default="", max_length=200)
    country_code: CountryCodeAlpha2 = "ES"
    transaction_date: date
    amount_donated: Decimal
    deduction_percentage: Decimal
    is_recurrent: bool = False

    _country_code_uppercase = field_validator("country_code")(uppercase_alpha_code("country_code"))

    @field_validator("amount_donated")
    @classmethod
    def _decimal_amount(cls, value: Decimal) -> Decimal:
        if value < Decimal("0"):
            raise RegistryValidationError("amount_donated must be non-negative")
        return value

    @field_validator("deduction_percentage")
    @classmethod
    def _percentage_within_bounds(cls, value: Decimal) -> Decimal:
        if value < Decimal("0") or value > Decimal("100"):
            raise RegistryValidationError("deduction_percentage must be within [0, 100]")
        return value


class _DonativoSelector(BaseModel):
    model_config = STRICT_FROZEN_CONFIG

    fact: Literal["row_field"]
    row_field: _DonativoRowField | None = None
    grouping: str | None = Field(default=None, min_length=1, max_length=64)
    record: str | None = Field(default=None, min_length=1, max_length=64)
    data_type: BindingExportDataType | None = None
    """Scalar type of the value this row field contributes to the export.

    The same fact ``BindingRowExportSelector.data_type`` carries; declared here
    so the selector model admits the key, since a source-family selector is
    validated whole against its own strict model. Optional while the families
    adopt it.
    """


def _validated_donativo_selector(binding: DataBindingDefinition) -> _DonativoSelector:
    try:
        selector = _DonativoSelector.model_validate(_selector_as_dict(binding))
    except ValueError as exc:
        raise RegistryValidationError(f"binding {binding.id!r} has malformed donativo selector") from exc
    _validate_donativo_row_field(binding, selector.fact, selector.row_field)
    return selector


def validate_donativo_binding(binding: DataBindingDefinition) -> list[str]:
    """Validate a donativo-donor binding at registry-build time.

    Accumulating ``list[str]`` validator: validates the selector against
    :class:`_DonativoSelector` and lifts the resolve-time op/fact invariant to
    build time, preserving the underlying pydantic field error.
    """
    failures = selector_against_model(binding, _DonativoSelector)
    if failures:
        return failures
    return invariant_diagnostics(binding, "donativo", lambda b: _validated_donativo_selector(b))


DonativoSelector = _DonativoSelector
