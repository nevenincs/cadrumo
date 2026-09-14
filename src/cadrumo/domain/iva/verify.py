"""Canonical catalogue-level verification for :mod:`cadrumo.domain.iva`.

Runs cross-record checks on top of the per-model validation that pydantic
already performs:

* Every :class:`cadrumo.domain.iva.IvaCategory` member must be present.
* Every regulation must carry at least one
  :class:`cadrumo.domain.iva.IvaCitation`, unless it declares
  ``legal_basis_exempt`` (a classifier sentinel with no tax treatment).
* Every citation identity must resolve to a verified, article-qualified
  registry legal reference with bundled corpus evidence.
* Every citation claiming verified grounding must carry a quotation that
  actually occurs in that reference's bundled corpus text. Non-emptiness was
  the prior check and is not grounding: it passes for any string at all.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import TYPE_CHECKING

from ...core.citation_grounding import CitationGrounding
from ...core.corpus_text import normalise_corpus_text
from ...core.errors.severity import BaseSeverity
from ...core.logging import get_logger
from ..calculations.registry.iva_category_catalogue import resolve_iva_category_catalogue
from .errors import IvaCatalogueError
from .schema import (
    IvaCatalogue,
    IvaCitation,
    IvaVerificationIssue,
    IvaVerificationReport,
)

_logger = get_logger(__name__)

if TYPE_CHECKING:
    from ..calculations.registry.authority import PinnedAuthorityOperation
    from ..calculations.registry.governed_fact_scope import GovernedFactSource
    from ..calculations.registry.schema_references import LegalReference


def verify_catalogue_against_legal(
    catalogue: IvaCatalogue,
    *,
    authority: GovernedFactSource | None = None,
    operation: PinnedAuthorityOperation | None = None,
    legal: Mapping[str, LegalReference] | None = None,
) -> IvaVerificationReport:
    """Verify one catalogue against signed, published legal evidence."""
    if authority is not None and operation is not None:
        raise TypeError("IVA catalogue verification accepts either authority or operation, not both")
    if operation is not None:
        selected = operation
    elif authority is not None:
        selected = authority
    else:
        raise IvaCatalogueError("IVA catalogue verification requires an explicit operation or governed source")
    issues: list[IvaVerificationIssue] = []
    present = set(catalogue.regulations.keys())
    declared_categories = resolve_iva_category_catalogue(
        effective_date=date.today(),
        authority=selected,
    ).all_categories
    missing = [member for member in declared_categories if member not in present]
    for member in missing:
        issues.append(
            IvaVerificationIssue(
                level=BaseSeverity.ERROR,
                code="missing_category",
                message=f"catalogue does not cover IVA category {member.value}",
                category_id=member.value,
            ),
        )

    for regulation in catalogue:
        if not regulation.citations and not regulation.legal_basis_exempt:
            issues.append(
                IvaVerificationIssue(
                    level=BaseSeverity.ERROR,
                    code="missing_citation",
                    message="regulation has no IvaCitation records",
                    category_id=regulation.category.value,
                ),
            )
        for citation in regulation.citations:
            issues.extend(
                _citation_issues(
                    citation,
                    category_id=regulation.category.value,
                    authority=selected,
                    operation=operation,
                    legal=legal,
                ),
            )
    _logger.debug("verify_catalogue_against_legal produced %d issue(s)", len(issues))
    return IvaVerificationReport(issues=tuple(issues))


def _citation_issues(
    citation: IvaCitation,
    *,
    category_id: str,
    authority: GovernedFactSource,
    operation: PinnedAuthorityOperation | None = None,
    legal: Mapping[str, LegalReference] | None = None,
) -> list[IvaVerificationIssue]:
    """Run every registry and corpus check for one citation, in refusal order.

    Returns the findings rather than raising, because the catalogue audit reports
    every defect at once. A check that cannot resolve its reference stops this
    citation's remaining checks, which would otherwise report a second failure
    caused solely by the first.
    """
    issues: list[IvaVerificationIssue] = []
    # An UNRESOLVED citation is empty by design: it was read against
    # the corpus and refused, and its reason is recorded beside it.
    # Flagging it here would erase the distinction between a citation
    # nobody checked and one that failed the check.
    if citation.grounding is CitationGrounding.VERIFIED and not citation.quoted_text.strip():
        issues.append(
            IvaVerificationIssue(
                level=BaseSeverity.ERROR,
                code="empty_quoted_text",
                message=f"citation {citation.legal_reference!r} claims verified grounding with no quotation",
                category_id=category_id,
            ),
        )
    if legal is None:
        if operation is None:
            legal = authority.catalogues.legal  # type: ignore[attr-defined]
        else:
            try:
                reference = operation.legal_reference(citation.legal_reference)
            except Exception as exc:
                issues.append(
                    IvaVerificationIssue(
                        level=BaseSeverity.ERROR,
                        code="unknown_legal_reference",
                        message=(
                            f"citation legal_reference {citation.legal_reference!r} is absent from the registry "
                            f"legal catalogue: {exc}"
                        ),
                        category_id=category_id,
                    ),
                )
                return issues
    reference = legal.get(citation.legal_reference) if legal is not None else reference
    if reference is None:
        issues.append(
            IvaVerificationIssue(
                level=BaseSeverity.ERROR,
                code="unknown_legal_reference",
                message=(
                    f"citation legal_reference {citation.legal_reference!r} is absent from the registry legal catalogue"
                ),
                category_id=category_id,
            ),
        )
        return issues
    if reference.article is None:
        issues.append(
            IvaVerificationIssue(
                level=BaseSeverity.ERROR,
                code="legal_reference_not_article_qualified",
                message=f"citation legal_reference {citation.legal_reference!r} has no registry article",
                category_id=category_id,
            ),
        )
        return issues
    try:
        if operation is None:
            authority.legal_evidence_text(citation.legal_reference)  # type: ignore[attr-defined]
        else:
            operation.legal_evidence(citation.legal_reference)
    except Exception as exc:
        issues.append(
            IvaVerificationIssue(
                level=BaseSeverity.ERROR,
                code="legal_reference_unverified",
                message=(f"citation legal_reference {citation.legal_reference!r} has invalid corpus evidence: {exc}"),
                category_id=category_id,
            ),
        )
        return issues
    # A non-empty quotation is not yet grounding. This reads the stored
    # text back against the bundled corpus, which is the only check that
    # separates a transcription from an assertion about one.
    if citation.grounding is not CitationGrounding.VERIFIED:
        return issues
    try:
        if operation is None:
            anchored_text = authority.legal_evidence_text(citation.legal_reference)  # type: ignore[attr-defined]
        else:
            anchored_text = operation.legal_evidence(citation.legal_reference).anchored_text
        quoted = normalise_corpus_text(citation.quoted_text) in normalise_corpus_text(anchored_text)
    except Exception as exc:
        issues.append(
            IvaVerificationIssue(
                level=BaseSeverity.ERROR,
                code="quotation_uncheckable",
                message=(
                    f"citation {citation.legal_reference!r} quotation could not be read "
                    f"against the bundled corpus: {exc}"
                ),
                category_id=category_id,
            ),
        )
        return issues
    if not quoted:
        issues.append(
            IvaVerificationIssue(
                level=BaseSeverity.ERROR,
                code="quotation_absent_from_corpus",
                message=(
                    f"citation {citation.legal_reference!r} claims verified grounding, but its "
                    "quotation does not occur in the bundled corpus text for that reference"
                ),
                category_id=category_id,
            ),
        )
    return issues


__all__ = ["verify_catalogue_against_legal"]
