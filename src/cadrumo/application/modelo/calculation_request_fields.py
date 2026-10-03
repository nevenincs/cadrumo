"""Typed operator input channels for registered Modelo calculation."""

from __future__ import annotations

from decimal import Decimal
from typing import TYPE_CHECKING, Annotated

from pydantic import BaseModel, Field, field_validator

from ...core.decimal.grammar import try_parse_canonical_decimal
from ...core.filing_year import FilingYear
from ...core.irnr import M210GrossIncomeSourceMode
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.rescate_type import RescateType
from .calculate_input import WorkCalculateInputBundle, build_work_calculate_input_bundle

if TYPE_CHECKING:
    from ...domain.modelos.calculation_revision_m303_handoff import FilingInstanceEvidence
    from ...domain.modelos.row_models import ModeloDetailRow
    from .calculation_action_ports import CalculationActionPorts
    from .work_profile import ModeloWorkProfile


class ModeloCalculationOverride(BaseModel):
    """One caller token; its declared channel is resolved by the pinned registry."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    key: Annotated[str, Field(min_length=1, max_length=256)]
    value: Annotated[str, Field(max_length=4096)]


class ModeloCalculationInputFieldsV1(BaseModel):
    """Complete scalar channels, retaining raw text until canonical validation.

    Detail rows and ordinary-M303 evidence have their own typed request fields.
    This object contains no backend values, source provenance or tax readiness
    claims; those remain produced by the application calculation service.
    """

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    casilla_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)
    binding_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)
    relation_overrides: tuple[ModeloCalculationOverride, ...] = Field(default=(), max_length=20_000)
    borrador_snapshot_id: str | None = Field(default=None, min_length=1, max_length=128)
    m210_gross_income_source_mode: M210GrossIncomeSourceMode = M210GrossIncomeSourceMode.MANUAL
    prestacion_inss_exenta: str | None = None
    rescate_plan_pensiones_capital: str | None = None
    rescate_plan_pensiones_aportaciones_pre_2007: str | None = None
    rescate_plan_pensiones_aportaciones_totales: str | None = None
    rescate_type: RescateType | None = None
    contingencia_year: FilingYear | None = None
    rescate_year: FilingYear | None = None
    sal_beneficio_neto: str | None = None
    sal_reserva_dotada: str | None = None
    sal_capital_social: str | None = None
    autoconsumo_promotor_base: str | None = None

    @field_validator("casilla_overrides", "binding_overrides", "relation_overrides")
    @classmethod
    def _unique_keys(cls, values: tuple[ModeloCalculationOverride, ...]) -> tuple[ModeloCalculationOverride, ...]:
        if len({item.key for item in values}) != len(values):
            raise ValueError("calculation input channel contains duplicate keys")
        return values

    @field_validator(
        "prestacion_inss_exenta",
        "rescate_plan_pensiones_capital",
        "rescate_plan_pensiones_aportaciones_pre_2007",
        "rescate_plan_pensiones_aportaciones_totales",
        "sal_beneficio_neto",
        "sal_reserva_dotada",
        "sal_capital_social",
        "autoconsumo_promotor_base",
    )
    @classmethod
    def _decimal_token(cls, value: str | None) -> str | None:
        if value is not None and try_parse_canonical_decimal(value) is None:
            raise ValueError("calculation amount must use canonical finite decimal text")
        return value

    def build_bundle(
        self,
        *,
        work_unit_id: str,
        ports: CalculationActionPorts,
        profile: ModeloWorkProfile | None,
        detail_rows: tuple[ModeloDetailRow, ...],
        filing_instance_evidence: FilingInstanceEvidence | None,
    ) -> WorkCalculateInputBundle:
        """Delegate all membership, channel, grouped-input and shortcut policy."""
        return build_work_calculate_input_bundle(
            work_unit_id=work_unit_id,
            ports=ports,
            profile=profile,
            operation=ports.operation,
            casilla_overrides={item.key: item.value for item in self.casilla_overrides},
            binding_overrides={item.key: item.value for item in self.binding_overrides},
            relation_overrides={item.key: item.value for item in self.relation_overrides},
            detail_rows=detail_rows,
            borrador_snapshot_id=self.borrador_snapshot_id,
            filing_instance_evidence=filing_instance_evidence,
            m210_gross_income_source_mode=self.m210_gross_income_source_mode,
            prestacion_inss_exenta=_amount(self.prestacion_inss_exenta),
            rescate_plan_pensiones_capital=_amount(self.rescate_plan_pensiones_capital),
            rescate_plan_pensiones_aportaciones_pre_2007=_amount(self.rescate_plan_pensiones_aportaciones_pre_2007),
            rescate_plan_pensiones_aportaciones_totales=_amount(self.rescate_plan_pensiones_aportaciones_totales),
            rescate_plan_pensiones_tipo=self.rescate_type,
            rescate_plan_pensiones_contingencia_year=self.contingencia_year,
            rescate_plan_pensiones_rescate_year=self.rescate_year,
            sal_beneficio_neto=_amount(self.sal_beneficio_neto),
            sal_reserva_dotada=_amount(self.sal_reserva_dotada),
            sal_capital_social=_amount(self.sal_capital_social),
            autoconsumo_promotor_base=_amount(self.autoconsumo_promotor_base),
        )


def _amount(value: str | None) -> Decimal | None:
    """Decode only tokens that already passed the public finite-decimal gate."""
    return None if value is None else Decimal(value)


__all__ = ["ModeloCalculationInputFieldsV1", "ModeloCalculationOverride"]
