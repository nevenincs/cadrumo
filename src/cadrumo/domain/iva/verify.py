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

from typing import TYPE_CHECKING

from ...core.citation_grounding import CitationGrounding
from ...core.errors.severity import BaseSeverity
from ...core.logging import get_logger
from ._grounding import registry_catalogues
from .schema import (
    IvaCatalogue,
    IvaCategory,
    IvaCitation,
    IvaVerificationIssue,
    IvaVerificationReport,
)

if TYPE_CHECKING:
    from collections.abc import Mapping

    from ..calculations.registry.ids import LegalRefId
    from ..calculations.registry.schema_references import LegalReference

_logger = get_logger(__name__)


def verify_catalogue(catalogue: IvaCatalogue) -> IvaVerificationReport:
    """Run every cross-record check on ``catalogue``.

    Args:
        catalogue: The :class:`cadrumo.domain.iva.IvaCatalogue` under audit.

    Returns:
        A :class:`cadrumo.domain.iva.IvaVerificationReport` aggregating every
        finding.
    """
    issues: list[IvaVerificationIssue] = []
    # The registry authority constructs every modelo and consumes IVA modules
    # while doing so.  Loading it here would therefore make a catalogue load
    # re-enter that construction path.  The IVA grounding helper is the
    # established cycle-safe access path for the parsed shared catalogues.
    legal, _sources, source_root = registry_catalogues()

    present = set(catalogue.regulations.keys())
    missing = [member for member in IvaCategory if member not in present]
    for member in missing:
        issues.append(
            IvaVerificationIssue(
                level=BaseSeverity.ERROR,
                code="missing_category",
                message=f"catalogue does not cover IvaCategory.{member.name}",
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
                    legal=legal,
                    source_root=source_root,
                ),
            )
    _logger.debug("verify_catalogue produced %d issue(s)", len(issues))
    return IvaVerificationReport(issues=tuple(issues))


def _citation_issues(
    citation: IvaCitation,
    *,
    category_id: str,
    legal: Mapping[LegalRefId, LegalReference],
    source_root: Path,
) -> list[IvaVerificationIssue]:
    """Run every registry and corpus check for one citation, in refusal order.

    Returns the findings rather than raising, because the catalogue audit reports
    every defect at once. A check that cannot resolve its reference stops this
    citation's remaining checks, which would otherwise report a second failure
    caused solely by the first.
    """
    from ..calculations.registry.legal import legal_reference_quotes_corpus, verify_legal_reference

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
    reference = legal.get(citation.legal_reference)
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
        verify_legal_reference(reference, source_root=source_root)
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
        quoted = legal_reference_quotes_corpus(
            reference,
            citation.quoted_text,
            source_root=source_root,
        )
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


__all__ = ["verify_catalogue"]
