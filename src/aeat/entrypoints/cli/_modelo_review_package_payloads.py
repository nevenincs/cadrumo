"""Review-package build/verify CLI payload schemas.

Strict :class:`OutputSchema` subclasses registered through
:func:`register_schema` for the ``aeat app modelo review-package build`` and
``aeat app modelo review-package verify`` verbs. Kept in its own module
(mirroring the ``_modelo_aux_payloads`` split for the evidence-bundle audit
payloads) so the review-package CLI surface has one dedicated payload home.
"""

from __future__ import annotations

from ...core import Period
from ._schemas import OutputSchema, register_schema


@register_schema("modelo.review_package.build")
class ModeloReviewPackageBuildResult(OutputSchema):
    """Review-package build result (path reference only — no raw bytes in envelope)."""

    operation: str = "modelo.review_package.build"
    bucket_id: str
    work_unit_id: str
    calculation_revision_id: str
    modelo: str
    filing_year: int
    period: Period
    revision_state: str
    has_ledger_evidence: bool
    output_path: str
    member_count: int
    built_by: str
    built_at: str


@register_schema("modelo.review_package.verify")
class ModeloReviewPackageVerifyResult(OutputSchema):
    """Review-package integrity-verification result.

    ``is_clean`` summarises ``missing`` / ``unexpected`` / ``mismatched``
    (empty across all three iff clean). This is an INTEGRITY check only —
    it does not assert who built the package; cryptographic signing and
    counter-sign verification are a deferred follow-up slice.
    """

    operation: str = "modelo.review_package.verify"
    package_path: str
    is_clean: bool
    missing: list[str]
    unexpected: list[str]
    mismatched: list[str]
    bucket_id: str
    work_unit_id: str
    calculation_revision_id: str
    modelo: str
    filing_year: int
    period: Period
    revision_state: str
    has_ledger_evidence: bool
    built_by: str
    built_at: str


__all__ = [
    "ModeloReviewPackageBuildResult",
    "ModeloReviewPackageVerifyResult",
]
