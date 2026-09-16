"""Opaque prorrata-register axes projected from facts authority.

The register regime, special-prorrata transition, art. 105 provenance, and
differentiated-sector letter vocabularies are governing-body facts. This core
module retains only their structural token contracts. Registry membership and
legal meaning, including whether a regime apportions a deduction, are projected
by ``domain.calculations.registry.prorrata_register_catalogue``.
"""

from __future__ import annotations

from enum import StrEnum

from .registry_token import TextProjectedRegistryToken


class ProrrataRegisterRegime(TextProjectedRegistryToken):
    """Opaque registry-projected regime token for one register ejercicio."""

    __slots__ = ()

    _empty_value_message = "prorrata register regime token must be a non-empty string"
    _boundary_subject = "prorrata register regime"


class ProrrataEspecialTransitionKind(TextProjectedRegistryToken):
    """Opaque registry-projected special-prorrata transition token."""

    __slots__ = ()

    _empty_value_message = "prorrata transition token must be a non-empty string"
    _boundary_subject = "prorrata transition"


class ProrrataActivityRowType(StrEnum):
    """Official Modelo 303 token for one per-activity prorrata row."""

    GENERAL = "G"
    ESPECIAL = "E"


class ProrrataProvisionalProvenance(TextProjectedRegistryToken):
    """Opaque registry-projected art. 105 provisional-provenance token."""

    __slots__ = ()

    _empty_value_message = "prorrata provisional provenance token must be a non-empty string"
    _boundary_subject = "prorrata provenance"


class SectorDiferenciadoLetra(TextProjectedRegistryToken):
    """Opaque registry-projected LIVA art. 9.1.c sector-letter token."""

    __slots__ = ()

    _empty_value_message = "differentiated-sector letter must be a non-empty string"
    _boundary_subject = "sector letter"


__all__ = [
    "ProrrataActivityRowType",
    "ProrrataEspecialTransitionKind",
    "ProrrataProvisionalProvenance",
    "ProrrataRegisterRegime",
    "SectorDiferenciadoLetra",
]
