"""Catalogue-level verification for :mod:`aeat.domain.iva`.

Runs cross-record checks on top of the per-model validation that pydantic
already performs:

* Every :class:`aeat.domain.iva.IvaCategory` member must be present.
* Every regulation must carry at least one
  :class:`aeat.domain.iva.IvaCitation`.
* Every citation must have non-empty
  :attr:`aeat.domain.iva.IvaCitation.quoted_text`.
* Every ``boe_references`` id must match the kebab-case document-id
  shape used by the registry legal catalogue.
"""

from __future__ import annotations

import re

from ...core.logging import get_logger
from ._schema import (
    IvaCatalogue,
    IvaCategory,
    IvaVerificationIssue,
    IvaVerificationReport,
)

_logger = get_logger(__name__)

_NORMATIVE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def verify_catalogue(catalogue: IvaCatalogue) -> IvaVerificationReport:
    """Run every cross-record check on ``catalogue``.

    Args:
        catalogue: The :class:`aeat.domain.iva.IvaCatalogue` under audit.

    Returns:
        A :class:`aeat.domain.iva.IvaVerificationReport` aggregating every
        finding.
    """
    issues: list[IvaVerificationIssue] = []

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
        for ref in regulation.boe_references:
            if not _NORMATIVE_ID_PATTERN.fullmatch(ref):
                issues.append(
                    IvaVerificationIssue(
                        level="error",
                        code="invalid_legal_reference_id",
                        message=f"boe_reference {ref!r} is not a kebab-case legal reference id",
                        category_id=regulation.category.value,
                    ),
                )
    _logger.debug("verify_catalogue produced %d issue(s)", len(issues))
    return IvaVerificationReport(issues=tuple(issues))


__all__ = ["verify_catalogue"]
