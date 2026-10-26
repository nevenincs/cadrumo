"""Resolve workbook review copy through the canonical locale catalogue."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ....core.external_constants import OutputLanguage
from ....core.i18n.render import MissingTranslationError, lookup_translation
from ....core.i18n.translatable import Translatable as tr

_REVIEW_LABEL_KEYS: Final[dict[str, tr]] = {
    "overview": tr("application.storage.calc_sheets.review.labels.overview"),
    "baseline_notice": tr("application.storage.calc_sheets.review.labels.baseline_notice"),
    "index_only_notice": tr("application.storage.calc_sheets.review.labels.index_only_notice"),
    "external_notes_notice": tr("application.storage.calc_sheets.review.labels.external_notes_notice"),
    "ledger_notice": tr("application.storage.calc_sheets.review.labels.ledger_notice"),
    "ledger_scope_notice": tr("application.storage.calc_sheets.review.labels.ledger_scope_notice"),
    "attribution_notice": tr("application.storage.calc_sheets.review.labels.attribution_notice"),
    "unattributed": tr("application.storage.calc_sheets.review.labels.unattributed"),
    "not_captured": tr("application.storage.calc_sheets.review.labels.not_captured"),
    "not_captured_notice": tr("application.storage.calc_sheets.review.labels.not_captured_notice"),
    "no_captured_rows": tr("application.storage.calc_sheets.review.labels.no_captured_rows"),
    "not_ledger_source": tr("application.storage.calc_sheets.review.labels.not_ledger_source"),
    "no_inventory_reference": tr("application.storage.calc_sheets.review.labels.no_inventory_reference"),
    "exact_decimal_notice": tr("application.storage.calc_sheets.review.labels.exact_decimal_notice"),
    "status": tr("application.storage.calc_sheets.review.labels.status"),
    "calculation_state": tr("application.storage.calc_sheets.review.labels.calculation_state"),
    "current_calculation": tr("application.storage.calc_sheets.review.labels.current_calculation"),
    "current_filing": tr("application.storage.calc_sheets.review.labels.current_filing"),
    "filing_status": tr("application.storage.calc_sheets.review.labels.filing_status"),
    "filing_record": tr("application.storage.calc_sheets.review.labels.filing_record"),
    "filing_status_vigente": tr("application.storage.calc_sheets.review.labels.filing_status_vigente"),
    "filing_status_supersedido": tr("application.storage.calc_sheets.review.labels.filing_status_supersedido"),
    "aeat_confirmation": tr("application.storage.calc_sheets.review.labels.aeat_confirmation"),
    "yes": tr("application.storage.calc_sheets.review.labels.yes"),
    "no": tr("application.storage.calc_sheets.review.labels.no"),
    "calculation_state_borrador": tr("application.storage.calc_sheets.review.labels.calculation_state_borrador"),
    "calculation_state_verificado_completo": tr(
        "application.storage.calc_sheets.review.labels.calculation_state_verificado_completo"
    ),
    "calculation_state_presentado": tr("application.storage.calc_sheets.review.labels.calculation_state_presentado"),
    "calculation_state_presentado_supersedido": tr(
        "application.storage.calc_sheets.review.labels.calculation_state_presentado_supersedido"
    ),
    "calculation_state_descartado": tr("application.storage.calc_sheets.review.labels.calculation_state_descartado"),
    "aeat_confirmation_pendiente": tr("application.storage.calc_sheets.review.labels.aeat_confirmation_pendiente"),
    "aeat_confirmation_confirmada": tr("application.storage.calc_sheets.review.labels.aeat_confirmation_confirmada"),
    "aeat_confirmation_discrepante": tr("application.storage.calc_sheets.review.labels.aeat_confirmation_discrepante"),
    "aeat_confirmation_descartada": tr("application.storage.calc_sheets.review.labels.aeat_confirmation_descartada"),
    "review_quality": tr("application.storage.calc_sheets.review.labels.review_quality"),
    "status_provisional": tr("application.storage.calc_sheets.review.labels.status_provisional"),
    "status_verified": tr("application.storage.calc_sheets.review.labels.status_verified"),
    "status_incomplete": tr("application.storage.calc_sheets.review.labels.status_incomplete"),
    "snapshot": tr("application.storage.calc_sheets.review.labels.snapshot"),
    "publication": tr("application.storage.calc_sheets.review.labels.publication"),
    "exported_at": tr("application.storage.calc_sheets.review.labels.exported_at"),
    "evidence_scope": tr("application.storage.calc_sheets.review.labels.evidence_scope"),
    "numeric_notice": tr("application.storage.calc_sheets.review.labels.numeric_notice"),
    "missing_data": tr("application.storage.calc_sheets.review.labels.missing_data"),
    "modelo": tr("application.storage.calc_sheets.review.labels.modelo"),
    "period": tr("application.storage.calc_sheets.review.labels.period"),
    "work_unit": tr("application.storage.calc_sheets.review.labels.work_unit"),
    "calculation_revision": tr("application.storage.calc_sheets.review.labels.calculation_revision"),
    "registry_revision": tr("application.storage.calc_sheets.review.labels.registry_revision"),
    "authority": tr("application.storage.calc_sheets.review.labels.authority"),
    "registry_digest": tr("application.storage.calc_sheets.review.labels.registry_digest"),
    "ledger_snapshot": tr("application.storage.calc_sheets.review.labels.ledger_snapshot"),
    "scope": tr("application.storage.calc_sheets.review.labels.scope"),
    "finding": tr("application.storage.calc_sheets.review.labels.finding"),
    "ledger": tr("application.storage.calc_sheets.review.labels.ledger"),
    "sources": tr("application.storage.calc_sheets.review.labels.sources"),
    "evidence": tr("application.storage.calc_sheets.review.labels.evidence"),
    "review": tr("application.storage.calc_sheets.review.labels.review"),
    "results": tr("application.storage.calc_sheets.review.labels.results"),
    "field": tr("application.storage.calc_sheets.review.labels.field"),
    "value": tr("application.storage.calc_sheets.review.labels.value"),
    "result_count": tr("application.storage.calc_sheets.review.labels.result_count"),
    "ledger_row_count": tr("application.storage.calc_sheets.review.labels.ledger_row_count"),
    "contribution_count": tr("application.storage.calc_sheets.review.labels.contribution_count"),
    "evidence_count": tr("application.storage.calc_sheets.review.labels.evidence_count"),
    "finding_count": tr("application.storage.calc_sheets.review.labels.finding_count"),
    "amount_id": tr("application.storage.calc_sheets.review.labels.amount_id"),
    "casilla": tr("application.storage.calc_sheets.review.labels.casilla"),
    "row_id": tr("application.storage.calc_sheets.review.labels.row_id"),
    "exact_value": tr("application.storage.calc_sheets.review.labels.exact_value"),
    "unit": tr("application.storage.calc_sheets.review.labels.unit"),
    "currency": tr("application.storage.calc_sheets.review.labels.currency"),
    "rounding": tr("application.storage.calc_sheets.review.labels.rounding"),
    "formula": tr("application.storage.calc_sheets.review.labels.formula"),
    "legal_refs": tr("application.storage.calc_sheets.review.labels.legal_refs"),
    "source_refs": tr("application.storage.calc_sheets.review.labels.source_refs"),
    "transaction": tr("application.storage.calc_sheets.review.labels.transaction"),
    "booked_date": tr("application.storage.calc_sheets.review.labels.booked_date"),
    "value_date": tr("application.storage.calc_sheets.review.labels.value_date"),
    "direction": tr("application.storage.calc_sheets.review.labels.direction"),
    "amount": tr("application.storage.calc_sheets.review.labels.amount"),
    "eur_value": tr("application.storage.calc_sheets.review.labels.eur_value"),
    "classification": tr("application.storage.calc_sheets.review.labels.classification"),
    "taxable_base": tr("application.storage.calc_sheets.review.labels.taxable_base"),
    "iva_amount": tr("application.storage.calc_sheets.review.labels.iva_amount"),
    "counterparty": tr("application.storage.calc_sheets.review.labels.counterparty"),
    "invoice": tr("application.storage.calc_sheets.review.labels.invoice"),
    "digest": tr("application.storage.calc_sheets.review.labels.digest"),
    "attachments": tr("application.storage.calc_sheets.review.labels.attachments"),
    "document_links": tr("application.storage.calc_sheets.review.labels.document_links"),
    "fx_rate": tr("application.storage.calc_sheets.review.labels.fx_rate"),
    "business_pct": tr("application.storage.calc_sheets.review.labels.business_pct"),
    "iva_rate": tr("application.storage.calc_sheets.review.labels.iva_rate"),
    "recargo_amount": tr("application.storage.calc_sheets.review.labels.recargo_amount"),
    "iva_category": tr("application.storage.calc_sheets.review.labels.iva_category"),
    "irpf_category": tr("application.storage.calc_sheets.review.labels.irpf_category"),
    "purchase_invoice_evidence": tr("application.storage.calc_sheets.review.labels.purchase_invoice_evidence"),
    "exact_amount": tr("application.storage.calc_sheets.review.labels.exact_amount"),
    "lifecycle_state": tr("application.storage.calc_sheets.review.labels.lifecycle_state"),
    "description": tr("application.storage.calc_sheets.review.labels.description"),
    "usage_ratio_id": tr("application.storage.calc_sheets.review.labels.usage_ratio_id"),
    "deduction_fact_kind": tr("application.storage.calc_sheets.review.labels.deduction_fact_kind"),
    "art_104_tres_exclusion": tr("application.storage.calc_sheets.review.labels.art_104_tres_exclusion"),
    "input_classification": tr("application.storage.calc_sheets.review.labels.input_classification"),
    "prorrata_sector_id": tr("application.storage.calc_sheets.review.labels.prorrata_sector_id"),
    "prorrata_reference": tr("application.storage.calc_sheets.review.labels.prorrata_reference"),
    "category_id": tr("application.storage.calc_sheets.review.labels.category_id"),
    "source_jurisdiction": tr("application.storage.calc_sheets.review.labels.source_jurisdiction"),
    "m210_official_tipo_renta_code": tr("application.storage.calc_sheets.review.labels.m210_official_tipo_renta_code"),
    "m210_gross_income_amount": tr("application.storage.calc_sheets.review.labels.m210_gross_income_amount"),
    "m210_applicable_rate": tr("application.storage.calc_sheets.review.labels.m210_applicable_rate"),
    "m210_payer_mode": tr("application.storage.calc_sheets.review.labels.m210_payer_mode"),
    "m210_payer_id": tr("application.storage.calc_sheets.review.labels.m210_payer_id"),
    "m210_asset_or_right_id": tr("application.storage.calc_sheets.review.labels.m210_asset_or_right_id"),
    "counterparty_country": tr("application.storage.calc_sheets.review.labels.counterparty_country"),
    "exact_eur_value": tr("application.storage.calc_sheets.review.labels.exact_eur_value"),
    "exact_taxable_base": tr("application.storage.calc_sheets.review.labels.exact_taxable_base"),
    "exact_iva_amount": tr("application.storage.calc_sheets.review.labels.exact_iva_amount"),
    "exact_fx_rate": tr("application.storage.calc_sheets.review.labels.exact_fx_rate"),
    "exact_business_pct": tr("application.storage.calc_sheets.review.labels.exact_business_pct"),
    "exact_iva_rate": tr("application.storage.calc_sheets.review.labels.exact_iva_rate"),
    "exact_recargo_amount": tr("application.storage.calc_sheets.review.labels.exact_recargo_amount"),
    "exact_m210_gross_income_amount": tr(
        "application.storage.calc_sheets.review.labels.exact_m210_gross_income_amount"
    ),
    "exact_m210_applicable_rate": tr("application.storage.calc_sheets.review.labels.exact_m210_applicable_rate"),
    "contribution": tr("application.storage.calc_sheets.review.labels.contribution"),
    "kind": tr("application.storage.calc_sheets.review.labels.kind"),
    "source_id": tr("application.storage.calc_sheets.review.labels.source_id"),
    "source_revision": tr("application.storage.calc_sheets.review.labels.source_revision"),
    "detail": tr("application.storage.calc_sheets.review.labels.detail"),
    "source_kind": tr("application.storage.calc_sheets.review.labels.source_kind"),
    "source_kind_ledger_row": tr("application.storage.calc_sheets.review.labels.source_kind_ledger_row"),
    "source_kind_invoice": tr("application.storage.calc_sheets.review.labels.source_kind_invoice"),
    "source_kind_manual_input": tr("application.storage.calc_sheets.review.labels.source_kind_manual_input"),
    "source_kind_adjustment": tr("application.storage.calc_sheets.review.labels.source_kind_adjustment"),
    "source_kind_unavailable": tr("application.storage.calc_sheets.review.labels.source_kind_unavailable"),
    "evidence_id": tr("application.storage.calc_sheets.review.labels.evidence_id"),
    "disposition": tr("application.storage.calc_sheets.review.labels.disposition"),
    "media_type": tr("application.storage.calc_sheets.review.labels.media_type"),
    "byte_length": tr("application.storage.calc_sheets.review.labels.byte_length"),
    "reason": tr("application.storage.calc_sheets.review.labels.reason"),
    "availability": tr("application.storage.calc_sheets.review.labels.availability"),
    "evidence_included": tr("application.storage.calc_sheets.review.labels.evidence_included"),
    "evidence_excluded": tr("application.storage.calc_sheets.review.labels.evidence_excluded"),
    "evidence_missing": tr("application.storage.calc_sheets.review.labels.evidence_missing"),
    "evidence_unavailable": tr("application.storage.calc_sheets.review.labels.evidence_unavailable"),
    "reference": tr("application.storage.calc_sheets.review.labels.reference"),
    "scenario": tr("application.storage.calc_sheets.review.labels.scenario"),
    "reviewer": tr("application.storage.calc_sheets.review.labels.reviewer"),
    "review_date": tr("application.storage.calc_sheets.review.labels.review_date"),
    "review_status": tr("application.storage.calc_sheets.review.labels.review_status"),
}


@dataclass(frozen=True, slots=True)
class ReviewWorkbookLabels:
    """Bind a review to one language and refuse untranslated required copy.

    Keys are statically enrolled for every supported locale. No fixture wording,
    key humanisation or Spanish fallback can hide an unfinished catalogue.
    """

    locale: OutputLanguage

    def __call__(self, key: str) -> str:
        """Resolve one semantic renderer label through the owning catalogue."""
        translation_key = _REVIEW_LABEL_KEYS[key]
        value = lookup_translation(translation_key, locale=self.locale.value)
        if value is None or not value.strip():
            raise MissingTranslationError(key=translation_key, locale=self.locale.value)
        return value
