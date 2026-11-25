"""AEAT Renta profile-code types and stable export projections.

The closed profile vocabularies keep their semantic members here. The code each
member carries on Modelo 100 and in a stored profile answer is a form datum that
the registry declares in the ``modelo-100-profile-form-codes`` fact, together with
the Modelo 100 numbering of the autonomous communities. Reading a code needs a
generation-pinned governed-fact scope. The cross-cutting fiscal-residency vocabulary
is an opaque token projected from the governed facts registry, so CLI and wizard
surfaces obtain its choices through the registry resolver.

:class:`SituacionFamiliar` and :class:`SituacionFamiliarM145` keep the Art. 82 LIRPF
joint-taxation axis separate from Modelo 145 withholding categories.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Final, override

from ...core.registry_token import StrictRegistryToken
from ..calculations.registry.form_codes import RegistryCodedEnum, resolve_form_codes
from ..calculations.registry.governed_fact_scope import GovernedFactSource
from .ccaa import CCAA

_PROFILE_FORM_CODES_FACT: Final = "modelo-100-profile-form-codes"


class RentaSexCode(RegistryCodedEnum):
    """Modelo 100 ``tipo_Sexo`` vocabulary."""

    HOMBRE = "hombre"
    MUJER = "mujer"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _PROFILE_FORM_CODES_FACT, "sex"


class RentaMaritalStatus(RegistryCodedEnum):
    """Renta taxpayer marital / registered-partnership profile vocabulary."""

    SOLTERO = "soltero"
    CASADO = "casado"
    VIUDO = "viudo"
    SEPARADO_DIVORCIADO = "separado_divorciado"
    PAREJA_HECHO = "pareja_hecho"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _PROFILE_FORM_CODES_FACT, "marital_status"


class RentaDeclaracionType(RegistryCodedEnum):
    """Modelo 100 ``TIPOTRIBUTACION`` vocabulary."""

    INDIVIDUAL = "individual"
    JOINT = "joint"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _PROFILE_FORM_CODES_FACT, "declaration_type"


class RentaDisabilityGrade(RegistryCodedEnum):
    """Modelo 100 ``tipo_GradoDiscapacidad`` vocabulary."""

    GE_33_LT_65 = "ge_33_lt_65"
    GE_65 = "ge_65"
    JUDICIAL_INCAPACITY = "judicial_incapacity"
    ASSISTANCE_OR_REDUCED_MOBILITY = "assistance_or_reduced_mobility"

    @classmethod
    @override
    def _form_code_source(cls) -> tuple[str, str]:
        return _PROFILE_FORM_CODES_FACT, "disability_grade"


def modelo100_ecivil_export_code(value: object) -> str:
    """Return a validated official Modelo 100 ECIVIL export code.

    The registered-partnership marker is profile-only. The official ECIVIL field
    takes the members the fact lists for export, so a caller supplies the taxpayer's
    true official civil status instead of exporting that marker.
    """
    code = str(value).strip()
    declared = resolve_form_codes(_PROFILE_FORM_CODES_FACT)
    accepted = sorted(
        declared.code(f"marital_status.{member}") for member in declared.ordered_codes("marital_status_export.members")
    )
    if code in accepted:
        return code
    if code == declared.code(f"marital_status.{RentaMaritalStatus.PAREJA_HECHO.value}"):
        raise ValueError(
            f"profile-only pareja de hecho marital status code {code!r} is not a valid Modelo 100 ECIVIL export code; "
            f"supply the official Estado Civil code, one of {', '.join(accepted)}"
        )
    raise ValueError(f"Modelo 100 ECIVIL export code must be one of {', '.join(accepted)}; got {code!r}")


def renta_modelo100_ccaa_codigos(*, authority: GovernedFactSource | None = None) -> Mapping[CCAA, str]:
    """Return the official Modelo 100 CCAA códigos the registry declares.

    The numbering belongs to Modelo 100 alone. Other modelos and the INE number the
    same communities differently, so it is never a general CCAA numbering.
    """
    from ..calculations.registry.ccaa_catalogue import resolve_ccaa_catalogue

    catalogue = resolve_ccaa_catalogue(authority=authority)
    declared = resolve_form_codes(_PROFILE_FORM_CODES_FACT, authority=authority).under("ccaa")
    return MappingProxyType({catalogue.require(token): codigo for token, codigo in declared.items()})


def modelo100_ccaa_codigo(value: CCAA | str) -> str:
    """Return the official Modelo 100 código for an autonomous community.

    Args:
        value: The community to look up, as a :class:`CCAA` member or its
            canonical lowercase token (``"madrid"``). Any other string is a
            community this export cannot name, and is refused rather than
            resolved.

    Returns:
        The código AEAT's Modelo 100 schema accepts for ``value``.

    Raises:
        ValueError: when ``value`` names no community that carries a Modelo 100
            código. Refusing is deliberate: a community exported under the wrong
            código produces a declaration that validates against the AEAT schema
            while naming the wrong comunidad, so an absent código must fail the
            export rather than fall back to a default.
    """
    try:
        community: CCAA | None = CCAA(value)
    except ValueError:
        community = None
    if community is not None and not isinstance(value, CCAA) and str(community) != value:
        community = None
    codigos = renta_modelo100_ccaa_codigos()
    codigo = codigos.get(community) if community is not None else None
    if codigo is None:
        valid = ", ".join(sorted(str(member) for member in codigos))
        raise ValueError(f"no Modelo 100 CCAA código is assigned to {value!r}; communities carrying a código: {valid}")
    return codigo


class FiscalResidency(StrictRegistryToken):
    """Opaque fiscal-residency token projected from the facts registry.

    The registry owns residency membership and its downstream regime meaning.
    This type retains only the stable wire-token shape; callers obtain values
    through the typed residency catalogue resolver.
    """

    __slots__ = ()

    _projection_source = "registry"


class SituacionFamiliar(StrictRegistryToken):
    """Opaque Art. 82 family-situation token projected from the facts registry.

    The registry owns the five-token vocabulary and the joint-taxation
    eligibility mapping.  This type retains only the stable wire-token shape;
    callers obtain a value through the typed registry projection.
    """

    __slots__ = ()


class SituacionFamiliarM145(StrictRegistryToken):
    """Opaque Modelo 145 family-situation token projected from the facts registry.

    Fact 0142 owns the three form values, their legal descriptions, and the
    supplementary-reduction eligibility mapping. This type retains only the
    stable wire-token shape; callers obtain values through the typed registry
    projection in ``situacion_familiar_m145_catalogue``.
    """

    __slots__ = ()


__all__ = [
    "FiscalResidency",
    "RentaDeclaracionType",
    "RentaDisabilityGrade",
    "RentaMaritalStatus",
    "RentaSexCode",
    "SituacionFamiliar",
    "SituacionFamiliarM145",
    "modelo100_ccaa_codigo",
    "modelo100_ecivil_export_code",
    "renta_modelo100_ccaa_codigos",
]
