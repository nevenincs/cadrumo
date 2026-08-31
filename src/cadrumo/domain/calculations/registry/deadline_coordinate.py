"""Canonical semantic identity for registry deadline windows."""

from __future__ import annotations

from typing import NamedTuple

from ....core.irnr import M210_TIPO_RENTA_CODE_PROJECTION
from ....core.modelo import Modelo
from ....core.period import Period, registry_period_kind
from ....core.result_disposition import ResultDisposition
from .schema import DeadlineWindowDefinition


class DeadlineSemanticCoordinate(NamedTuple):
    """Law-fact identity shared by deadline validation and projection.

    Dates, authored ids, revision ids, and declared cadence are intentionally
    absent.  They describe or own a deadline fact; they cannot make two copies
    of the same fact semantically distinct.
    """

    modelo: str
    filing_year: int
    period_token: str
    resultado_scope: ResultDisposition | None
    tipo_renta_code: str | None


def deadline_semantic_coordinate(
    modelo: str,
    period: Period,
    resultado_scope: ResultDisposition | None,
    tipo_renta_code: str | None,
) -> DeadlineSemanticCoordinate:
    """Project one deadline identity through the canonical typed axes.

    ``Period`` supplies the filing year and registry token. Calling the shared
    cadence classifier here keeps the projection on the registry period
    vocabulary without copying its parser or token map. Qualifier values are
    atomic: authored scopes are expanded by
    :func:`deadline_window_semantic_coordinates` before uniqueness checks.
    """
    registry_period_kind(period.registry_token)
    return DeadlineSemanticCoordinate(
        modelo=modelo,
        filing_year=period.filing_year,
        period_token=period.registry_token,
        resultado_scope=resultado_scope,
        tipo_renta_code=tipo_renta_code,
    )


def deadline_window_semantic_coordinates(
    modelo: str,
    window: DeadlineWindowDefinition,
) -> tuple[DeadlineSemanticCoordinate, ...]:
    """Expand one window into every atomic request identity it can match.

    ``None`` is a wildcard in deadline resolution. Expanding it here makes an
    unqualified window collide during registry validation with every qualified
    window it would shadow at runtime. The expansion reuses the canonical core
    enum and official M210 code projection; it owns no vocabulary of its own.
    """
    resultados: tuple[ResultDisposition | None, ...] = (
        (None, *tuple(ResultDisposition)) if window.resultado_scope is None else (window.resultado_scope,)
    )

    tipos: tuple[str | None, ...]
    if window.tipo_renta_scope is not None:
        tipos = tuple(sorted(window.tipo_renta_scope))
    elif modelo == Modelo.M210:
        tipos = (None, *tuple(sorted(M210_TIPO_RENTA_CODE_PROJECTION)))
    else:
        tipos = (None,)

    return tuple(
        deadline_semantic_coordinate(modelo, window.period, resultado, tipo)
        for resultado in resultados
        for tipo in tipos
    )


__all__ = [
    "DeadlineSemanticCoordinate",
    "deadline_semantic_coordinate",
    "deadline_window_semantic_coordinates",
]
