"""The closed vocabularies of a contribution to a social-welfare system (previsión social).

A plan manager, mutualidad or insurer reports each contribution on Modelo 345
under an official clave and, for most claves, a subclave, and issues the
taxpayer a certificate stating the same. The clave and subclave say who paid and
into which instrument, which is what the art. 52 LIRPF limits turn on. These
tokens are persisted inside encrypted records and named by registry
declarations, so a value outside them is refused rather than carried as text.

The claves and subclaves are the union of those the bundled Modelo 345 record
designs define. Which Modelo 100 casilla a pair reaches, if any, is registry data
per edition, never decided here.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from types import MappingProxyType
from typing import Final

__all__ = [
    "PrevisionSocialBeneficiario",
    "PrevisionSocialClave",
    "PrevisionSocialPlacementRefusal",
    "PrevisionSocialSubclave",
    "is_defined_clave_pair",
]


class PrevisionSocialClave(StrEnum):
    """The Modelo 345 clave (registro de tipo 2, position 82): who paid, into which instrument."""

    CLAVE_A = "A"
    """Aportaciones de los partícipes a planes de pensiones."""
    CLAVE_B = "B"
    """Contribuciones de los promotores, imputadas o no a los partícipes."""
    CLAVE_C = "C"
    """Contribuciones deducibles del promotor de planes de pensiones del sistema de empleo."""
    CLAVE_D = "D"
    """Contribuciones y dotaciones de empresas acogidas a sistemas alternativos."""
    CLAVE_E = "E"
    """Cantidades abonadas a mutualidades por profesionales o empresarios individuales."""
    CLAVE_F = "F"
    """Cantidades abonadas a mutualidades por trabajadores por cuenta ajena o socios trabajadores."""
    CLAVE_G = "G"
    """Cantidades abonadas a mutualidades por el promotor."""
    CLAVE_H = "H"
    """Primas satisfechas a planes de previsión asegurados."""
    CLAVE_I = "I"
    """Primas satisfechas a planes individuales de ahorro sistemático."""
    CLAVE_J = "J"
    """Primas satisfechas a planes de previsión social empresarial."""
    CLAVE_K = "K"
    """Primas satisfechas a seguros privados de dependencia severa o gran dependencia."""
    CLAVE_L = "L"
    """Primas satisfechas a seguros colectivos de dependencia."""
    CLAVE_M = "M"
    """Aportaciones a productos paneuropeos de pensiones individuales (PEPP)."""


class PrevisionSocialSubclave(StrEnum):
    """The Modelo 345 subclave (positions 83-84); its meaning depends on the clave."""

    SUBCLAVE_01 = "01"
    SUBCLAVE_02 = "02"
    SUBCLAVE_03 = "03"
    SUBCLAVE_04 = "04"


_SUBCLAVES_BY_CLAVE: Final[Mapping[PrevisionSocialClave, frozenset[PrevisionSocialSubclave]]] = MappingProxyType(
    {
        PrevisionSocialClave.CLAVE_A: frozenset(
            {
                PrevisionSocialSubclave.SUBCLAVE_01,
                PrevisionSocialSubclave.SUBCLAVE_02,
                PrevisionSocialSubclave.SUBCLAVE_03,
            }
        ),
        PrevisionSocialClave.CLAVE_B: frozenset(),
        PrevisionSocialClave.CLAVE_C: frozenset(PrevisionSocialSubclave),
        PrevisionSocialClave.CLAVE_D: frozenset(
            {
                PrevisionSocialSubclave.SUBCLAVE_01,
                PrevisionSocialSubclave.SUBCLAVE_02,
                PrevisionSocialSubclave.SUBCLAVE_03,
            }
        ),
        PrevisionSocialClave.CLAVE_E: frozenset(
            {PrevisionSocialSubclave.SUBCLAVE_01, PrevisionSocialSubclave.SUBCLAVE_02}
        ),
        PrevisionSocialClave.CLAVE_F: frozenset(
            {PrevisionSocialSubclave.SUBCLAVE_01, PrevisionSocialSubclave.SUBCLAVE_02}
        ),
        PrevisionSocialClave.CLAVE_G: frozenset(
            {PrevisionSocialSubclave.SUBCLAVE_01, PrevisionSocialSubclave.SUBCLAVE_02}
        ),
        PrevisionSocialClave.CLAVE_H: frozenset(),
        PrevisionSocialClave.CLAVE_I: frozenset(
            {PrevisionSocialSubclave.SUBCLAVE_01, PrevisionSocialSubclave.SUBCLAVE_02}
        ),
        PrevisionSocialClave.CLAVE_J: frozenset(PrevisionSocialSubclave),
        PrevisionSocialClave.CLAVE_K: frozenset(),
        PrevisionSocialClave.CLAVE_L: frozenset(
            {
                PrevisionSocialSubclave.SUBCLAVE_01,
                PrevisionSocialSubclave.SUBCLAVE_02,
                PrevisionSocialSubclave.SUBCLAVE_03,
            }
        ),
        PrevisionSocialClave.CLAVE_M: frozenset(),
    }
)
"""The subclaves each clave takes in the Modelo 345 designs; an empty set means the clave takes none."""


def is_defined_clave_pair(clave: PrevisionSocialClave, subclave: PrevisionSocialSubclave | None) -> bool:
    """Return whether the Modelo 345 designs define ``subclave`` under ``clave``, or no subclave for it."""
    defined = _SUBCLAVES_BY_CLAVE[clave]
    if subclave is None:
        return not defined
    return subclave in defined


class PrevisionSocialBeneficiario(StrEnum):
    """Whose social-welfare system a contribution goes to, as the taxpayer's return sees it."""

    TAXPAYER = "taxpayer"
    """The taxpayer's own system: the reduction of LIRPF arts. 51 and 52."""
    SPOUSE = "spouse"
    """The spouse's system (LIRPF art. 51.7); not placed in this version."""
    DISABLED_PERSON = "disabled_person"
    """A person with a disability's system (LIRPF art. 53); not placed in this version."""


class PrevisionSocialPlacementRefusal(StrEnum):
    """Why a contribution reaches no Modelo 100 casilla, so the operator enters the box instead."""

    UNPLACED_CLAVE = "unplaced_clave"
    """No official text places this clave and subclave in a casilla of the reduction."""
    INDIRECT_MATCH = "indirect_match"
    """A casilla fits only by analogy; no official text names this instrument for it."""
    DESIGN_NOT_BUNDLED = "design_not_bundled"
    """Cadrumo holds no Modelo 345 design for the ejercicio, so no clave is placed for it."""
    SAME_PLAN_SPLIT_UNSTATED = "same_plan_split_unstated"
    """The casilla depends on whether the employer contributed to the same plan, and the record does not say."""
    BENEFICIARY_OUT_OF_SCOPE = "beneficiary_out_of_scope"
    """The contribution is to a spouse's or a disabled person's system, which this version does not place."""
