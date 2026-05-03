"""Trace records emitted by registry-backed calculations."""

from __future__ import annotations

from collections.abc import Mapping
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CalculationTrace(BaseModel):
    """Auditable trace for one registry-backed calculation run."""

    model_config = ConfigDict(strict=True, frozen=True, extra="forbid")

    modelo: str
    revision: str
    legal_refs: tuple[str, ...]
    source_refs: tuple[str, ...]
    formula_order: tuple[str, ...]
    inputs: Mapping[str, Decimal]
    outputs: Mapping[str, Decimal]
