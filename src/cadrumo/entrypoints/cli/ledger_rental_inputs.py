"""The rental-link options of the ledger doors, resolved before a patch is built.

``--arrendamiento`` and ``--inmueble`` name a stored lease or property by its
row key; ``--gasto-inmobiliario`` names the kind of property expense. The kinds
are the registry's: the option accepts what the pinned authority declares and
says which tokens it does when a value is not one of them. Blank text clears
the link, so the three are returned with their clears kept.
"""

from __future__ import annotations

from collections.abc import Mapping

import typer

from ...core.gasto_capital_inmobiliario import GastoCapitalInmobiliario
from ...core.i18n.render import tr
from ...domain.calculations.registry.errors import RegistryValidationError
from ...domain.calculations.registry.gasto_capital_inmobiliario import resolve_gasto_capital_inmobiliario_catalogue
from .common import bad


def _concept(ctx: typer.Context, value: str) -> GastoCapitalInmobiliario | None:
    from .state_projection_support import authority_operation

    stated = value.strip()
    if not stated:
        return None
    catalogue = resolve_gasto_capital_inmobiliario_catalogue(authority=authority_operation(ctx))
    try:
        return catalogue.require(stated)
    except RegistryValidationError:
        accepted = ", ".join(sorted(str(token) for token in catalogue.all_tokens))
        raise bad(tr("cli.ledger.errors.rental_concept_unknown", value=stated, accepted=accepted)) from None


def rental_link_patch_values(
    ctx: typer.Context,
    *,
    arrendamiento: str | None,
    inmueble: str | None,
    gasto_inmobiliario: str | None,
) -> Mapping[str, object]:
    """Return the rental-link values the operator stated, a blank one as an explicit clear."""
    values: dict[str, object] = {}
    if arrendamiento is not None:
        values["arrendamiento_ref"] = arrendamiento
    if inmueble is not None:
        values["inmueble_ref"] = inmueble
    if gasto_inmobiliario is not None:
        values["gasto_capital_inmobiliario"] = _concept(ctx, gasto_inmobiliario)
    return values


__all__ = ["rental_link_patch_values"]
