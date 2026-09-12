"""Runtime legal-reference eligibility checks.

The authority artifact carries immutable, already-published legal evidence.
Corpus extraction, textual-grounding and provenance verification are publisher
responsibilities in :mod:`dev.registry.compiler.legal_grounding`; runtime only
checks whether the artifact's selected citation is eligible for filing.
"""

from __future__ import annotations

from ....core.revision_review import REVIEWED_REVISION_REVIEW_STATUSES
from .citation_blocklist import find_known_bad
from .errors import RegistryValidationError
from .schema_references import LegalReference


def verify_legal_reference(reference: LegalReference) -> None:
    """Reject an artifact citation that is not eligible for filing.

    This deliberately does not open ``corpus_ref``. Publication has already
    established corpus provenance and textual grounding; installed runtime has
    no mutable authoring tree to verify or rebuild from.
    """
    if reference.review_status not in REVIEWED_REVISION_REVIEW_STATUSES:
        raise RegistryValidationError(
            f"legal reference {reference.id!r} is {reference.review_status.value!r}; "
            "filing-grade authority requires a reviewed status",
        )
    _validate_known_bad_citation(reference)


def _validate_known_bad_citation(reference: LegalReference) -> None:
    if reference.article is None:
        return
    from .setup_profile_bindings import legal_source_kind_declarations

    source = legal_source_kind_declarations().get(str(reference.kind))
    if source is None:
        return
    role_text = " ".join(part for part in (reference.section, reference.notes) if part)
    if role_text and (
        known_bad := find_known_bad(
            source,
            reference.article,
            role_text,
            effective_date=reference.effective_from,
        )
    ):
        raise RegistryValidationError(
            f"legal reference {reference.id!r} matches known-bad citation: {known_bad.reason}",
        )
