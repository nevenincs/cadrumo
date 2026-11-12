"""The savings-link options of the ledger doors, resolved before a patch is built.

``--posicion`` names a stored savings position by its row key;
``--concepto-capital-mobiliario`` names what the row is within that position.
The concepts are the registry's: the option accepts what the pinned authority
declares and says which tokens it does when a value is not one of them. Blank
text clears the link, so the two are returned with their clears kept.
"""

from __future__ import annotations

from collections.abc import Mapping

import typer

from ...core.concepto_capital_mobiliario import ConceptoCapitalMobiliario
from ...core.i18n.render import tr
from ...domain.calculations.registry.capital_mobiliario_facts import (
    require_concepto_capital_mobiliario,
    resolve_capital_mobiliario_concept_vocabulary,
)
from ...domain.calculations.registry.errors import RegistryValidationError
from .common import bad


def _concept(ctx: typer.Context, value: str) -> ConceptoCapitalMobiliario | None:
    from .state_projection_support import authority_operation

    stated = value.strip()
    if not stated:
        return None
    authority = authority_operation(ctx)
    try:
        return require_concepto_capital_mobiliario(stated, authority=authority)
    except RegistryValidationError:
        accepted = ", ".join(sorted(resolve_capital_mobiliario_concept_vocabulary(authority=authority).tokens))
        raise bad(tr("errors.transaction.savings_concept_unknown", value=stated, accepted=accepted)) from None


def savings_link_patch_values(
    ctx: typer.Context,
    *,
    posicion: str | None,
    concepto_capital_mobiliario: str | None,
) -> Mapping[str, object]:
    """Return the savings-link values the operator stated, a blank one as an explicit clear."""
    values: dict[str, object] = {}
    if posicion is not None:
        values["posicion_ref"] = posicion
    if concepto_capital_mobiliario is not None:
        values["concepto_capital_mobiliario"] = _concept(ctx, concepto_capital_mobiliario)
    return values


__all__ = ["savings_link_patch_values"]
