"""Typed Modelo 210 income-classification boundary.

The selected Modelo 210 registry revision owns the income-code catalogue,
labels, and payer applicability. This module retains only the transaction
validation/type shell while that registry declaration is consumed by the
calculation path.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, field_validator, model_validator

from ...core.errors.hierarchy import pydantic_validation_boundary
from ...core.irnr import M210PayerMode
from ...core.models import STRICT_FROZEN_CONFIG
from ...core.time.clock import today_madrid
from ...core.unit_proportion import UnitProportion
from .errors import TransactionValidationError

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation


def _resolved_m210_detail_declarations(
    effective_date: date,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> Mapping[str, str]:
    """Resolve the selected detail catalogue as string declarations."""
    # Registry resolution loads the authority tree; the model itself must stay
    # importable without it.
    from ..calculations.registry.authority import bundled_indexed_authority
    from ..calculations.registry.facts.resolution import MappingFactQuery, ResolvedMappingFact
    from ..calculations.registry.schema_base import DateAxis

    query = MappingFactQuery(
        fact_id="detail-m349-m210-catalogues",
        date_axis=DateAxis.FILING_PERIOD,
        effective_date=effective_date,
    )
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return _resolved_m210_detail_declarations(effective_date, operation=indexed_operation)
    resolved = operation.resolve_governed_fact(query)
    if not isinstance(resolved, ResolvedMappingFact):
        raise TransactionValidationError("detail M349/M210 catalogue must resolve as a mapping fact")
    return {str(entry.key): str(entry.value) for entry in resolved.payload.entries}


def _registry_m210_payer_mode_declarations(
    effective_date: date | None = None,
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[frozenset[str], str, Mapping[str, str]]:
    """Resolve payer-mode membership, default, and model applicability."""
    as_of = effective_date or today_madrid()
    declarations = _resolved_m210_detail_declarations(as_of, operation=operation)
    order_text = declarations.get("m210.payer_mode_order")
    default_mode = declarations.get("m210.payer_mode.default")
    if order_text is None or default_mode is None:
        raise TransactionValidationError("detail M349/M210 catalogue lacks payer-mode membership")
    modes = tuple(token.strip() for token in order_text.split(",") if token.strip())
    if not modes or len(modes) != len(set(modes)):
        raise TransactionValidationError("detail M349/M210 catalogue has invalid payer-mode membership")
    for mode in modes:
        if declarations.get(f"m210.payer_mode.{mode}.value") != mode:
            raise TransactionValidationError(f"payer-mode declaration is missing canonical value for {mode!r}")
        applicable_modelos = tuple(
            token.strip()
            for token in declarations.get(f"m210.payer_mode.{mode}.modelos", "").split(",")
            if token.strip()
        )
        if not applicable_modelos:
            raise TransactionValidationError(f"payer-mode declaration is missing model applicability for {mode!r}")
    if default_mode not in modes:
        raise TransactionValidationError("detail M349/M210 catalogue declares an unknown payer-mode default")
    return frozenset(modes), default_mode, declarations


def resolve_m210_payer_mode(
    value: object | None = None,
    *,
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> M210PayerMode:
    """Project an operator or stored payer-mode token from the detail fact."""
    modes, default_mode, _ = _registry_m210_payer_mode_declarations(effective_date, operation=operation)
    if value is None:
        return M210PayerMode.from_registry(default_mode)
    if isinstance(value, M210PayerMode):
        if value.value not in modes:
            raise TransactionValidationError("payer-mode token is not declared by the selected registry")
        return value
    if not isinstance(value, str) or value not in modes:
        raise TransactionValidationError("payer-mode token is not declared by the selected registry")
    return M210PayerMode.from_registry(value)


def required_m210_payer_mode_for_code(
    code: object,
    *,
    effective_date: date | None = None,
    operation: PinnedAuthorityOperation | None = None,
) -> M210PayerMode | None:
    """Return the payer mode required for one registry-declared income code."""
    normalized_code = code.strip() if isinstance(code, str) else ""
    modes, _, declarations = _registry_m210_payer_mode_declarations(effective_date, operation=operation)
    required_mode = declarations.get(f"m210.code{normalized_code}.payer_mode")
    if required_mode is None:
        return None
    if required_mode not in modes:
        raise TransactionValidationError("detail M349/M210 catalogue declares an unknown required payer mode")
    return M210PayerMode.from_registry(required_mode)


def _registry_m210_declarations(
    *,
    operation: PinnedAuthorityOperation | None = None,
) -> tuple[frozenset[str], frozenset[str], M210PayerMode]:
    """Resolve the selected M210 code and payer-applicability declarations."""
    from ..calculations.registry.authority import bundled_indexed_authority
    from ..calculations.registry.temporal import select_revision_metadata_for_year

    effective_date = today_madrid()
    if operation is None:
        with bundled_indexed_authority().operation() as indexed_operation:
            return _registry_m210_declarations(operation=indexed_operation)
    directory = operation.modelo_directory("210")
    selected = select_revision_metadata_for_year(
        directory,
        filing_year=effective_date.year,
        on=effective_date,
    )
    revision = operation.revision("210", str(selected.id))
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
    required_mode = required_m210_payer_mode_for_code(
        "35",
        effective_date=effective_date,
        operation=operation,
    )
    if required_mode is None:
        raise TransactionValidationError("detail M349/M210 catalogue lacks code-35 payer-mode declaration")
    return (
        frozenset(str(entry.key) for entry in code_parameter.keyed_brackets),
        frozenset(str(entry.key) for entry in payer_parameter.keyed_brackets),
        required_mode,
    )


def _default_m210_payer_mode() -> M210PayerMode:
    """Return the registry-declared payer mode for a classification that names none."""
    return resolve_m210_payer_mode()


class M210IncomeClassification(BaseModel):
    """One operator-supplied M210 income classification."""

    model_config = STRICT_FROZEN_CONFIG

    official_tipo_renta_code: str = Field(min_length=2, max_length=2)
    gross_income_amount: Decimal = Field(ge=Decimal("0"))
    applicable_rate: UnitProportion
    # A registry-derived default rather than a model-level before-validator: a
    # validator returning a rebuilt mapping hands the fields Python input, and
    # the strict config then refuses the JSON-decoded amounts of a stored row.
    payer_mode: M210PayerMode = Field(default_factory=_default_m210_payer_mode)
    payer_id: str | None = Field(default=None, min_length=1, max_length=128)
    asset_or_right_id: str | None = Field(default=None, min_length=1, max_length=128)

    @field_validator("official_tipo_renta_code")
    @classmethod
    @pydantic_validation_boundary
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
    @pydantic_validation_boundary
    def _coerce_payer_mode(cls, value: object) -> object:
        return resolve_m210_payer_mode(value)

    @field_validator("payer_id", "asset_or_right_id")
    @classmethod
    def _trim_optional_identity(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_registry_payer_applicability(self) -> M210IncomeClassification:
        _, multiple_payer_codes, required_mode = _registry_m210_declarations()
        if self.official_tipo_renta_code in multiple_payer_codes and self.payer_mode != required_mode:
            raise TransactionValidationError(
                "official_tipo_renta_code requires the registry-declared payer mode",
            )
        return self


__all__ = [
    "M210IncomeClassification",
    "required_m210_payer_mode_for_code",
    "resolve_m210_payer_mode",
]
