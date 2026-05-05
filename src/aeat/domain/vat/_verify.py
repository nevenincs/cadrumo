"""Catalogue-level verification for :mod:`aeat.domain.vat`.

Runs cross-record checks on top of the per-model validation that pydantic
already performs:

* Every :class:`aeat.domain.vat.VATCategory` member must be present.
* Every regulation must carry at least one
  :class:`aeat.domain.vat.VatCitation`.
* Every citation must have non-empty
  :attr:`aeat.domain.vat.VatCitation.quoted_text`.
* Every ``boe_references`` id must match the kebab-case shape used by
  :mod:`aeat.domain.normatives`.
"""

from __future__ import annotations

import re

from ...core.logging import get_logger
from ._schema import (
    VATCatalogue,
    VATCategory,
    VatVerificationIssue,
    VatVerificationReport,
)

_logger = get_logger(__name__)

_NORMATIVE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def verify_catalogue(catalogue: VATCatalogue) -> VatVerificationReport:
    """Run every cross-record check on ``catalogue``.

    Args:
        catalogue: The :class:`aeat.domain.vat.VATCatalogue` under audit.

    Returns:
        A :class:`aeat.domain.vat.VatVerificationReport` aggregating every
        finding.
    """
    issues: list[VatVerificationIssue] = []

    present = set(catalogue.regulations.keys())
    missing = [member for member in VATCategory if member not in present]
    for member in missing:
        issues.append(
            VatVerificationIssue(
                level="error",
                code="missing_category",
                message=f"catalogue does not cover VATCategory.{member.name}",
                category_id=member.value,
            )
        )

    for regulation in catalogue:
        if not regulation.citations:
            issues.append(
                VatVerificationIssue(
                    level="error",
                    code="missing_citation",
                    message="regulation has no VatCitation records",
                    category_id=regulation.category.value,
                )
            )
        for citation in regulation.citations:
            if not citation.quoted_text.strip():
                issues.append(
                    VatVerificationIssue(
                        level="error",
                        code="empty_quoted_text",
                        message=f"citation {citation.article!r} has empty quoted_text",
                        category_id=regulation.category.value,
                    )
                )
        for ref in regulation.boe_references:
            if not _NORMATIVE_ID_PATTERN.fullmatch(ref):
                issues.append(
                    VatVerificationIssue(
                        level="error",
                        code="invalid_normative_id",
                        message=f"boe_reference {ref!r} is not a kebab-case normative id",
                        category_id=regulation.category.value,
                    )
                )
    _logger.debug("verify_catalogue produced %d issue(s)", len(issues))
    return VatVerificationReport(issues=tuple(issues))


__all__ = ["verify_catalogue"]
