"""Filed-state comparison for registry calculation outputs."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ....core import STRICT_FROZEN_CONFIG, Period
from ._bindings import RegistryModeloObservation
from ._errors import RegistryValidationError
from ._formula_runtime import RegistryCalculationResult
from ._ids import CasillaId

__all__ = [
    "RegistryFiledStateComparison",
    "RegistryFiledStateDrift",
    "compare_calculation_to_filed_observation",
]


class RegistryFiledStateDrift(BaseModel):
    """One casilla whose local calculation does not match filed AEAT state.

    ``formula_id``, ``legal_refs``, and ``source_refs`` carry the
    regulatory grounding for the casilla from the calculation engine.
    For formula-computed casillas these are populated from the
    :class:`RegistryCalculationEntry`; for input or bound casillas they
    default to ``None`` / empty tuples.
    """

    model_config = STRICT_FROZEN_CONFIG

    casilla_id: CasillaId
    local_value: Decimal
    filed_value: Decimal
    delta: Decimal
    formula_id: str | None = None
    legal_refs: tuple[str, ...] = ()
    source_refs: tuple[str, ...] = ()


class RegistryFiledStateComparison(BaseModel):
    """Verdict for one local calculation versus one normalized filed observation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: str = Field(min_length=1, max_length=8)
    revision: str = Field(min_length=1)
    filing_period: Period | None = None
    filing_year: int = Field(ge=2000, le=2099)
    period: str = Field(min_length=1, max_length=8)
    status: Literal["satisfied", "failed"]
    compared_casillas: tuple[str, ...]
    missing_local_casillas: tuple[str, ...] = ()
    missing_filed_casillas: tuple[str, ...] = ()
    drifts: tuple[RegistryFiledStateDrift, ...] = ()

    @field_validator("compared_casillas", "missing_local_casillas", "missing_filed_casillas")
    @classmethod
    def _casilla_ids_unique(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise RegistryValidationError("casilla ids must be unique")
        return value


def compare_calculation_to_filed_observation(
    calculation: RegistryCalculationResult,
    observation: RegistryModeloObservation,
    *,
    required_casillas: Iterable[str],
) -> RegistryFiledStateComparison:
    """Compare local registry calculation values against filed AEAT casillas.

    Each :class:`RegistryFiledStateDrift` in the returned comparison
    carries ``formula_id``, ``legal_refs``, and ``source_refs`` from the
    :class:`RegistryCalculationEntry` for formula-computed casillas, so
    the regulatory grounding for every drifted casilla is preserved in
    the comparison result and propagates to CLI / audit surfaces.

    Returns:
        A :class:`RegistryFiledStateComparison` summarising all casilla-level drift.
    """
    if calculation.modelo != observation.modelo:
        raise RegistryValidationError(
            f"cannot compare calculation modelo {calculation.modelo!r} "
            f"with filed observation modelo {observation.modelo!r}",
        )
    target_casillas = tuple(sorted(set(required_casillas)))
    if not target_casillas:
        raise RegistryValidationError("filed-state comparison requires at least one casilla")

    local_values = calculation.values
    filed_values = observation.casilla_values
    entries_by_target = {entry.target: entry for entry in calculation.entries}
    missing_local = tuple(casilla_id for casilla_id in target_casillas if casilla_id not in local_values)
    missing_filed = tuple(casilla_id for casilla_id in target_casillas if casilla_id not in filed_values)
    comparable = tuple(
        casilla_id for casilla_id in target_casillas if casilla_id in local_values and casilla_id in filed_values
    )
    drifts = tuple(
        RegistryFiledStateDrift(
            casilla_id=casilla_id,
            local_value=local_values[casilla_id],
            filed_value=filed_values[casilla_id],
            delta=local_values[casilla_id] - filed_values[casilla_id],
            formula_id=entries_by_target[casilla_id].formula_id if casilla_id in entries_by_target else None,
            legal_refs=entries_by_target[casilla_id].legal_refs if casilla_id in entries_by_target else (),
            source_refs=entries_by_target[casilla_id].source_refs if casilla_id in entries_by_target else (),
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
        compared_casillas=comparable,
        missing_local_casillas=missing_local,
        missing_filed_casillas=missing_filed,
        drifts=drifts,
    )
