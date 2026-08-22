"""Closed identities shared by calculation-route owners and operator projections."""

from __future__ import annotations

from enum import StrEnum


class ModeloCalculationRouteId(StrEnum):
    """Canonical production route used to calculate a modelo work unit."""

    MODELO_WORK_CALCULATION = "modelo_work_calculation"


__all__ = ["ModeloCalculationRouteId"]
