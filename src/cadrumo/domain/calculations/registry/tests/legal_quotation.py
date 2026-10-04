"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from .....core.corpus_text import normalise_corpus_text
from ..authority import PinnedAuthorityOperation
from ..authority_artifact import AuthorityEvidenceProjection
from ..ids import LegalRefId


def legal_quotation_is_grounded(self: PinnedAuthorityOperation, legal_ref_id: LegalRefId, quotation: str) -> bool:
    """Answer one citation query from this generation's published legal evidence."""
    evidence = self.legal_evidence(str(legal_ref_id))
    projection = AuthorityEvidenceProjection(legal=(evidence,))
    return bool(quotation.strip()) and normalise_corpus_text(quotation) in projection.legal_text(str(legal_ref_id))
