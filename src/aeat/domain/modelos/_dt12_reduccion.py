"""DT 12ª LIRPF plan-de-pensiones capital-rescate reducción.

The 40% reducción on the part of a plan-de-pensiones capital rescate attributable
to contributions made on or before 31-12-2006 (LIRPF Disposición Transitoria 12ª).
"""

from __future__ import annotations

from decimal import Decimal

from ...core.external_constants import DT12_RESCATE_REDUCCION_RATE
from ...core.money import round_to_cents
from ._errors import PensionReduccionError


def compute_dt12_reduccion_plan_pensiones(
    *,
    gross_rescate: Decimal,
    aportaciones_pre_2007: Decimal,
    aportaciones_totales: Decimal,
) -> Decimal:
    """Compute the DT 12ª LIRPF 40% reducción for a plan-de-pensiones capital rescate.

    Formula (LIRPF DT 12ª): ``pre_2007 / totales * gross_rescate * 40%``. The result
    is rounded to 2 decimal places (money-2 per the registry convention).

    Raises:
        PensionReduccionError: When ``aportaciones_totales`` is zero or negative
            (division-by-zero guard), or when any input is negative.
    """
    if aportaciones_totales <= Decimal(0):
        raise PensionReduccionError(
            f"aportaciones_totales must be positive; got {aportaciones_totales}",
            context={"field": "aportaciones_totales", "value": str(aportaciones_totales)},
        )
    if gross_rescate < Decimal(0):
        raise PensionReduccionError(
            f"gross_rescate must be non-negative; got {gross_rescate}",
            context={"field": "gross_rescate", "value": str(gross_rescate)},
        )
    if aportaciones_pre_2007 < Decimal(0):
        raise PensionReduccionError(
            f"aportaciones_pre_2007 must be non-negative; got {aportaciones_pre_2007}",
            context={"field": "aportaciones_pre_2007", "value": str(aportaciones_pre_2007)},
        )

    reduccion = (aportaciones_pre_2007 / aportaciones_totales) * gross_rescate * DT12_RESCATE_REDUCCION_RATE
    return round_to_cents(reduccion)
