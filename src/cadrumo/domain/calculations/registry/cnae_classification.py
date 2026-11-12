"""The classification of economic activities a C.N.A.E. is consigned in, as the registry publishes it.

A C.N.A.E. code means something only within one classification: Nota 12 of the
2025 Modelo 202 design consigns the ejercicio 2025 in CNAE-2009 and 2026 onwards
in CNAE-2025. Both the classifications and the one each ejercicio requires come
from governed facts, so no surface keeps its own list or year. No
correspondence between classifications is declared, so a code is never
converted from one into another.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Final

from .errors import RegistryValidationError
from .form_codes import resolve_form_codes
from .governed_fact_scope import GovernedFactSource

_CATALOGUE_FACT: Final = "cnae-classification-catalogue"
_BY_EJERCICIO_FACT: Final = "cnae-classification-by-ejercicio"


def cnae_classification_names(*, authority: GovernedFactSource | None = None) -> Mapping[str, str]:
    """Return each classification identifier with the name the design prints for it, in authored order."""
    codes = resolve_form_codes(_CATALOGUE_FACT, authority=authority)
    names = codes.under("name")
    return {code: names[code] for code in codes.ordered_codes("codes")}


def required_cnae_classification(*, effective_date: date, authority: GovernedFactSource | None = None) -> str:
    """Return the classification identifier the ejercicio containing ``effective_date`` consigns its C.N.A.E. in.

    Raises:
        RegistryValidationError: The required classification is not one the
            catalogue declares.
    """
    required = resolve_form_codes(_BY_EJERCICIO_FACT, effective_date=effective_date, authority=authority).code(
        "required"
    )
    if required not in cnae_classification_names(authority=authority):
        raise RegistryValidationError(f"CNAE classification {required!r} is not in {_CATALOGUE_FACT!r}")
    return required


__all__ = ["cnae_classification_names", "required_cnae_classification"]
