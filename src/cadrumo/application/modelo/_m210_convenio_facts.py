"""Typed governed-fact resolution shared by Modelo 210 treaty consumers."""

from __future__ import annotations

from datetime import date

from ...core.irnr import TipoRentaIrnr
from ...domain.calculations.registry.authority import bundled_indexed_authority
from ...domain.calculations.registry.convenio import (
    ResolvedConvenioOverride,
    resolve_convenio_override,
)

type ResolvedM210ConvenioOverride = ResolvedConvenioOverride


def resolve_m210_convenio_override(
    *,
    country_code: str,
    tipo_renta: TipoRentaIrnr,
    devengo_date: date,
) -> ResolvedM210ConvenioOverride | None:
    """Resolve the exact dated treaty fact for Modelo 210."""
    with bundled_indexed_authority().operation() as operation:
        return resolve_convenio_override(
            country_code=country_code,
            tipo_renta=tipo_renta,
            devengo_date=devengo_date,
            operation=operation,
        )


__all__ = ["ResolvedM210ConvenioOverride", "resolve_m210_convenio_override"]
