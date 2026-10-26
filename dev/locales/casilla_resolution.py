"""Resolve the serving locale through the canonical casilla localization rule."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .modelo_casilla_catalogue import ModeloCasillaCatalogue
from cadrumo.domain.calculations.registry.modelo_localization import (
    modelo_localization_source,
)

from .casilla_catalogue_models import (
    Values,
)


def _served_locale(
    catalogue: ModeloCasillaCatalogue,
    index: int,
    field_name: str,
    locale: str,
    values: Values | None = None,
) -> str | None:
    source = modelo_localization_source(
        catalogue.occurrences[index].chain(field_name),
        locale=locale,
        lookup=catalogue.lookup_for(catalogue.values if values is None else values),
    )
    return None if source is None else source[1]
