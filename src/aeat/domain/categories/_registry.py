"""Curated 2025 AEAT spending-category registry."""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType

from ...core.i18n import Translatable
from ._profile import CategoryProfile, VatCategory
from ._proportionality import (
    CategoryCitation,
    CategoryCitationSource,
    ProportionalityKind,
    ProportionalityRule,
    StatutoryCapPeriod,
    parse_http_url,
)
from ._spending_category import SpendingCategory

_MANUAL_RENTA_2025 = "https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IRPF/IRPF-2025/ManualRenta2025Parte1_es_es.pdf"
_MANUAL_IVA_2025 = (
    "https://sede.agenciatributaria.gob.es/static_files/Sede/Biblioteca/Manual/Practicos/IVA/Manual_IVA_2025.pdf"
)
_LEY_IRPF = "https://www.boe.es/buscar/act.php?id=BOE-A-2006-20764"
_REGLAMENTO_IRPF = "https://www.boe.es/eli/es/rd/2007/03/30/439/con"
_AEAT_RETA = (
    "https://sede.agenciatributaria.gob.es/Sede/ayuda/manuales-videos-folletos/manuales-ayuda-presentacion/"
    "irpf-2025/7-cumplimentacion-irpf/7_4-rendimientos-actividades-economicas/7_4_2-regimen-estimacion-directa/"
    "7_4_2_3-gastos-fiscalmente-deducibles/cotizaciones-reta.html"
)


def _label(message: str) -> Translatable:
    """Build a multilingual label payload."""

    return Translatable(message)


def _citation(
    *,
    source: CategoryCitationSource,
    reference: str,
    locator: str,
    url: str,
    quote_es: str,
) -> CategoryCitation:
    """Build a citation with a compact Spanish quote."""
    return CategoryCitation(
        source=source,
        reference=reference,
        locator=locator,
        url=parse_http_url(url),
        quote_es=quote_es,
    )


def _rule(
    *,
    kind: ProportionalityKind,
    citations: tuple[CategoryCitation, ...],
    notes_es: str,
    fixed_pct: Decimal | None = None,
    default_ratio: Decimal | None = None,
    statutory_cap_eur_per_day: Decimal | None = None,
    statutory_cap_eur: Decimal | None = None,
    statutory_cap_period: StatutoryCapPeriod | None = None,
) -> ProportionalityRule:
    """Build a proportionality rule."""

    return ProportionalityRule(
        kind=kind,
        fixed_pct=fixed_pct,
        default_ratio=default_ratio,
        statutory_cap_eur_per_day=statutory_cap_eur_per_day,
        statutory_cap_eur=statutory_cap_eur,
        statutory_cap_period=statutory_cap_period,
        citations=citations,
        notes_es=notes_es,
    )


def _profile(
    *,
    category: SpendingCategory,
    label: Translatable,
    proportionality: ProportionalityRule,
    vat_hint: VatCategory | None,
) -> CategoryProfile:
    """Build a category profile."""

    return CategoryProfile(
        category=category,
        display_label=label,
        proportionality=proportionality,
        vat_hint=vat_hint,
    )


_CIT_GENERAL_EXPENSES = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Rendimientos de actividades económicas, gastos fiscalmente deducibles",
        url=_MANUAL_RENTA_2025,
        quote_es="Son deducibles los gastos necesarios para la obtención de ingresos.",
    ),
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="El rendimiento neto se determinará según las normas del Impuesto sobre Sociedades.",
    ),
)
_CIT_HOME_SUPPLIES = (
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30.2.5.b",
        url=_LEY_IRPF,
        quote_es=(
            "Se aplicará el 30 por ciento a la proporción existente entre los metros afectos y la superficie total."
        ),
    ),
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Vivienda parcialmente afecta",
        url=_MANUAL_RENTA_2025,
        quote_es="Los suministros de la vivienda afecta se deducen con el límite legal de afectación parcial.",
    ),
)
_CIT_TELEFONIA_MOVIL = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Afectación exclusiva del elemento patrimonial",
        url=_MANUAL_RENTA_2025,
        quote_es=(
            "Los bienes divisibles o de uso mixto exigen prueba de afectación exclusiva para la deducción íntegra."
        ),
    ),
    _citation(
        source=CategoryCitationSource.REGLAMENTO_IRPF,
        reference="Reglamento IRPF",
        locator="art. 22",
        url=_REGLAMENTO_IRPF,
        quote_es="Solo se consideran afectos los elementos utilizados exclusivamente para la actividad.",
    ),
)
_CIT_DIETAS = (
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 6/2017 / Ley IRPF",
        locator="art. 30.2.5.c",
        url=_LEY_IRPF,
        quote_es="Serán deducibles los gastos de manutención del propio contribuyente con los límites reglamentarios.",
    ),
    _citation(
        source=CategoryCitationSource.REGLAMENTO_IRPF,
        reference="Reglamento IRPF",
        locator="art. 9.A.3.a",
        url=_REGLAMENTO_IRPF,
        quote_es="En territorio español el límite general es 53,34 euros diarios con pernocta.",
    ),
)
_CIT_VEHICLE = (
    _citation(
        source=CategoryCitationSource.REGLAMENTO_IRPF,
        reference="Reglamento IRPF",
        locator="art. 22",
        url=_REGLAMENTO_IRPF,
        quote_es="Los turismos se presumen no afectos salvo prueba de utilización exclusiva en la actividad.",
    ),
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Vehículos y afectación exclusiva",
        url=_MANUAL_RENTA_2025,
        quote_es="Los gastos del vehículo ordinario quedan condicionados a la afectación exclusiva.",
    ),
)
_CIT_RETA = (
    _citation(
        source=CategoryCitationSource.AEAT_HELP,
        reference="AEAT ayuda Renta 2025",
        locator="Cotizaciones al RETA",
        url=_AEAT_RETA,
        quote_es="Las cotizaciones al RETA tienen la consideración de gasto fiscalmente deducible.",
    ),
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Seguridad Social del titular",
        url=_MANUAL_RENTA_2025,
        quote_es="Son gasto deducible las cotizaciones del titular a la Seguridad Social.",
    ),
)
_CIT_PROFESSIONAL_SERVICES = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Servicios de profesionales independientes",
        url=_MANUAL_RENTA_2025,
        quote_es="Los servicios exteriores necesarios para la actividad tienen la consideración de gasto deducible.",
    ),
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="Se aplican las reglas generales de gastos correlacionados con los ingresos.",
    ),
)
_CIT_OTHER_SERVICES = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Otros servicios exteriores",
        url=_MANUAL_RENTA_2025,
        quote_es=(
            "Publicidad, formación, transportes y otros servicios exteriores "
            "son deducibles cuando se correlacionan con la actividad."
        ),
    ),
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="El gasto debe quedar vinculado a la obtención de ingresos.",
    ),
)
_CIT_HEALTH_INSURANCE = (
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30.2.5.c regla 1.a",
        url=_LEY_IRPF,
        quote_es="Son deducibles las primas de seguro de enfermedad con el límite de 500 euros por persona asegurada.",
    ),
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Primas de seguro de enfermedad",
        url=_MANUAL_RENTA_2025,
        quote_es="El límite asciende a 1.500 euros por persona con discapacidad.",
    ),
)
_CIT_AMORTIZATION = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Amortizaciones del inmovilizado",
        url=_MANUAL_RENTA_2025,
        quote_es="Las inversiones en inmovilizado se deducen mediante las amortizaciones fiscalmente admitidas.",
    ),
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="La deducción sigue las reglas de amortización aplicables al rendimiento neto.",
    ),
)
_CIT_TAXES = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Tributos fiscalmente deducibles",
        url=_MANUAL_RENTA_2025,
        quote_es="Son deducibles los tributos no estatales que recaen sobre elementos afectos.",
    ),
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 14 LIS por remisión",
        url=_LEY_IRPF,
        quote_es="No tienen la consideración de deducibles los tributos expresamente excluidos por la norma.",
    ),
)
_CIT_FINANCIAL = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Gastos financieros y bancarios",
        url=_MANUAL_RENTA_2025,
        quote_es="Los gastos financieros vinculados a la actividad pueden deducirse como gasto corriente.",
    ),
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="La deducibilidad exige correlación con la actividad económica.",
    ),
)
_CIT_LOCAL_RENT = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Arrendamientos y cánones",
        url=_MANUAL_RENTA_2025,
        quote_es="Los arrendamientos del local afecto son gasto deducible de la actividad.",
    ),
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="El alquiler del local afecto se integra entre los gastos necesarios.",
    ),
)
_CIT_HOME_RENT = (
    _citation(
        source=CategoryCitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Vivienda parcialmente afecta",
        url=_MANUAL_RENTA_2025,
        quote_es="La vivienda parcialmente afecta exige prorratear solo los gastos admitidos por la norma.",
    ),
    _citation(
        source=CategoryCitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30.2.5.b",
        url=_LEY_IRPF,
        quote_es="La regla especial de vivienda afecta se aplica a los suministros y gastos compatibles.",
    ),
)

_PROFILE_BY_CATEGORY: dict[SpendingCategory, CategoryProfile] = {
    SpendingCategory.CUOTAS_COLEGIALES: _profile(
        category=SpendingCategory.CUOTAS_COLEGIALES,
        label=_label("categories.registry.cuotas_colegiales"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=(_CIT_GENERAL_EXPENSES[0],),
            notes_es="Suscripción necesaria para el ejercicio de la actividad profesional.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.CUOTAS_AUTONOMOS_SS: _profile(
        category=SpendingCategory.CUOTAS_AUTONOMOS_SS,
        label=_label("categories.registry.cuotas_reta"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_RETA,
            notes_es="Cotizaciones al RETA del titular de la actividad.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.MUTUALIDAD_ALTERNATIVA: _profile(
        category=SpendingCategory.MUTUALIDAD_ALTERNATIVA,
        label=_label("categories.registry.mutualidad_alternativa"),
        proportionality=_rule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=_CIT_RETA,
            notes_es="Las cuotas de mutualidades alternativas al RETA son gasto en lugar de reducción en base imponible.",
            statutory_cap_eur=Decimal("15000"),
            statutory_cap_period=StatutoryCapPeriod.YEAR_PER_PERSON,
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.ARRENDAMIENTO_LOCAL: _profile(
        category=SpendingCategory.ARRENDAMIENTO_LOCAL,
        label=_label("categories.registry.arrendamiento_local"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_LOCAL_RENT,
            notes_es="Alquiler del local afecto exclusivamente a la actividad.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO: _profile(
        category=SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO,
        label=_label("categories.registry.arrendamiento_vivienda_afecta"),
        proportionality=_rule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            citations=_CIT_HOME_RENT,
            notes_es="Regla especial: 30% del porcentaje de afectación.",
            default_ratio=Decimal("0.30"),
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.IBI_LOCAL_AFECTO: _profile(
        category=SpendingCategory.IBI_LOCAL_AFECTO,
        label=_label("categories.registry.ibi_local_afecto"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_TAXES,
            notes_es="IBI y tasas municipales sobre inmuebles de uso exclusivo.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: _profile(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        label=_label("categories.registry.home_office_luz"),
        proportionality=_rule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Electricidad de vivienda afecta: 30% de la proporción m2.",
            default_ratio=Decimal("0.30"),
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA: _profile(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA,
        label=_label("categories.registry.home_office_agua"),
        proportionality=_rule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Agua de vivienda afecta: 30% de la proporción m2.",
            default_ratio=Decimal("0.30"),
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS: _profile(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS,
        label=_label("categories.registry.home_office_gas"),
        proportionality=_rule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Gas de vivienda afecta: 30% de la proporción m2.",
            default_ratio=Decimal("0.30"),
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET: _profile(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET,
        label=_label("categories.registry.home_office_internet"),
        proportionality=_rule(
            kind=ProportionalityKind.FIXED_PERCENTAGE,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Internet de vivienda afecta: 30% de la proporción m2.",
            default_ratio=Decimal("0.30"),
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.TELEFONIA_MOVIL: _profile(
        category=SpendingCategory.TELEFONIA_MOVIL,
        label=_label("categories.registry.telefonia_movil"),
        proportionality=_rule(
            kind=ProportionalityKind.REQUIRES_EXCLUSIVE_USE,
            citations=_CIT_TELEFONIA_MOVIL,
            notes_es="Requiere línea independiente dedicada en exclusiva a la actividad.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.TELEFONIA_FIJA: _profile(
        category=SpendingCategory.TELEFONIA_FIJA,
        label=_label("categories.registry.telefonia_fija"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Gastos de telefonía fija en local afecto.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.MATERIAL_OFICINA: _profile(
        category=SpendingCategory.MATERIAL_OFICINA,
        label=_label("categories.registry.material_oficina"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Consumibles de oficina ordinarios.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SOFTWARE_SUSCRIPCION: _profile(
        category=SpendingCategory.SOFTWARE_SUSCRIPCION,
        label=_label("categories.registry.software_suscripcion"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Licencias SaaS, cloud y herramientas digitales.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.HARDWARE_AMORTIZABLE: _profile(
        category=SpendingCategory.HARDWARE_AMORTIZABLE,
        label=_label("categories.registry.hardware_amortizable"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_AMORTIZATION,
            notes_es="Equipos informáticos. Deducible vía amortización plurianual.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.MOBILIARIO_AMORTIZABLE: _profile(
        category=SpendingCategory.MOBILIARIO_AMORTIZABLE,
        label=_label("categories.registry.mobiliario_amortizable"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_AMORTIZATION,
            notes_es="Muebles y enseres. Deducible vía amortización plurianual.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.REPARACIONES_CONSERVACION: _profile(
        category=SpendingCategory.REPARACIONES_CONSERVACION,
        label=_label("categories.registry.reparaciones_conservacion"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Mantenimiento de bienes de inversión afectos.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VEHICULO_COMBUSTIBLE: _profile(
        category=SpendingCategory.VEHICULO_COMBUSTIBLE,
        label=_label("categories.registry.vehiculo_combustible"),
        proportionality=_rule(
            kind=ProportionalityKind.REQUIRES_EXCLUSIVE_USE,
            citations=_CIT_VEHICLE,
            notes_es="Presunción de no afectación salvo prueba fehaciente (IRPF).",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VEHICULO_MANTENIMIENTO: _profile(
        category=SpendingCategory.VEHICULO_MANTENIMIENTO,
        label=_label("categories.registry.vehiculo_mantenimiento"),
        proportionality=_rule(
            kind=ProportionalityKind.REQUIRES_EXCLUSIVE_USE,
            citations=_CIT_VEHICLE,
            notes_es="Presunción de no afectación salvo prueba fehaciente (IRPF).",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VEHICULO_SEGURO: _profile(
        category=SpendingCategory.VEHICULO_SEGURO,
        label=_label("categories.registry.vehiculo_seguro"),
        proportionality=_rule(
            kind=ProportionalityKind.REQUIRES_EXCLUSIVE_USE,
            citations=_CIT_VEHICLE,
            notes_es="Presunción de no afectación salvo prueba fehaciente (IRPF).",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.VEHICULO_PEAJE: _profile(
        category=SpendingCategory.VEHICULO_PEAJE,
        label=_label("categories.registry.vehiculo_peaje"),
        proportionality=_rule(
            kind=ProportionalityKind.REQUIRES_EXCLUSIVE_USE,
            citations=_CIT_VEHICLE,
            notes_es="Presunción de no afectación salvo prueba fehaciente (IRPF).",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VEHICULO_PARKING: _profile(
        category=SpendingCategory.VEHICULO_PARKING,
        label=_label("categories.registry.vehiculo_parking"),
        proportionality=_rule(
            kind=ProportionalityKind.REQUIRES_EXCLUSIVE_USE,
            citations=_CIT_VEHICLE,
            notes_es="Presunción de no afectación salvo prueba fehaciente (IRPF).",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.MANUTENCION_DIETAS_NACIONAL: _profile(
        category=SpendingCategory.MANUTENCION_DIETAS_NACIONAL,
        label=_label("categories.registry.manutencion_nacional"),
        proportionality=_rule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=_CIT_DIETAS,
            notes_es="Límite reglamentario: 53,34 EUR/día (con pernocta), 26,67 EUR/día (sin). Pago electrónico obligatorio.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.MANUTENCION_DIETAS_EXTRANJERO: _profile(
        category=SpendingCategory.MANUTENCION_DIETAS_EXTRANJERO,
        label=_label("categories.registry.manutencion_extranjero"),
        proportionality=_rule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=_CIT_DIETAS,
            notes_es="Límite reglamentario: 91,35 EUR/día (con pernocta), 48,08 EUR/día (sin). Pago electrónico obligatorio.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.ASESORIA_FISCAL: _profile(
        category=SpendingCategory.ASESORIA_FISCAL,
        label=_label("categories.registry.asesoria_fiscal"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_PROFESSIONAL_SERVICES,
            notes_es="Gastos por servicios de gestoría y asesoramiento.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.ASESORIA_JURIDICA: _profile(
        category=SpendingCategory.ASESORIA_JURIDICA,
        label=_label("categories.registry.asesoria_juridica"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_PROFESSIONAL_SERVICES,
            notes_es="Honorarios de abogados y procuradores por asuntos vinculados a la actividad.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.ASESORIA_CONTABLE: _profile(
        category=SpendingCategory.ASESORIA_CONTABLE,
        label=_label("categories.registry.asesoria_contable"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_PROFESSIONAL_SERVICES,
            notes_es="Servicios de contabilidad y teneduría de libros.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.PUBLICIDAD_MARKETING: _profile(
        category=SpendingCategory.PUBLICIDAD_MARKETING,
        label=_label("categories.registry.publicidad_marketing"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="Relaciones públicas, campañas publicitarias y promocionales.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.FORMACION_PROFESIONAL: _profile(
        category=SpendingCategory.FORMACION_PROFESIONAL,
        label=_label("categories.registry.formacion_profesional"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="Asistencia a cursos, congresos y seminarios vinculados a la actividad.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VIAJES_TRANSPORTE: _profile(
        category=SpendingCategory.VIAJES_TRANSPORTE,
        label=_label("categories.registry.viajes_transporte"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="Billetes de avión, tren y transporte público por desplazamientos profesionales.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VIAJES_ALOJAMIENTO: _profile(
        category=SpendingCategory.VIAJES_ALOJAMIENTO,
        label=_label("categories.registry.viajes_alojamiento"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="Hoteles y alojamiento por desplazamientos profesionales (sin límite como las dietas).",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SEGUROS_RESPONSABILIDAD_CIVIL: _profile(
        category=SpendingCategory.SEGUROS_RESPONSABILIDAD_CIVIL,
        label=_label("categories.registry.seguros_rc"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Primas de seguros exigidos para el ejercicio de la actividad profesional.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.SEGUROS_SALUD_AUTONOMO: _profile(
        category=SpendingCategory.SEGUROS_SALUD_AUTONOMO,
        label=_label("categories.registry.seguros_salud"),
        proportionality=_rule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=_CIT_HEALTH_INSURANCE,
            notes_es="Límite 500 EUR anuales (1.500 EUR con discapacidad) para titular, cónyuge e hijos menores de 25.",
            statutory_cap_eur=Decimal("500"),
            statutory_cap_period=StatutoryCapPeriod.YEAR_PER_PERSON,
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.GASTOS_BANCARIOS: _profile(
        category=SpendingCategory.GASTOS_BANCARIOS,
        label=_label("categories.registry.gastos_bancarios"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_FINANCIAL,
            notes_es="Comisiones de mantenimiento, tarjetas y TPV de cuentas vinculadas a la actividad.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.GASTOS_FINANCIEROS: _profile(
        category=SpendingCategory.GASTOS_FINANCIEROS,
        label=_label("categories.registry.gastos_financieros"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_FINANCIAL,
            notes_es="Intereses de préstamos y pólizas de crédito afectos a la actividad.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.SUMINISTROS_CLIENTE_DIRECTOS: _profile(
        category=SpendingCategory.SUMINISTROS_CLIENTE_DIRECTOS,
        label=_label("categories.registry.suministros_cliente_directos"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Costes directos refacturados o incorporados al servicio del cliente (servidores, APIs, materiales).",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SUBCONTRATACION: _profile(
        category=SpendingCategory.SUBCONTRATACION,
        label=_label("categories.registry.subcontratacion"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_PROFESSIONAL_SERVICES,
            notes_es="Trabajos realizados por otros profesionales para incorporar a proyectos de clientes.",
        ),
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.TRIBUTOS_FISCALMENTE_DEDUCIBLES: _profile(
        category=SpendingCategory.TRIBUTOS_FISCALMENTE_DEDUCIBLES,
        label=_label("categories.registry.tributos_deducibles"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_TAXES,
            notes_es="IAE, IAE autonómico y tasas no penalizadoras que recaigan sobre la actividad.",
        ),
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
}

if set(_PROFILE_BY_CATEGORY) != set(SpendingCategory):
    missing = sorted(category.value for category in set(SpendingCategory) - set(_PROFILE_BY_CATEGORY))
    extra = sorted(category.value for category in set(_PROFILE_BY_CATEGORY) - set(SpendingCategory))
    raise RuntimeError(f"incomplete category registry: missing={missing} extra={extra}")

CATEGORY_PROFILES_2025 = MappingProxyType(_PROFILE_BY_CATEGORY)
