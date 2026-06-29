"""Filed-state comparison for registry calculation outputs."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG, Period
from ._bindings import CasillaObservation, RegistryModeloObservation
from ._errors import RegistryValidationError
from ._formula_runtime import RegistryCalculationResult
from ._ids import CasillaId, ModeloId

__all__ = [
    "RegistryFiledStateComparison",
    "RegistryFiledStateDrift",
    "compare_calculation_to_filed_observation",
]


class RegistryFiledStateDrift(BaseModel):
    """One casilla whose local calculation does not match filed AEAT state.

    ``formula_id``, ``legal_refs``, and ``source_refs`` carry the
    regulatory grounding for the casilla from the typed calculation
    observation.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    local_value: Decimal
    filed_value: Decimal
    delta: Decimal
    formula_id: str | None = None
    legal_refs: tuple[str, ...] = Field(min_length=1)
    source_refs: tuple[str, ...] = Field(min_length=1)


class RegistryFiledStateComparison(BaseModel):
    """Verdict for one local calculation versus one normalized filed observation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloId
    revision: str = Field(min_length=1)
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    status: Literal["satisfied", "failed"]
    compared_casilla_ids: tuple[CasillaId, ...]
    missing_local_casilla_ids: tuple[CasillaId, ...] = ()
    missing_filed_casilla_ids: tuple[CasillaId, ...] = ()
    drifts: tuple[RegistryFiledStateDrift, ...] = ()

    @field_validator("compared_casilla_ids", "missing_local_casilla_ids", "missing_filed_casilla_ids")
    @classmethod
    def _casilla_ids_unique(cls, value: tuple[CasillaId, ...]) -> tuple[CasillaId, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("casilla ids must be unique")
        return value


def _drift_from_observation(
    *,
    casilla_id: CasillaId,
    local_observation: CasillaObservation | None,
    local_value: Decimal,
    filed_value: Decimal,
) -> RegistryFiledStateDrift:
    if local_observation is None:
        raise RegistryValidationError(
            f"cannot ground filed-state drift for casilla {casilla_id!r}; "
            "calculation.values exposed a value with no CasillaObservation provenance",
        )
    if not local_observation.legal_refs or not local_observation.source_refs:
        raise RegistryValidationError(
            f"cannot ground filed-state drift for casilla {casilla_id!r}; "
            "CasillaObservation is missing legal_refs/source_refs provenance",
        )
    return RegistryFiledStateDrift(
        casilla_id=casilla_id,
        local_value=local_value,
        filed_value=filed_value,
        delta=local_value - filed_value,
        formula_id=local_observation.formula_id,
        legal_refs=local_observation.legal_refs,
        source_refs=local_observation.source_refs,
    )


def compare_calculation_to_filed_observation(
    calculation: RegistryCalculationResult,
    observation: RegistryModeloObservation,
    *,
    required_casilla_ids: Iterable[CasillaId],
) -> RegistryFiledStateComparison:
    """Compare local registry calculation values against filed AEAT casillas.

    Each :class:`RegistryFiledStateDrift` in the returned comparison
    carries ``formula_id``, ``legal_refs``, and ``source_refs`` from the
    typed :class:`CasillaObservation` envelope, so the regulatory
    grounding for every drifted casilla is preserved in the comparison
    result and propagates to CLI / audit surfaces.

    Returns:
        A :class:`RegistryFiledStateComparison` summarising all casilla-level drift.
    """
    if calculation.modelo != observation.modelo:
        raise RegistryValidationError(
            f"cannot compare calculation modelo {calculation.modelo!r} "
            f"with filed observation modelo {observation.modelo!r}",
        )
    target_casilla_ids = tuple(sorted(set(required_casilla_ids)))
    if not target_casilla_ids:
        raise RegistryValidationError("filed-state comparison requires at least one casilla")

    local_values = calculation.values
    filed_values = observation.casilla_values
    observations_by_id = {obs.casilla_id: obs for obs in calculation.observations}
    missing_local = tuple(casilla_id for casilla_id in target_casilla_ids if casilla_id not in local_values)
    missing_filed = tuple(casilla_id for casilla_id in target_casilla_ids if casilla_id not in filed_values)
    comparable = tuple(
        casilla_id for casilla_id in target_casilla_ids if casilla_id in local_values and casilla_id in filed_values
    )
    drifts = tuple(
        _drift_from_observation(
            casilla_id=casilla_id,
            local_observation=observations_by_id.get(casilla_id),
            local_value=local_values[casilla_id],
            filed_value=filed_values[casilla_id],
        )
        for casilla_id in comparable
        if local_values[casilla_id] != filed_values[casilla_id]
    )
    status: Literal["satisfied", "failed"] = (
        "satisfied" if not missing_local and not missing_filed and not drifts else "failed"
    )
    return RegistryFiledStateComparison(
        modelo=calculation.modelo,
        revision=calculation.revision,
        filing_period=observation.filing_period,
        filing_year=observation.filing_year,
        period=observation.period,
        status=status,
        compared_casilla_ids=comparable,
        missing_local_casilla_ids=missing_local,
        missing_filed_casilla_ids=missing_filed,
        drifts=drifts,
    )
