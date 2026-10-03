"""Shared exact-token validation for registry-projected IVA vocabularies."""

from __future__ import annotations

from typing import TypeVar

from ...deadlines.models import IVARegime, M303RegimeComposition
from ...iva.schema import IvaArt69DosService, IvaCashAccountingTreatment, IvaExemptionArticle
from .errors import RegistryValidationError

TokenT = TypeVar(
    "TokenT",
    IVARegime,
    M303RegimeComposition,
    IvaCashAccountingTreatment,
    IvaExemptionArticle,
    IvaArt69DosService,
)


def _require_token[
    TokenT: (
        IVARegime,
        M303RegimeComposition,
        IvaCashAccountingTreatment,
        IvaExemptionArticle,
        IvaArt69DosService,
    ),
](
    value: object,
    token_type: type[TokenT],
    members: frozenset[TokenT],
    label: str,
) -> TokenT:
    if isinstance(value, token_type):
        token = value
    elif isinstance(value, str):
        token = token_type(value.strip())
    else:
        raise RegistryValidationError(f"{label} must be a string token")
    if not str(token) or token not in members:
        raise RegistryValidationError(f"{label} {str(token)!r} is not declared by the facts registry")
    return token
