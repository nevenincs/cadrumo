"""Typed governed-fact resolution shared by Modelo 210 treaty consumers."""

from __future__ import annotations

from datetime import date
from typing import TypeAlias

from ...core.irnr import TipoRentaIrnr
from ...domain.calculations.registry.convenio import (
    ResolvedConvenioOverride,
    resolve_convenio_override,
)

ResolvedM210ConvenioOverride: TypeAlias = ResolvedConvenioOverride


def resolve_m210_convenio_override(
    *,
    country_code: str,
    tipo_renta: TipoRentaIrnr,
    devengo_date: date,
) -> ResolvedM210ConvenioOverride | None:
    """Resolve the exact dated treaty fact for Modelo 210."""
    return resolve_convenio_override(
        country_code=country_code,
        tipo_renta=tipo_renta,
        devengo_date=devengo_date,
    )


__all__ = ["ResolvedM210ConvenioOverride", "resolve_m210_convenio_override"]
