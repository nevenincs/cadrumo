"""Catalogue-level verification for :mod:`cadrumo.domain.iva`.

Runs cross-record checks on top of the per-model validation that pydantic
already performs:

* Every :class:`cadrumo.domain.iva.IvaCategory` member must be present.
* Every regulation must carry at least one
  :class:`cadrumo.domain.iva.IvaCitation`.
* Every citation must have non-empty
  :attr:`cadrumo.domain.iva.IvaCitation.quoted_text`.
* Every citation identity must resolve to a verified, article-qualified
  registry legal reference with bundled corpus evidence.
"""

from __future__ import annotations

from ...core.logging import get_logger
from ._schema import (
    IvaCatalogue,
    IvaCategory,
    IvaVerificationIssue,
    IvaVerificationReport,
)

_logger = get_logger(__name__)

def verify_catalogue(catalogue: IvaCatalogue) -> IvaVerificationReport:
    """Run every cross-record check on ``catalogue``.

    Args:
        catalogue: The :class:`cadrumo.domain.iva.IvaCatalogue` under audit.

    Returns:
        A :class:`cadrumo.domain.iva.IvaVerificationReport` aggregating every
        finding.
    """
    # Keep this local: registry binding modules consume the IVA public facade.
    from ...core.resources import bundled_path
    from ..calculations.registry import bundled_authority, verify_legal_reference

    issues: list[IvaVerificationIssue] = []
    legal = bundled_authority().catalogues.legal

    present = set(catalogue.regulations.keys())
    missing = [member for member in IvaCategory if member not in present]
    for member in missing:
        issues.append(
            IvaVerificationIssue(
                level="error",
                code="missing_category",
                message=f"catalogue does not cover IvaCategory.{member.name}",
                category_id=member.value,
            ),
        )

    for regulation in catalogue:
        if not regulation.citations:
            issues.append(
                IvaVerificationIssue(
                    level="error",
                    code="missing_citation",
                    message="regulation has no IvaCitation records",
                    category_id=regulation.category.value,
                ),
            )
        for citation in regulation.citations:
            if not citation.quoted_text.strip():
                issues.append(
                    IvaVerificationIssue(
                        level="error",
                        code="empty_quoted_text",
                        message=f"citation {citation.article!r} has empty quoted_text",
                        category_id=regulation.category.value,
                    ),
                )
            reference = legal.get(citation.legal_reference)
            if reference is None:
                issues.append(
                    IvaVerificationIssue(
                        level="error",
                        code="unknown_legal_reference",
                        message=(
                            f"citation legal_reference {citation.legal_reference!r} "
                            "is absent from the registry legal catalogue"
                        ),
                        category_id=regulation.category.value,
                    ),
                )
                continue
            if reference.article is None:
                issues.append(
                    IvaVerificationIssue(
                        level="error",
                        code="legal_reference_not_article_qualified",
                        message=f"citation legal_reference {citation.legal_reference!r} has no registry article",
                        category_id=regulation.category.value,
                    ),
                )
                continue
            try:
                verify_legal_reference(reference, source_root=bundled_path())
            except Exception as exc:
                issues.append(
                    IvaVerificationIssue(
                        level="error",
                        code="legal_reference_unverified",
                        message=(
                            f"citation legal_reference {citation.legal_reference!r} "
                            f"has invalid corpus evidence: {exc}"
                        ),
                        category_id=regulation.category.value,
                    ),
                )
    _logger.debug("verify_catalogue produced %d issue(s)", len(issues))
    return IvaVerificationReport(issues=tuple(issues))


__all__ = ["verify_catalogue"]
