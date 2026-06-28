"""Art. 81 LIRPF deducción maternidad computation helpers.

Pure-domain arithmetic; no entrypoint or CLI dependencies.
:func:`compute_deduccion_maternidad_0611` applies the central
:data:`~aeat.core.external_constants.DEDUCCION_MATERNIDAD_MENSUAL_EUR` and
:data:`~aeat.core.external_constants.DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR`
limits used by :class:`RentaFamilyProfile`.
"""

from __future__ import annotations

from ...core.external_constants import (
    DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR,
    DEDUCCION_MATERNIDAD_MENSUAL_EUR,
)


def compute_deduccion_maternidad_0611(meses_por_hijo: list[tuple[str, int]]) -> int:
    """Compute Art. 81 LIRPF deducción maternidad from per-hijo meses pairs.

    Formula: ``sum(min(meses × :data:`DEDUCCION_MATERNIDAD_MENSUAL_EUR`,
    :data:`DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR`))`` for each ``(hijo_id, meses)`` pair.
    Returns an integer euros amount.
    """
    return sum(
        min(meses * DEDUCCION_MATERNIDAD_MENSUAL_EUR, DEDUCCION_MATERNIDAD_ANUAL_CAP_EUR) for _, meses in meses_por_hijo
    )
