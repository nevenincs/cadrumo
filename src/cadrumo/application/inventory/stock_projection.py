"""Inventory stock-layer and acquisition summary wire projections."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, NonNegativeInt, PositiveInt

from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ..operations.public_scalar import PublicDecimal


class InventoryStockLayerProjection(BaseModel):
    """One exact stock layer with no omitted or truncated numeric fields."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    sku: str
    quantity: PublicDecimal
    unit_cost: PublicDecimal
    source_movement_id: str


class InventoryAcquisitionCostProjection(BaseModel):
    """Safe totals and counts without component, evidence, or digest values."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG

    consideration_excluding_iva: PublicDecimal
    directly_attributable_cost_total: PublicDecimal
    nonrecoverable_iva_included: PublicDecimal
    recoverable_iva_excluded: PublicDecimal
    total_acquisition_cost: PublicDecimal
    component_count: NonNegativeInt
    evidence_count: PositiveInt
    complete: Literal[True]
