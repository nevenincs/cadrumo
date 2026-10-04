"""Own finite fixture projections over real domain and storage kernels."""

from __future__ import annotations

from ..authority import PinnedAuthorityOperation
from ..authority_artifact import AuthorityEvidenceProjection
from ..ids import LegalRefId


def legal_quotation_is_grounded(self: PinnedAuthorityOperation, legal_ref_id: LegalRefId, quotation: str) -> bool:
    """Answer one citation query from this generation's published legal evidence."""
    evidence = self.legal_evidence(str(legal_ref_id))
    return AuthorityEvidenceProjection(legal=(evidence,)).quotation_is_grounded(str(legal_ref_id), quotation)
