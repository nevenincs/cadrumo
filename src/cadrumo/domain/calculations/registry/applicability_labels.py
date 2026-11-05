from __future__ import annotations

from ....core.i18n.render import tr
from .applicability_payer_facts import PayerFact, PayerFactProjection, PayerFactValue

PAYER_FACT_INCOMPLETE_LABEL_LOCALE_KEYS: dict[PayerFact, str] = {
    PayerFact.PAYS_WITHHELD_INCOME: "filing.applicability.payer_fact.pays_withheld_income",
    PayerFact.PAYS_RENT_WITH_RETENCION: "filing.applicability.payer_fact.pays_rent_with_retencion",
    PayerFact.TRADES_INTRACOMMUNITY: "filing.applicability.payer_fact.trades_intracommunity",
    PayerFact.IVA_GROUP_MEMBER: "filing.applicability.payer_fact.iva_group_member",
    PayerFact.IVA_GROUP_DOMINANT_ENTITY: "filing.applicability.payer_fact.iva_group_dominant_entity",
    PayerFact.OSS_ENROLLED: "filing.applicability.payer_fact.oss_enrolled",
}
"""Catalogue keys for the retained mechanics facts, one per enum member.

These labels are named inside an ``INCOMPLETE`` rationale the operator reads
through ``overview explain`` and ``overview calendar``, so they render in the
active output language. They were authored Spanish strings, which put a Spanish
clause inside an otherwise English sentence.

A :class:`PayerFactProjection` carries registry-authored text instead, and that
stays as authored: the dated catalogue owns its own wording.
"""


def payer_fact_incomplete_label(fact: PayerFactValue) -> str:
    """Return the registry-owned label or the rendered mechanics label."""
    if isinstance(fact, PayerFactProjection):
        return fact.label
    return tr(PAYER_FACT_INCOMPLETE_LABEL_LOCALE_KEYS[fact])
