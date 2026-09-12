"""Typed Modelo 210 income-classification boundary.

The selected Modelo 210 registry revision owns the income-code catalogue,
labels, and payer applicability. This module retains only the transaction
validation/type shell while that registry declaration is consumed by the
calculation path.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.irnr import M210PayerMode
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.unit_proportion import UnitProportion
from ..calculations.registry.authority import bundled_authority
from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
from ..calculations.registry.queries import RegistryQueryService
from ..calculations.registry.schema_base import DateAxis
from .errors import TransactionValidationError


def _registry_m210_declarations() -> tuple[frozenset[str], frozenset[str], str]:
    """Resolve the selected M210 code and payer-applicability declarations."""
    effective_date = date.today()
    authority = bundled_authority()
    report = RegistryQueryService(authority).describe_modelo("210", as_of=effective_date)
    revision = authority.modelo("210").revisions.get(report.revision)
    if revision is None:
        raise TransactionValidationError("selected M210 registry revision is unavailable")
    code_parameter = next(
        (parameter for parameter in revision.parameters if "tipo-renta-code" in str(parameter.id)),
        None,
    )
    payer_parameter = next(
        (parameter for parameter in revision.parameters if "multiple-payers" in str(parameter.id)),
        None,
    )
    if code_parameter is None or payer_parameter is None:
        raise TransactionValidationError("selected M210 registry revision lacks income-code declarations")
    resolved = authority.resolve_governed_fact(
        MappingFactQuery(
            fact_id="detail-m349-m210-catalogues",
            date_axis=DateAxis.FILING_PERIOD,
            effective_date=effective_date,
        ),
    )
    if not isinstance(resolved, ResolvedMappingFact):
        raise TransactionValidationError("detail M349/M210 catalogue must resolve as a mapping fact")
    mode_entries = {
        str(entry.key): str(entry.value)
        for entry in resolved.payload.entries
        if str(entry.key).startswith("m210.code") and str(entry.key).endswith(".payer_mode")
    }
    if not mode_entries:
        raise TransactionValidationError("detail M349/M210 catalogue lacks payer-mode declarations")
    required_mode = next(iter(mode_entries.values()))
    return (
        frozenset(str(entry.key) for entry in code_parameter.keyed_brackets),
        frozenset(str(entry.key) for entry in payer_parameter.keyed_brackets),
        required_mode,
    )


class M210IncomeClassification(BaseModel):
    """One operator-supplied M210 income classification."""

    model_config = STRICT_FROZEN_CONFIG

    official_tipo_renta_code: str = Field(min_length=2, max_length=2)
    gross_income_amount: Decimal = Field(ge=Decimal("0"))
    applicable_rate: UnitProportion
    payer_mode: M210PayerMode = M210PayerMode.SINGLE_PAYER
    payer_id: str | None = Field(default=None, min_length=1, max_length=128)
    asset_or_right_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("official_tipo_renta_code")
    @classmethod
    def _validate_official_tipo_renta_code(cls, value: str) -> str:
        code = value.strip()
        if not code.isdecimal():
            raise TransactionValidationError(
                "official_tipo_renta_code must be a two-character numeric code",
            )
        code_catalogue, _, _ = _registry_m210_declarations()
        if code not in code_catalogue:
            raise TransactionValidationError("official_tipo_renta_code is not declared by the selected registry")
        return code

    @field_validator("payer_mode", mode="before")
    @classmethod
    def _coerce_payer_mode(cls, value: object) -> object:
        if isinstance(value, str) and not isinstance(value, M210PayerMode):
            return M210PayerMode(value)
        return value

    @field_validator("payer_id", "asset_or_right_id")
    @classmethod
    def _trim_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="after")
    def _validate_registry_payer_applicability(self) -> M210IncomeClassification:
        _, multiple_payer_codes, required_mode = _registry_m210_declarations()
        if self.official_tipo_renta_code in multiple_payer_codes and self.payer_mode.value != required_mode:
            raise TransactionValidationError(
                "official_tipo_renta_code requires the registry-declared payer mode",
            )
        return self


__all__ = ["M210IncomeClassification"]
