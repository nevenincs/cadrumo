"""Canonical localized labels shared by Google review operator surfaces."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..core.external_constants import OutputLanguage
from ..core.i18n.render import MissingTranslationError, lookup_translation
from ..core.i18n.translatable import Translatable as tr

_GOOGLE_REVIEW_LOCALE_KEYS: Final[frozenset[tr]] = frozenset(
    {
        tr("google_review.field"),
        tr("google_review.value"),
        tr("google_review.offer.title"),
        tr("google_review.result.title"),
        tr("google_review.open_document"),
        tr("google_review.technical"),
        tr("google_review.cancel"),
        tr("google_review.publish"),
        tr("google_review.close"),
        tr("google_review.selection.ledger"),
        tr("google_review.destination.managed_google_folder"),
        tr("google_review.label.selection"),
        tr("google_review.label.review_status"),
        tr("google_review.label.amount_count"),
        tr("google_review.label.ledger_row_count"),
        tr("google_review.label.evidence_count"),
        tr("google_review.label.finding_count"),
        tr("google_review.label.destination"),
        tr("google_review.label.payload_categories"),
        tr("google_review.label.publication_state"),
        tr("google_review.label.snapshot_digest"),
        tr("google_review.label.work_unit_id"),
        tr("google_review.label.calculation_revision_id"),
        tr("google_review.label.registry_digest"),
        tr("google_review.label.ledger_snapshot_id"),
        tr("google_review.label.root_folder_id"),
        tr("google_review.label.publication_id"),
        tr("google_review.label.package_digest"),
        tr("google_review.status.provisional"),
        tr("google_review.status.verified"),
        tr("google_review.status.incomplete"),
        tr("google_review.notice.external_copy"),
        tr("google_review.notice.evidence_index"),
        tr("google_review.notice.provisional"),
        tr("google_review.notice.incomplete"),
        tr("google_review.notice.missing_evidence"),
        tr("google_review.notice.prerequisite_unavailable"),
        tr("google_review.notice.submission_unresolved"),
        tr("google_review.notice.receipt_unavailable"),
        tr("google_review.notice.calculation_required"),
        tr("google_review.notice.staged_edits"),
        tr("google_review.key"),
        tr("google_review.publication.prepared"),
        tr("google_review.publication.remote-created"),
        tr("google_review.publication.populated"),
        tr("google_review.publication.verified"),
        tr("google_review.publication.published"),
        tr("google_review.publication.partial"),
        tr("google_review.publication.uncertain"),
        tr("google_review.failure.admission"),
        tr("google_review.failure.create_unknown"),
        tr("google_review.failure.population"),
        tr("google_review.failure.integrity"),
        tr("google_review.failure.cancelled"),
        tr("google_review.failure.custody"),
        tr("google_review.category.calculation"),
        tr("google_review.category.ledger"),
        tr("google_review.category.original_attachment"),
        tr("google_review.category.evidence_package"),
    }
)


@dataclass(frozen=True, slots=True)
class GoogleReviewLabels:
    """Resolve required review wording in one locale without hidden untranslated fallback."""

    locale: OutputLanguage

    def __call__(self, key: str) -> str:
        """Resolve a declared frontend label or expose incomplete locale enrollment."""
        if key not in _GOOGLE_REVIEW_LOCALE_KEYS:
            raise KeyError(key)
        value = lookup_translation(key, locale=self.locale.value)
        if value is None or not value.strip() or value == key:
            raise MissingTranslationError(key=key, locale=self.locale.value)
        return value
