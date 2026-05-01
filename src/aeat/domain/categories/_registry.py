"""Curated 2025 AEAT spending-category registry."""

from __future__ import annotations

from decimal import Decimal
from types import MappingProxyType

from ...core.i18n import Translatable
from ..casillas import ModeloCode, PeriodType
from ._casilla_mapping import CasillaMapping, CasillaMappingSign
from ._profile import CategoryProfile, VatCategory
from ._proportionality import (
    Citation,
    CitationSource,
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

_EXPENSE_IRPF = (
    CasillaMapping(
        modelo=ModeloCode.MODELO_130,
        period_type=PeriodType.QUARTERLY,
        casilla_code="01",
        sign=CasillaMappingSign.CREDIT,
    ),
)
_COARSE_IVA = (
    CasillaMapping(
        modelo=ModeloCode.MODELO_303,
        period_type=PeriodType.QUARTERLY,
        casilla_code="71",
        sign=CasillaMappingSign.CREDIT,
    ),
)


def _label(es: str, en: str, hu: str) -> Translatable:
    """Build a trilingual label payload."""

    return {"es": es, "en": en, "hu": hu}


def _citation(
    *,
    source: CitationSource,
    reference: str,
    locator: str,
    url: str,
    quote_es: str,
) -> Citation:
    """Build a citation with a compact Spanish quote."""

    return Citation(
        source=source,
        reference=reference,
        locator=locator,
        url=parse_http_url(url),
        quote_es=quote_es,
    )


def _rule(
    *,
    kind: ProportionalityKind,
    citations: tuple[Citation, ...],
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
    casilla_mappings: tuple[CasillaMapping, ...],
    vat_hint: VatCategory | None,
) -> CategoryProfile:
    """Build a category profile."""

    return CategoryProfile(
        category=category,
        display_label=label,
        proportionality=proportionality,
        casilla_mappings=casilla_mappings,
        vat_hint=vat_hint,
    )


_CIT_GENERAL_EXPENSES = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Rendimientos de actividades económicas, gastos fiscalmente deducibles",
        url=_MANUAL_RENTA_2025,
        quote_es="Son deducibles los gastos necesarios para la obtención de ingresos.",
    ),
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="El rendimiento neto se determinará según las normas del Impuesto sobre Sociedades.",
    ),
)
_CIT_HOME_SUPPLIES = (
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30.2.5.b",
        url=_LEY_IRPF,
        quote_es=(
            "Se aplicará el 30 por ciento a la proporción existente entre los metros afectos y la superficie total."
        ),
    ),
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Vivienda parcialmente afecta",
        url=_MANUAL_RENTA_2025,
        quote_es="Los suministros de la vivienda afecta se deducen con el límite legal de afectación parcial.",
    ),
)
_CIT_TELEFONIA_MOVIL = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Afectación exclusiva del elemento patrimonial",
        url=_MANUAL_RENTA_2025,
        quote_es=(
            "Los bienes divisibles o de uso mixto exigen prueba de afectación exclusiva para la deducción íntegra."
        ),
    ),
    _citation(
        source=CitationSource.REGLAMENTO_IRPF,
        reference="Reglamento IRPF",
        locator="art. 22",
        url=_REGLAMENTO_IRPF,
        quote_es="Solo se consideran afectos los elementos utilizados exclusivamente para la actividad.",
    ),
)
_CIT_DIETAS = (
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 6/2017 / Ley IRPF",
        locator="art. 30.2.5.c",
        url=_LEY_IRPF,
        quote_es="Serán deducibles los gastos de manutención del propio contribuyente con los límites reglamentarios.",
    ),
    _citation(
        source=CitationSource.REGLAMENTO_IRPF,
        reference="Reglamento IRPF",
        locator="art. 9.A.3.a",
        url=_REGLAMENTO_IRPF,
        quote_es="En territorio español el límite general es 53,34 euros diarios con pernocta.",
    ),
)
_CIT_VEHICLE = (
    _citation(
        source=CitationSource.REGLAMENTO_IRPF,
        reference="Reglamento IRPF",
        locator="art. 22",
        url=_REGLAMENTO_IRPF,
        quote_es="Los turismos se presumen no afectos salvo prueba de utilización exclusiva en la actividad.",
    ),
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Vehículos y afectación exclusiva",
        url=_MANUAL_RENTA_2025,
        quote_es="Los gastos del vehículo ordinario quedan condicionados a la afectación exclusiva.",
    ),
)
_CIT_RETA = (
    _citation(
        source=CitationSource.AEAT_HELP,
        reference="AEAT ayuda Renta 2025",
        locator="Cotizaciones al RETA",
        url=_AEAT_RETA,
        quote_es="Las cotizaciones al RETA tienen la consideración de gasto fiscalmente deducible.",
    ),
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Seguridad Social del titular",
        url=_MANUAL_RENTA_2025,
        quote_es="Son gasto deducible las cotizaciones del titular a la Seguridad Social.",
    ),
)
_CIT_PROFESSIONAL_SERVICES = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Servicios de profesionales independientes",
        url=_MANUAL_RENTA_2025,
        quote_es="Los servicios exteriores necesarios para la actividad tienen la consideración de gasto deducible.",
    ),
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="Se aplican las reglas generales de gastos correlacionados con los ingresos.",
    ),
)
_CIT_OTHER_SERVICES = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Otros servicios exteriores",
        url=_MANUAL_RENTA_2025,
        quote_es=(
            "Publicidad, formación, transportes y otros servicios exteriores "
            "son deducibles cuando se correlacionan con la actividad."
        ),
    ),
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="El gasto debe quedar vinculado a la obtención de ingresos.",
    ),
)
_CIT_HEALTH_INSURANCE = (
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30.2.5.c regla 1.a",
        url=_LEY_IRPF,
        quote_es="Son deducibles las primas de seguro de enfermedad con el límite de 500 euros por persona asegurada.",
    ),
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Primas de seguro de enfermedad",
        url=_MANUAL_RENTA_2025,
        quote_es="El límite asciende a 1.500 euros por persona con discapacidad.",
    ),
)
_CIT_AMORTIZATION = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Amortizaciones del inmovilizado",
        url=_MANUAL_RENTA_2025,
        quote_es="Las inversiones en inmovilizado se deducen mediante las amortizaciones fiscalmente admitidas.",
    ),
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="La deducción sigue las reglas de amortización aplicables al rendimiento neto.",
    ),
)
_CIT_TAXES = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Tributos fiscalmente deducibles",
        url=_MANUAL_RENTA_2025,
        quote_es="Son deducibles los tributos no estatales que recaen sobre elementos afectos.",
    ),
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 14 LIS por remisión",
        url=_LEY_IRPF,
        quote_es="No tienen la consideración de deducibles los tributos expresamente excluidos por la norma.",
    ),
)
_CIT_FINANCIAL = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Gastos financieros y bancarios",
        url=_MANUAL_RENTA_2025,
        quote_es="Los gastos financieros vinculados a la actividad pueden deducirse como gasto corriente.",
    ),
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="La deducibilidad exige correlación con la actividad económica.",
    ),
)
_CIT_LOCAL_RENT = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Arrendamientos y cánones",
        url=_MANUAL_RENTA_2025,
        quote_es="Los arrendamientos del local afecto son gasto deducible de la actividad.",
    ),
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 28.1",
        url=_LEY_IRPF,
        quote_es="El alquiler del local afecto se integra entre los gastos necesarios.",
    ),
)
_CIT_HOME_RENT = (
    _citation(
        source=CitationSource.MANUAL_RENTA,
        reference="Manual práctico Renta 2025",
        locator="Vivienda parcialmente afecta",
        url=_MANUAL_RENTA_2025,
        quote_es="La vivienda parcialmente afecta exige prorratear solo los gastos admitidos por la norma.",
    ),
    _citation(
        source=CitationSource.LEY_IRPF,
        reference="Ley 35/2006",
        locator="art. 30.2.5.b",
        url=_LEY_IRPF,
        quote_es="La regla especial de vivienda afecta se aplica a los suministros y gastos compatibles.",
    ),
)

_PROFILE_BY_CATEGORY: dict[SpendingCategory, CategoryProfile] = {
    SpendingCategory.CUOTAS_COLEGIALES: _profile(
        category=SpendingCategory.CUOTAS_COLEGIALES,
        label=_label("Cuotas colegiales", "Professional association fees", "Szakmai kamarai díjak"),
        proportionality=_rule(
            kind=ProportionalityKind.NON_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es=(
                "Se mantiene un perfil conservador hasta distinguir colegiación obligatoria de cuotas voluntarias."
            ),
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.CUOTAS_AUTONOMOS_SS: _profile(
        category=SpendingCategory.CUOTAS_AUTONOMOS_SS,
        label=_label("Cuotas RETA", "Self-employed social security", "Önálló vállalkozói társadalombiztosítás"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_RETA,
            notes_es="Deducibilidad íntegra como gasto del titular cuando corresponde a la actividad.",
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.MUTUALIDAD_ALTERNATIVA: _profile(
        category=SpendingCategory.MUTUALIDAD_ALTERNATIVA,
        label=_label("Mutualidad alternativa", "Alternative mutual scheme", "Alternatív szakmai biztosító"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_RETA,
            notes_es="Se alinea con las cotizaciones obligatorias del profesional cuando sustituye al RETA.",
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.ARRENDAMIENTO_LOCAL: _profile(
        category=SpendingCategory.ARRENDAMIENTO_LOCAL,
        label=_label("Arrendamiento de local", "Business premises rent", "Üzlethelyiség bérleti díja"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_LOCAL_RENT,
            notes_es="Deducible íntegramente cuando el inmueble está totalmente afecto a la actividad.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO: _profile(
        category=SpendingCategory.ARRENDAMIENTO_VIVIENDA_AFECTO,
        label=_label(
            "Arrendamiento de vivienda afecta",
            "Partially allocated dwelling rent",
            "Részben üzleti célra használt lakás bérleti díja",
        ),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
            citations=_CIT_HOME_RENT,
            notes_es=(
                "Perfil conservador basado en la proporción de superficie afecta y sujeto a justificación reforzada."
            ),
            default_ratio=Decimal("0.30"),
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.IBI_LOCAL_AFECTO: _profile(
        category=SpendingCategory.IBI_LOCAL_AFECTO,
        label=_label("IBI del local afecto", "Business premises property tax", "Üzlethelyiség ingatlanadója"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_TAXES,
            notes_es="Deducible para inmuebles afectos no excluidos expresamente por la norma.",
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ: _profile(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_LUZ,
        label=_label("Suministro home office: luz", "Home-office electricity", "Otthoni iroda villany"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Aplicar el 30% sobre la proporción entre superficie afecta y superficie total.",
            default_ratio=Decimal("0.30"),
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA: _profile(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_AGUA,
        label=_label("Suministro home office: agua", "Home-office water", "Otthoni iroda víz"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Aplicar el 30% sobre la proporción entre superficie afecta y superficie total.",
            default_ratio=Decimal("0.30"),
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS: _profile(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_GAS,
        label=_label("Suministro home office: gas", "Home-office gas", "Otthoni iroda gáz"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Aplicar el 30% sobre la proporción entre superficie afecta y superficie total.",
            default_ratio=Decimal("0.30"),
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET: _profile(
        category=SpendingCategory.SUMINISTROS_HOME_OFFICE_INTERNET,
        label=_label("Suministro home office: internet", "Home-office internet", "Otthoni iroda internet"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Se reutiliza la regla legal de suministros de vivienda parcialmente afecta.",
            default_ratio=Decimal("0.30"),
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.TELEFONIA_MOVIL: _profile(
        category=SpendingCategory.TELEFONIA_MOVIL,
        label=_label("Telefonía móvil", "Mobile phone service", "Mobiltelefon-szolgáltatás"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_PERSONAL,
            citations=_CIT_TELEFONIA_MOVIL,
            notes_es="La deducción exige acreditar uso profesional exclusivo o una línea separada.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.TELEFONIA_FIJA: _profile(
        category=SpendingCategory.TELEFONIA_FIJA,
        label=_label("Telefonía fija", "Fixed-line phone service", "Vezetékes telefon"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_HOME_AREA,
            citations=_CIT_HOME_SUPPLIES,
            notes_es="Cuando la línea está integrada en la vivienda afecta se aplica la regla de suministros.",
            default_ratio=Decimal("0.30"),
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.MATERIAL_OFICINA: _profile(
        category=SpendingCategory.MATERIAL_OFICINA,
        label=_label("Material de oficina", "Office supplies", "Irodaszerek"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="Gasto corriente deducible cuando existe vinculación con la actividad.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SOFTWARE_SUSCRIPCION: _profile(
        category=SpendingCategory.SOFTWARE_SUSCRIPCION,
        label=_label("Suscripción software", "Software subscription", "Szoftver-előfizetés"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="Tratamiento de servicio exterior recurrente siempre que el uso sea profesional.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.HARDWARE_AMORTIZABLE: _profile(
        category=SpendingCategory.HARDWARE_AMORTIZABLE,
        label=_label("Hardware amortizable", "Depreciable hardware", "Amortizálható hardver"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_AMORTIZATION,
            notes_es=(
                "Sin prorrata especial de proporcionalidad; el reconocimiento "
                "cuantitativo depende de la amortización fiscal."
            ),
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.MOBILIARIO_AMORTIZABLE: _profile(
        category=SpendingCategory.MOBILIARIO_AMORTIZABLE,
        label=_label("Mobiliario amortizable", "Depreciable furniture", "Amortizálható bútor"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_AMORTIZATION,
            notes_es=(
                "Sin prorrata especial de proporcionalidad; la deducción material depende de la tabla de amortización."
            ),
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.REPARACIONES_CONSERVACION: _profile(
        category=SpendingCategory.REPARACIONES_CONSERVACION,
        label=_label("Reparaciones y conservación", "Repairs and maintenance", "Javítás és karbantartás"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Deducible como gasto de mantenimiento cuando no incrementa el valor del activo.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VEHICULO_COMBUSTIBLE: _profile(
        category=SpendingCategory.VEHICULO_COMBUSTIBLE,
        label=_label("Vehículo: combustible", "Vehicle fuel", "Jármű üzemanyag"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_PERSONAL,
            citations=_CIT_VEHICLE,
            notes_es=(
                "El turismo ordinario exige afectación exclusiva; no se fija una ratio por defecto en este sustrato."
            ),
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VEHICULO_MANTENIMIENTO: _profile(
        category=SpendingCategory.VEHICULO_MANTENIMIENTO,
        label=_label("Vehículo: mantenimiento", "Vehicle maintenance", "Jármű karbantartás"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_PERSONAL,
            citations=_CIT_VEHICLE,
            notes_es="Los gastos accesorios siguen la afectación exclusiva del vehículo principal cuando procede.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VEHICULO_SEGURO: _profile(
        category=SpendingCategory.VEHICULO_SEGURO,
        label=_label("Vehículo: seguro", "Vehicle insurance", "Járműbiztosítás"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_PERSONAL,
            citations=_CIT_VEHICLE,
            notes_es="El seguro acompaña la afectación exclusiva exigida para el turismo ordinario.",
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.VEHICULO_PEAJE: _profile(
        category=SpendingCategory.VEHICULO_PEAJE,
        label=_label("Vehículo: peajes", "Vehicle tolls", "Jármű útdíjak"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_PERSONAL,
            citations=_CIT_VEHICLE,
            notes_es="El peaje sigue el mismo criterio de afectación exclusiva que el resto del uso del vehículo.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VEHICULO_PARKING: _profile(
        category=SpendingCategory.VEHICULO_PARKING,
        label=_label("Vehículo: parking", "Vehicle parking", "Jármű parkolás"),
        proportionality=_rule(
            kind=ProportionalityKind.USAGE_RATIO_PERSONAL,
            citations=_CIT_VEHICLE,
            notes_es="El estacionamiento acompaña la misma prueba de afectación exclusiva del vehículo.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.MANUTENCION_DIETAS_NACIONAL: _profile(
        category=SpendingCategory.MANUTENCION_DIETAS_NACIONAL,
        label=_label("Dietas de manutención nacionales", "Domestic meal allowances", "Belföldi étkezési költségek"),
        proportionality=_rule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=_CIT_DIETAS,
            notes_es="Requiere pago electrónico y consumo en hostelería; el límite sin pernocta es inferior.",
            statutory_cap_eur_per_day=Decimal("53.34"),
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.MANUTENCION_DIETAS_EXTRANJERO: _profile(
        category=SpendingCategory.MANUTENCION_DIETAS_EXTRANJERO,
        label=_label(
            "Dietas de manutención en el extranjero",
            "Foreign meal allowances",
            "Külföldi étkezési költségek",
        ),
        proportionality=_rule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=_CIT_DIETAS,
            notes_es="Requiere pago electrónico y consumo en hostelería; el límite sin pernocta es inferior.",
            statutory_cap_eur_per_day=Decimal("91.35"),
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.ASESORIA_FISCAL: _profile(
        category=SpendingCategory.ASESORIA_FISCAL,
        label=_label("Asesoría fiscal", "Tax advisory", "Adótanácsadás"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_PROFESSIONAL_SERVICES,
            notes_es="Servicio profesional ordinario directamente correlacionado con la actividad.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.ASESORIA_JURIDICA: _profile(
        category=SpendingCategory.ASESORIA_JURIDICA,
        label=_label("Asesoría jurídica", "Legal advisory", "Jogi tanácsadás"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_PROFESSIONAL_SERVICES,
            notes_es="Deducible cuando el servicio jurídico se refiere a la actividad económica.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.ASESORIA_CONTABLE: _profile(
        category=SpendingCategory.ASESORIA_CONTABLE,
        label=_label("Asesoría contable", "Accounting advisory", "Könyvelési tanácsadás"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_PROFESSIONAL_SERVICES,
            notes_es="Servicio profesional ordinario necesario para el cumplimiento formal.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.PUBLICIDAD_MARKETING: _profile(
        category=SpendingCategory.PUBLICIDAD_MARKETING,
        label=_label("Publicidad y marketing", "Advertising and marketing", "Reklám és marketing"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="Gasto de promoción deducible cuando persigue la obtención de ingresos.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.FORMACION_PROFESIONAL: _profile(
        category=SpendingCategory.FORMACION_PROFESIONAL,
        label=_label("Formación profesional", "Professional training", "Szakmai képzés"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="La formación debe guardar relación con la actividad o con su actualización profesional.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VIAJES_TRANSPORTE: _profile(
        category=SpendingCategory.VIAJES_TRANSPORTE,
        label=_label("Viajes y transporte", "Travel and transport", "Utazás és közlekedés"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="Deducible cuando el desplazamiento se realiza por razón de la actividad.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.VIAJES_ALOJAMIENTO: _profile(
        category=SpendingCategory.VIAJES_ALOJAMIENTO,
        label=_label("Viajes y alojamiento", "Travel lodging", "Utazási szállás"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_OTHER_SERVICES,
            notes_es="El alojamiento exige acreditar la finalidad profesional del desplazamiento.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SEGUROS_RESPONSABILIDAD_CIVIL: _profile(
        category=SpendingCategory.SEGUROS_RESPONSABILIDAD_CIVIL,
        label=_label("Seguro de responsabilidad civil", "Liability insurance", "Felelősségbiztosítás"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Seguro directamente vinculado al ejercicio profesional.",
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.SEGUROS_SALUD_AUTONOMO: _profile(
        category=SpendingCategory.SEGUROS_SALUD_AUTONOMO,
        label=_label(
            "Seguro de salud del autónomo",
            "Self-employed health insurance",
            "Vállalkozói egészségbiztosítás",
        ),
        proportionality=_rule(
            kind=ProportionalityKind.STATUTORY_CAP,
            citations=_CIT_HEALTH_INSURANCE,
            notes_es=(
                "Tope anual por persona asegurada; el límite asciende a 1.500 euros por persona con discapacidad."
            ),
            statutory_cap_eur=Decimal("500"),
            statutory_cap_period=StatutoryCapPeriod.YEAR_PER_PERSON,
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.GASTOS_BANCARIOS: _profile(
        category=SpendingCategory.GASTOS_BANCARIOS,
        label=_label("Gastos bancarios", "Bank charges", "Bankköltségek"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_FINANCIAL,
            notes_es="Comisiones y costes bancarios deducibles cuando la cuenta está vinculada a la actividad.",
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.GASTOS_FINANCIEROS: _profile(
        category=SpendingCategory.GASTOS_FINANCIEROS,
        label=_label("Gastos financieros", "Financing expenses", "Finanszírozási költségek"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_FINANCIAL,
            notes_es="Intereses y financiación deducibles cuando se contraen para la actividad.",
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
    SpendingCategory.SUMINISTROS_CLIENTE_DIRECTOS: _profile(
        category=SpendingCategory.SUMINISTROS_CLIENTE_DIRECTOS,
        label=_label(
            "Suministros directos al cliente",
            "Direct client supplies",
            "Ügyfélhez közvetlenül kapcsolódó anyagok",
        ),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_GENERAL_EXPENSES,
            notes_es="Consumos directamente incorporados a la prestación o entrega al cliente.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.SUBCONTRATACION: _profile(
        category=SpendingCategory.SUBCONTRATACION,
        label=_label("Subcontratación", "Subcontracting", "Alvállalkozás"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_PROFESSIONAL_SERVICES,
            notes_es="Coste directo deducible cuando la subcontrata interviene en la actividad del contribuyente.",
        ),
        casilla_mappings=_EXPENSE_IRPF + _COARSE_IVA,
        vat_hint=VatCategory.GENERAL,
    ),
    SpendingCategory.TRIBUTOS_FISCALMENTE_DEDUCIBLES: _profile(
        category=SpendingCategory.TRIBUTOS_FISCALMENTE_DEDUCIBLES,
        label=_label("Tributos fiscalmente deducibles", "Deductible taxes", "Levonható adók"),
        proportionality=_rule(
            kind=ProportionalityKind.FULL_DEDUCTIBLE,
            citations=_CIT_TAXES,
            notes_es="Incluye tributos locales o tasas no estatales no sancionadoras asociados a elementos afectos.",
        ),
        casilla_mappings=_EXPENSE_IRPF,
        vat_hint=VatCategory.EXEMPT_OR_NON_SUBJECT,
    ),
}

if set(_PROFILE_BY_CATEGORY) != set(SpendingCategory):
    missing = sorted(category.value for category in set(SpendingCategory) - set(_PROFILE_BY_CATEGORY))
    extra = sorted(category.value for category in set(_PROFILE_BY_CATEGORY) - set(SpendingCategory))
    raise RuntimeError(f"incomplete category registry: missing={missing} extra={extra}")

CATEGORY_PROFILES_2025 = MappingProxyType(_PROFILE_BY_CATEGORY)
