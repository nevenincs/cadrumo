"""Fail-closed boundary for financial transaction casilla aggregation.

The previous implementation projected spending categories directly to
modelo casillas in application code. That duplicated legal calculation
metadata outside the central calculation registry and is deliberately
disabled while the registry rebuild is in progress.
"""

from __future__ import annotations

from ...domain.modelos import ModeloCode
from ...domain.transactions import TransactionCatalogue
from ._errors import AggregationUnsupportedModeloError, t
from ._models import CasillaAggregation, Period


def aggregate_catalogue(
    catalogue: TransactionCatalogue,
    *,
    modelo: str | ModeloCode,
    period: str | Period,
) -> CasillaAggregation:
    """Refuse financial-to-casilla aggregation until registry coverage exists.

    The function keeps the public boundary typed and validates the
    incoming modelo and period tokens, but it does not derive any
    casilla value. Legal calculation and casilla projection must come
    from the central registry, not from category-profile metadata or
    application-layer shortcuts.

    Raises:
        AggregationUnsupportedModeloError: Always, with the requested
            modelo and period in the error context.
    """

    del catalogue
    modelo_code = _parse_modelo(modelo)
    resolved_period = period if isinstance(period, Period) else Period.model_validate(period)
    raise AggregationUnsupportedModeloError(
        translated_message=t(
            "La agregacion financiera a casillas esta deshabilitada hasta que exista cobertura en el registro central.",
            "Financial aggregation into casillas is disabled until central registry coverage exists.",
            "A penzugyi casilla-osszesites ki van kapcsolva, amig nincs kozponti registry-lefedettseg.",
        ),
        context={"modelo": modelo_code.value, "period": resolved_period.raw},
    )


def _parse_modelo(modelo: str | ModeloCode) -> ModeloCode:
    if isinstance(modelo, ModeloCode):
        return modelo
    text = modelo.strip().upper()
    for candidate in ModeloCode:
        if text in {candidate.value, candidate.name}:
            return candidate
    raise AggregationUnsupportedModeloError(
        translated_message=t(
            "Modelo desconocido para agregacion financiera.",
            "Unknown modelo for financial aggregation.",
            "Ismeretlen nyomtatvany penzugyi osszesiteshez.",
        ),
        context={"modelo": modelo},
    )


__all__ = ["aggregate_catalogue"]
