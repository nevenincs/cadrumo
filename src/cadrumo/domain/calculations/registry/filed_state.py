"""Filed-state comparison for registry calculation outputs."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from ....core.casilla_id import CasillaId
from ....core.filing_year import FilingYear
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.period import FilingPeriodCode, Period
from .bindings import CasillaObservation, RegistryModeloObservation
from .errors import RegistryValidationError
from .formula_runtime import RegistryCalculationResult
from .ids import FormulaId, LegalRefId, ModeloId, SourceRefId

__all__ = [
    "RegistryFiledStateComparison",
    "RegistryFiledStateDrift",
    "compare_calculation_to_filed_observation",
]


class RegistryFiledStateStatus(StrEnum):
    """Whether a filed-state comparison matched what the registry expected."""

    SATISFIED = "satisfied"
    FAILED = "failed"


RegistryFiledStateStatusValue = Literal[
    RegistryFiledStateStatus.SATISFIED,
    RegistryFiledStateStatus.FAILED,
]
"""The same vocabulary for a strict model field."""


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
    formula_id: FormulaId | None = None
    legal_refs: tuple[LegalRefId, ...] = Field(min_length=1)
    source_refs: tuple[SourceRefId, ...] = Field(min_length=1)


class RegistryFiledStateComparison(BaseModel):
    """Verdict for one local calculation versus one normalized filed observation."""

    model_config = STRICT_FROZEN_CONFIG

    modelo: ModeloId
    revision: str = Field(min_length=1)
    filing_period: Period | None = None
    filing_year: FilingYear
    period: FilingPeriodCode
    status: RegistryFiledStateStatusValue
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
    tolerance: Decimal = Decimal("0"),
) -> RegistryFiledStateComparison:
    """Compare local registry calculation values against filed AEAT casillas.

    Not substitutable with ``casillas_a_recapture_would_change`` in
    ``application/live``: that one compares two captures of the SAME filing and
    deliberately ignores casillas present on only one side, whereas this one
    reports them as missing-in-filed or extra-in-filed. Nor with the
    revision-vs-revision delta in ``application/modelo/projection.py``, which
    compares two of the application's own calculations rather than local
    against AEAT.

    Each :class:`RegistryFiledStateDrift` in the returned comparison
    carries ``formula_id``, ``legal_refs``, and ``source_refs`` from the
    typed :class:`CasillaObservation` envelope, so the regulatory
    grounding for every drifted casilla is preserved in the comparison
    result and propagates to CLI / audit surfaces.

    Args:
        calculation: The local registry calculation result.
        observation: The normalized filed AEAT observation to compare against.
        required_casilla_ids: The casilla ids the comparison must cover.
        tolerance: Maximum absolute delta that does not surface as a drift.
            THE REGISTRY IS THE AUTHORITY FOR THIS VALUE and publishes it per
            revision: resolve it with ``snapshot.verification_policy().tolerance``
            and pass it, matching :func:`~application.modelo.detect_casilla_divergences`'s
            same-named parameter and the same rationale. The default is exact
            equality — matching this function's behaviour before the parameter
            existed — because a caller that passes nothing must get the
            strictest reading rather than a silently more permissive one it
            never chose.

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
        if abs(local_values[casilla_id] - filed_values[casilla_id]) > tolerance
    )
    status: RegistryFiledStateStatusValue = (
        RegistryFiledStateStatus.SATISFIED
        if not missing_local and not missing_filed and not drifts
        else RegistryFiledStateStatus.FAILED
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
