"""Localized labels for saved reconciliation workbook reviews."""

from __future__ import annotations

from dataclasses import dataclass

from ...core.external_constants import OutputLanguage
from ...core.i18n.render import MissingTranslationError, lookup_translation
from ...core.i18n.translatable import Translatable as tr

_LABELS = {
    "record_identity": tr("application.reconciliation_export.record_identity"),
    "verdict_matches": tr("application.reconciliation_export.verdict_matches"),
    "verdict_mismatches": tr("application.reconciliation_export.verdict_mismatches"),
    "evidence_kind_justificante": tr("application.reconciliation_export.evidence_kind_justificante"),
    "evidence_kind_declaration": tr("application.reconciliation_export.evidence_kind_declaration"),
    "difference_kind_header_field": tr("application.reconciliation_export.difference_kind_header_field"),
    "difference_kind_total": tr("application.reconciliation_export.difference_kind_total"),
    "difference_kind_casilla": tr("application.reconciliation_export.difference_kind_casilla"),
    "title": tr("application.reconciliation_export.title"),
    "saved_comparison_notice": tr("application.reconciliation_export.saved_comparison_notice"),
    "record": tr("application.reconciliation_export.record"),
    "date": tr("application.reconciliation_export.date"),
    "verdict": tr("application.reconciliation_export.verdict"),
    "modelo": tr("application.reconciliation_export.modelo"),
    "year": tr("application.reconciliation_export.year"),
    "period": tr("application.reconciliation_export.period"),
    "registry_revision": tr("application.reconciliation_export.registry_revision"),
    "work_unit": tr("application.reconciliation_export.work_unit"),
    "calculation_revision": tr("application.reconciliation_export.calculation_revision"),
    "evidence_kind": tr("application.reconciliation_export.evidence_kind"),
    "evidence_reference": tr("application.reconciliation_export.evidence_reference"),
    "actor": tr("application.reconciliation_export.actor"),
    "difference_count": tr("application.reconciliation_export.difference_count"),
    "advisory_count": tr("application.reconciliation_export.advisory_count"),
    "difference_kind": tr("application.reconciliation_export.difference_kind"),
    "field": tr("application.reconciliation_export.field"),
    "saved_value": tr("application.reconciliation_export.saved_value"),
    "evidence_value": tr("application.reconciliation_export.evidence_value"),
    "difference_reason": tr("application.reconciliation_export.difference_reason"),
    "legal_refs": tr("application.reconciliation_export.legal_refs"),
    "source_refs": tr("application.reconciliation_export.source_refs"),
    "advisory_code": tr("application.reconciliation_export.advisory_code"),
    "advisory": tr("application.reconciliation_export.advisory"),
    "context": tr("application.reconciliation_export.context"),
}


@dataclass(frozen=True, slots=True)
class ReconciliationWorkbookLabels:
    """Resolve required workbook copy without key echo or locale fallback."""

    locale: OutputLanguage

    def __call__(self, key: str) -> str:
        """Return one localized label."""
        translation_key = _LABELS[key]
        value = lookup_translation(translation_key, locale=self.locale.value)
        if value is None or not value.strip():
            raise MissingTranslationError(key=translation_key, locale=self.locale.value)
        return value
