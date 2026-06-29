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
}
