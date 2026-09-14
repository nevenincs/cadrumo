from __future__ import annotations

from .applicability_payer_facts import PayerFact, PayerFactProjection, PayerFactValue

PAYER_FACT_INCOMPLETE_LABELS: dict[PayerFact, str] = {
    PayerFact.PAYS_WITHHELD_INCOME: "paga retribuciones sujetas a retención",
    PayerFact.PAYS_RENT_WITH_RETENCION: "paga alquileres sujetos a retención",
    PayerFact.TRADES_INTRACOMMUNITY: "realiza operaciones intracomunitarias",
    PayerFact.IVA_GROUP_MEMBER: "esta inscrito como entidad miembro de un grupo de IVA",
    PayerFact.IVA_GROUP_DOMINANT_ENTITY: "esta inscrito como entidad dominante de un grupo de IVA",
    PayerFact.OSS_ENROLLED: "esta inscrito en un regimen de ventanilla unica (OSS/IOSS) del IVA",
}


def payer_fact_incomplete_label(fact: PayerFactValue) -> str:
    """Return the registry-owned label or retained mechanics label."""
    if isinstance(fact, PayerFactProjection):
        return fact.label
    return PAYER_FACT_INCOMPLETE_LABELS[fact]
