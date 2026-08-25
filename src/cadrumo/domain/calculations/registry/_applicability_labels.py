from __future__ import annotations

from .applicability_payer_facts import PayerFact

PAYER_FACT_INCOMPLETE_LABELS: dict[PayerFact, str] = {
    PayerFact.PAYS_WITHHELD_INCOME: "paga retribuciones sujetas a retención",
    PayerFact.PAYS_RENT_WITH_RETENCION: "paga alquileres sujetos a retención",
    PayerFact.TRADES_INTRACOMMUNITY: "realiza operaciones intracomunitarias",
    PayerFact.EXCEEDS_THIRD_PARTY_THRESHOLD: "supera el umbral anual de operaciones con terceras personas",
    PayerFact.BIENES_EXTRANJERO_ABOVE_THRESHOLD: "posee bienes o derechos en el extranjero por encima del umbral",
    PayerFact.MONEDAS_VIRTUALES_EXTRANJERO_ABOVE_THRESHOLD: (
        "posee monedas virtuales situadas en el extranjero por encima del umbral"
    ),
    PayerFact.PAYS_CAPITAL_INCOME_WITH_RETENCION: ("paga rendimientos del capital mobiliario sujetos a retención"),
    PayerFact.IVA_GROUP_MEMBER: "esta inscrito como entidad miembro de un grupo de IVA",
    PayerFact.IVA_GROUP_DOMINANT_ENTITY: "esta inscrito como entidad dominante de un grupo de IVA",
    PayerFact.OSS_ENROLLED: "esta inscrito en un regimen de ventanilla unica (OSS/IOSS) del IVA",
}
