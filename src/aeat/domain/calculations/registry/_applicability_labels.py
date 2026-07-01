from __future__ import annotations

from ._applicability_payer_facts import PayerFact

PAYER_FACT_INCOMPLETE_LABELS: dict[PayerFact, str] = {
    PayerFact.PAYS_WITHHELD_INCOME: "paga retribuciones sujetas a retención",
    PayerFact.PAYS_RENT_WITH_RETENCION: "paga alquileres sujetos a retención",
    PayerFact.TRADES_INTRACOMMUNITY: "realiza operaciones intracomunitarias",
    PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD: "supera el umbral anual de operaciones con terceras personas",
    PayerFact.BIENES_EXTRANJERO_ABOVE_THRESHOLD: "posee bienes o derechos en el extranjero por encima del umbral",
    PayerFact.MONEDAS_VIRTUALES_EXTRANJERO_ABOVE_THRESHOLD: (
        "posee monedas virtuales situadas en el extranjero por encima del umbral"
    ),
    PayerFact.PAYS_NON_RESIDENT_INCOME: (
        "satisface rentas a no residentes sin establecimiento permanente sujetas a retención"
    ),
    PayerFact.PAYS_CAPITAL_INCOME_WITH_RETENCION: ("paga rendimientos del capital mobiliario sujetos a retención"),
    PayerFact.IVA_GROUP_MEMBER: "esta inscrito como entidad miembro de un grupo de IVA",
    PayerFact.IVA_GROUP_DOMINANT_ENTITY: "esta inscrito como entidad dominante de un grupo de IVA",
    PayerFact.MEMBER_OF_LARGE_MULTINATIONAL_GROUP: (
        "es la entidad declarante de un grupo multinacional por encima del umbral de información país por país"
    ),
    PayerFact.EU_BUSINESS_SEEKING_SPANISH_VAT_REFUND: (
        "es un empresario establecido en la UE que solicita la devolución del IVA soportado en España"
    ),
    PayerFact.REPORTS_CLIENT_SECURITIES_INSURANCE_ANNUITIES: (
        "es una entidad financiera o aseguradora que declara valores, seguros y rentas de clientes"
    ),
    PayerFact.MARKETS_LONG_TERM_SAVINGS_PLANS: (
        "comercializa Planes de Ahorro a Largo Plazo como entidad aseguradora o de crédito"
    ),
    PayerFact.CRS_REPORTING_FINANCIAL_INSTITUTION: (
        "es una institución financiera obligada a informar de cuentas financieras bajo el CRS"
    ),
    PayerFact.MANAGES_PENSION_PLAN_CONTRIBUTIONS: (
        "gestiona planes o fondos de pensiones y declara partícipes y aportaciones"
    ),
    PayerFact.PAYMENT_SERVICE_PROVIDER_CESOP: (
        "es un proveedor de servicios de pago obligado a informar de pagos transfronterizos (CESOP)"
    ),
    PayerFact.SUBJECT_TO_LOTTERY_PRIZE_SPECIAL_LEVY: (
        "obtuvo premios de loterías sujetos al gravamen especial sin retención practicada"
    ),
    PayerFact.ISSUES_NEW_ENTITY_INVESTOR_CERTIFICATIONS: (
        "es una entidad de nueva o reciente creación que emite certificaciones a sus socios"
    ),
    PayerFact.INTERMEDIATES_TOURIST_HOUSING_RENTAL: (
        "intermedia en la cesión de uso de viviendas con fines turísticos"
    ),
    PayerFact.CREDIT_INSTITUTION_REPORTING_PROPERTY_LOANS: (
        "es una entidad de crédito que informa de préstamos y operaciones financieras sobre inmuebles"
    ),
    PayerFact.RECEIVES_DEDUCTIBLE_DONATIONS: ("recibe donativos que generan derecho a deducción para el donante"),
    PayerFact.AUTHORIZED_CHILDCARE_CENTER: (
        "es una guardería o centro de educación infantil autorizado que declara gastos"
    ),
    PayerFact.REPORTING_PLATFORM_OPERATOR: ("es un operador de plataforma obligado a comunicar información (DAC7)"),
    PayerFact.PAYS_LOTTERY_PRIZES_SPECIAL_LEVY: (
        "satisface premios de loterías sujetos al gravamen especial y practica retención"
    ),
    PayerFact.MEMBER_OF_FISCAL_CONSOLIDATION_GROUP: (
        "es la entidad representante de un grupo fiscal en régimen de consolidación del Impuesto sobre Sociedades"
    ),
    PayerFact.DAC6_REPORTABLE_ARRANGEMENT_PARTY: (
        "es intermediario u obligado tributario de un mecanismo transfronterizo de planificación fiscal "
        "sujeto a declaración (DAC6)"
    ),
    PayerFact.FILES_PUBLIC_REGISTRY_OPERATIONS: (
        "es titular de un registro público que autoriza inscripciones de entidades sujetas al Impuesto sobre "
        "Sociedades"
    ),
    PayerFact.OPTS_MATERNITY_DEDUCTION_ADVANCE_PAYMENT: (
        "tiene derecho a la deducción por maternidad del IRPF y opta por su abono anticipado"
    ),
    PayerFact.REAGP_COMPENSATION_REINTEGRO: (
        "está acogido al régimen especial de la agricultura, ganadería y pesca del IVA y solicita el "
        "reintegro de compensaciones"
    ),
    PayerFact.PERFORMS_IVA_IMPORT_EQUIVALENT_OPERATIONS: (
        "realiza operaciones asimiladas a las importaciones del IVA (artículo 19 LIVA)"
    ),
}
