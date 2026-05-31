"""AEAT-aligned spending-category taxonomy.

Defines the closed enum :class:`SpendingCategory` of deductible
autónomo expense classes, the coarse :class:`SpendingCategoryFamily`
groups, and the static :data:`CATEGORY_FAMILY_MEMBERS` membership
table. The taxonomy is the stable identifier surface every other
package binds to; renaming a member is a breaking change.
"""

from __future__ import annotations

from enum import StrEnum


class SpendingCategory(StrEnum):
    """Stable identifiers for deductible autónomo spending categories.

    Members map one-to-one to the deductible expense classes
    recognised by AEAT. Each value is the stable kebab-style
    Spanish identifier used in the on-disk corpus and in CLI flags.
    """

    CUOTAS_COLEGIALES = "cuotas_colegiales"
    CUOTAS_AUTONOMOS_SS = "cuotas_autonomos_ss"
    MUTUALIDAD_ALTERNATIVA = "mutualidad_alternativa"
    ARRENDAMIENTO_LOCAL = "arrendamiento_local"
    ARRENDAMIENTO_VIVIENDA_AFECTO = "arrendamiento_vivienda_afecto"
    IBI_LOCAL_AFECTO = "ibi_local_afecto"
    SUMINISTROS_HOME_OFFICE_LUZ = "suministros_home_office_luz"
    SUMINISTROS_HOME_OFFICE_AGUA = "suministros_home_office_agua"
    SUMINISTROS_HOME_OFFICE_GAS = "suministros_home_office_gas"
    SUMINISTROS_HOME_OFFICE_INTERNET = "suministros_home_office_internet"
    AMORTIZACION_VIVIENDA_AFECTO = "amortizacion_vivienda_afecto"
    IBI_VIVIENDA_AFECTO = "ibi_vivienda_afecto"
    COMUNIDAD_VIVIENDA_AFECTO = "comunidad_vivienda_afecto"
    TELEFONIA_MOVIL = "telefonia_movil"
    TELEFONIA_FIJA = "telefonia_fija"
    MATERIAL_OFICINA = "material_oficina"
    SOFTWARE_SUSCRIPCION = "software_suscripcion"
    HARDWARE_AMORTIZABLE = "hardware_amortizable"
    MOBILIARIO_AMORTIZABLE = "mobiliario_amortizable"
    REPARACIONES_CONSERVACION = "reparaciones_conservacion"
    VEHICULO_COMBUSTIBLE = "vehiculo_combustible"
    VEHICULO_MANTENIMIENTO = "vehiculo_mantenimiento"
    VEHICULO_SEGURO = "vehiculo_seguro"
    VEHICULO_PEAJE = "vehiculo_peaje"
    VEHICULO_PARKING = "vehiculo_parking"
    MANUTENCION_DIETAS_NACIONAL = "manutencion_dietas_nacional"
    MANUTENCION_DIETAS_EXTRANJERO = "manutencion_dietas_extranjero"
    ASESORIA_FISCAL = "asesoria_fiscal"
    ASESORIA_JURIDICA = "asesoria_juridica"
    ASESORIA_CONTABLE = "asesoria_contable"
    PUBLICIDAD_MARKETING = "publicidad_marketing"
    FORMACION_PROFESIONAL = "formacion_profesional"
    VIAJES_TRANSPORTE = "viajes_transporte"
    VIAJES_ALOJAMIENTO = "viajes_alojamiento"
    SEGUROS_RESPONSABILIDAD_CIVIL = "seguros_responsabilidad_civil"
    SEGUROS_SALUD_AUTONOMO = "seguros_salud_autonomo"
    GASTOS_BANCARIOS = "gastos_bancarios"
    GASTOS_FINANCIEROS = "gastos_financieros"
    SUMINISTROS_CLIENTE_DIRECTOS = "suministros_cliente_directos"
    SUBCONTRATACION = "subcontratacion"
    TRIBUTOS_FISCALMENTE_DEDUCIBLES = "tributos_fiscalmente_deducibles"


class SpendingCategoryFamily(StrEnum):
    """Coarse families used by CLI listings and downstream classifiers.

    Each :class:`SpendingCategory` belongs to exactly one family —
    the membership table is :data:`CATEGORY_FAMILY_MEMBERS` and the
    invariant is enforced by
    :func:`aeat.domain.categories.test_spending_category.test_every_category_belongs_to_exactly_one_family`.

    The home-office bucket is split into two distinct families per
    LIRPF Art. 30.2 rule 5 (Ley 6/2017, BOE-A-2017-12544): the
    :attr:`HOME_OFFICE_SUMINISTROS` family carries the utility costs
    on which the statutory 0.30 multiplier applies on top of the
    operator-chosen vivienda afectación ratio; the
    :attr:`HOME_OFFICE_OWNERSHIP` family carries the
    titularity-attached costs (amortización, IBI, comunidad) that
    deduct at the raw vivienda afectación ratio with no statutory
    multiplier.
    """

    SOCIAL_SECURITY = "social_security"
    PREMISES = "premises"
    HOME_OFFICE_SUMINISTROS = "home_office_suministros"
    HOME_OFFICE_OWNERSHIP = "home_office_ownership"
    TELECOMS = "telecoms"
    OFFICE = "office"
    VEHICLE = "vehicle"
    MEALS = "meals"
    PROFESSIONAL_SERVICES = "professional_services"
    TRAVEL = "travel"
    INSURANCE = "insurance"
    FINANCIAL = "financial"
    DIRECT_COSTS = "direct_costs"
    TAXES = "taxes"


CATEGORY_FAMILY_MEMBERS: dict[SpendingCategoryFamily, tuple[SpendingCategory, ...]] = {
    SpendingCategoryFamily.SOCIAL_SECURITY: (
        SpendingCategory.CUOTAS_COLEGIALES,
        SpendingCategory.CUOTAS_AUTONOMOS_SS,
        SpendingCategory.MUTUALIDAD_ALTERNATIVA,
    ),
    SpendingCategoryFamily.PREMISES: (
        SpendingCategory.ARRENDAMIENTO_LOCAL,
        SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO,
        SpendingCategory.IBI_LOCAL_AFECTO,
    ),
    SpendingCategoryFamily.HOME_OFFICE_SUMINISTROS: (
        SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS,
        SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET,
    ),
    SpendingCategoryFamily.HOME_OFFICE_OWNERSHIP: (
        SpendingCategory.AMORTIZACION_VIVIENDA_AFECTO,
        SpendingCategory.IBI_VIVIENDA_AFECTO,
        SpendingCategory.COMUNIDAD_VIVIENDA_AFECTO,
    ),
    SpendingCategoryFamily.TELECOMS: (
        SpendingCategory.TELEFONIA_MOVIL,
        SpendingCategory.TELEFONIA_FIJA,
    ),
    SpendingCategoryFamily.OFFICE: (
        SpendingCategory.MATERIAL_OFICINA,
        SpendingCategory.SOFTWARE_SUSCRIPCION,
        SpendingCategory.HARDWARE_AMORTIZABLE,
        SpendingCategory.MOBILIARIO_AMORTIZABLE,
        SpendingCategory.REPARACIONES_CONSERVACION,
        SpendingCategory.PUBLICIDAD_MARKETING,
        SpendingCategory.FORMACION_PROFESIONAL,
    ),
    SpendingCategoryFamily.VEHICLE: (
        SpendingCategory.VEHICULO_COMBUSTIBLE,
        SpendingCategory.VEHICULO_MANTENIMIENTO,
        SpendingCategory.VEHICULO_SEGURO,
        SpendingCategory.VEHICULO_PEAJE,
        SpendingCategory.VEHICULO_PARKING,
    ),
    SpendingCategoryFamily.MEALS: (
        SpendingCategory.MANUTENCION_DIETAS_NACIONAL,
        SpendingCategory.MANUTENCION_DIETAS_EXTRANJERO,
    ),
    SpendingCategoryFamily.PROFESSIONAL_SERVICES: (
        SpendingCategory.ASESORIA_FISCAL,
        SpendingCategory.ASESORIA_JURIDICA,
        SpendingCategory.ASESORIA_CONTABLE,
    ),
    SpendingCategoryFamily.TRAVEL: (
        SpendingCategory.VIAJES_TRANSPORTE,
        SpendingCategory.VIAJES_ALOJAMIENTO,
    ),
    SpendingCategoryFamily.INSURANCE: (
        SpendingCategory.SEGUROS_RESPONSABILIDAD_CIVIL,
        SpendingCategory.SEGUROS_SALUD_AUTONOMO,
    ),
    SpendingCategoryFamily.FINANCIAL: (
        SpendingCategory.GASTOS_BANCARIOS,
        SpendingCategory.GASTOS_FINANCIEROS,
    ),
    SpendingCategoryFamily.DIRECT_COSTS: (
        SpendingCategory.SUMINISTROS_CLIENTE_DIRECTOS,
        SpendingCategory.SUBCONTRATACION,
    ),
    SpendingCategoryFamily.TAXES: (SpendingCategory.TRIBUTOS_FISCALMENTE_DEDUCIBLES,),
}
"""Static membership table from :class:`SpendingCategoryFamily` to its members.

Every :class:`SpendingCategory` appears in exactly one entry. The
table is the source of truth for :func:`family_for` and
:func:`categories_for_family`.
"""


def family_for(category: SpendingCategory) -> SpendingCategoryFamily:
    """Return the coarse family that a spending category belongs to.

    Args:
        category: A :class:`SpendingCategory` member.

    Returns:
        The unique :class:`SpendingCategoryFamily` containing
        ``category``.

    Raises:
        KeyError: If ``category`` is not registered in
            :data:`CATEGORY_FAMILY_MEMBERS`.
    """
    for family, members in CATEGORY_FAMILY_MEMBERS.items():
        if category in members:
            return family
    raise KeyError(f"unmapped spending category family: {category.value}")


def categories_for_family(family: SpendingCategoryFamily) -> tuple[SpendingCategory, ...]:
    """Return the categories belonging to a coarse family.

    Args:
        family: A :class:`SpendingCategoryFamily` member.

    Returns:
        Tuple of :class:`SpendingCategory` members in the family.
    """
    return CATEGORY_FAMILY_MEMBERS[family]
