"""Spain's provinces and autonomous cities by their INE code, as the registry publishes them.

A counterparty's provincia is the province of its domicilio fiscal, which Modelo
347 declares by these codes and a person states by name. Both the code set and
the names come from one fact, so no surface keeps its own list.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from .form_codes import resolve_form_codes
from .governed_fact_scope import GovernedFactSource

_FACT: Final = "ine-provincia-catalogue"


def ine_provincia_names(*, authority: GovernedFactSource | None = None) -> Mapping[str, str]:
    """Return each INE provincia code with its official name, in code order."""
    codes = resolve_form_codes(_FACT, authority=authority)
    names = codes.under("name")
    return {code: names[code] for code in codes.ordered_codes("codes")}


def is_ine_provincia_code(value: str, *, authority: GovernedFactSource | None = None) -> bool:
    """Return whether ``value`` is a provincia code the catalogue declares."""
    return value in ine_provincia_names(authority=authority)
