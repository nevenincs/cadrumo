"""Per-clave reconciliation breakdown for annual withholding summaries."""

from __future__ import annotations

from collections.abc import Iterable
from decimal import Decimal

from pydantic import BaseModel, Field, NonNegativeInt

from ....core.aggregation import RetencionClave
from ....core.models import STRICT_FROZEN_CONFIG
from .withholding_bindings import WithholdingObservation, distinct_percepcion_keys, percibido_total, retencion_total

__all__ = ["WithholdingClaveBreakdown", "aggregate_withholding_by_clave"]


class WithholdingClaveBreakdown(BaseModel):
    """One per-clave row of an annual withholding summary's reconciliation breakdown.

    Groups the per-perceptor-clave rows an annual summary's calculation reads
    (the type-2 perceptor records of the AEAT Diseño de Registros, as for
    Modelos 190 and 193) by their ``clave`` and carries that clave's
    distinct percepción count and percibido / retención magnitudes. The figures
    reuse the scalar withholding-fact arithmetic
    (:func:`~cadrumo.domain.calculations.registry.withholding_bindings.resolve_withholding_binding_values`): ``percepcion_count`` is the
    distinct ``(perceptor, clave, subclave)`` count, ``percibido_total`` is
    ``percibido_dinerario + percibido_especie``, and ``retencion_total`` is
    ``retencion_practicada + ingreso_a_cuenta``. It is a projection of the same
    rows the percepciones resolver materialises for that calculation, so the
    operator can reconcile the annual totals clave by clave against the periodic
    filings and captured allocations they were composed from.
    """

    model_config = STRICT_FROZEN_CONFIG

    clave: RetencionClave
    percepcion_count: NonNegativeInt
    percibido_total: Decimal = Field(ge=Decimal("0"))
    retencion_total: Decimal = Field(ge=Decimal("0"))


def aggregate_withholding_by_clave(
    observations: Iterable[WithholdingObservation],
) -> tuple[WithholdingClaveBreakdown, ...]:
    """Aggregate by clave using the same totals as the binding resolver."""
    by_clave: dict[RetencionClave, list[WithholdingObservation]] = {}
    for observation in observations:
        by_clave.setdefault(observation.clave, []).append(observation)
    return tuple(
        WithholdingClaveBreakdown(
            clave=clave,
            percepcion_count=len(distinct_percepcion_keys(group)),
            percibido_total=percibido_total(group),
            retencion_total=retencion_total(group),
        )
        for clave, group in sorted(by_clave.items())
    )
