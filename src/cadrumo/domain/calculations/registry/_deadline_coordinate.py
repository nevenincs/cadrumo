"""Canonical semantic identity for registry deadline windows."""

from __future__ import annotations

from typing import NamedTuple

from ....core import Period, ResultDisposition, registry_period_kind
from ._schema import DeadlineWindowDefinition


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
    tipo_renta_scope: tuple[str, ...] | None


def deadline_semantic_coordinate(
    modelo: str,
    period: Period,
    resultado_scope: ResultDisposition | None,
    tipo_renta_scope: tuple[str, ...] | None,
) -> DeadlineSemanticCoordinate:
    """Project one deadline identity through the canonical typed axes.

    ``Period`` supplies the filing year and registry token.  Calling the shared
    cadence classifier here keeps the projection on the registry period
    vocabulary without copying its parser or token map.  Tipo-renta scope is a
    set-like qualifier, so source ordering does not change identity.
    """
    registry_period_kind(period.registry_token)
    canonical_tipo_scope = tuple(sorted(tipo_renta_scope)) if tipo_renta_scope is not None else None
    return DeadlineSemanticCoordinate(
        modelo=modelo,
        filing_year=period.filing_year,
        period_token=period.registry_token,
        resultado_scope=resultado_scope,
        tipo_renta_scope=canonical_tipo_scope,
    )


def deadline_window_semantic_coordinate(
    modelo: str,
    window: DeadlineWindowDefinition,
) -> DeadlineSemanticCoordinate:
    """Project a validated window without admitting additional qualifiers."""
    return deadline_semantic_coordinate(
        modelo,
        window.period,
        window.resultado_scope,
        window.tipo_renta_scope,
    )


__all__ = [
    "DeadlineSemanticCoordinate",
    "deadline_semantic_coordinate",
    "deadline_window_semantic_coordinate",
]
