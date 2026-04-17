"""Catalogue-level verification for ``aeat.financial.vat``.

Runs cross-record checks on top of the per-model validation that
pydantic already performs: every :class:`VATCategory` member must be
present; every regulation must carry ≥1 :class:`Citation`; every
citation must have non-empty ``quoted_text_es``; every
``boe_references`` id must match the kebab-case shape used by
:mod:`aeat.normatives`; every ``declares_in_modelos`` entry must be
three ASCII digits.
"""

from __future__ import annotations

import re

from ...logging import get_logger
from ._schema import (
    VATCatalogue,
    VATCategory,
    VerificationIssue,
    VerificationReport,
)

_logger = get_logger(__name__)

_NORMATIVE_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_MODELO_PATTERN = re.compile(r"^[0-9]{3}$")


def verify_catalogue(catalogue: VATCatalogue) -> VerificationReport:
    """Run every cross-record check on ``catalogue``.

    Args:
        catalogue: The :class:`VATCatalogue` under audit.

    Returns:
        A :class:`VerificationReport` aggregating every finding.
    """
    issues: list[VerificationIssue] = []

    present = set(catalogue.regulations.keys())
    missing = [member for member in VATCategory if member not in present]
    for member in missing:
        issues.append(
            VerificationIssue(
                level="error",
                code="missing_category",
                message=f"catalogue does not cover VATCategory.{member.name}",
                category_id=member.value,
            )
        )

    for regulation in catalogue:
        if not regulation.citations:
            issues.append(
                VerificationIssue(
                    level="error",
                    code="missing_citation",
                    message="regulation has no Citation records",
                    category_id=regulation.category.value,
                )
            )
        for citation in regulation.citations:
            if not citation.quoted_text_es.strip():
                issues.append(
                    VerificationIssue(
                        level="error",
                        code="empty_quoted_text",
                        message=f"citation {citation.article!r} has empty quoted_text_es",
                        category_id=regulation.category.value,
                    )
                )
        for ref in regulation.boe_references:
            if not _NORMATIVE_ID_PATTERN.fullmatch(ref):
                issues.append(
                    VerificationIssue(
                        level="error",
                        code="invalid_normative_id",
                        message=f"boe_reference {ref!r} is not a kebab-case normative id",
                        category_id=regulation.category.value,
                    )
                )
        for modelo in regulation.declares_in_modelos:
            if not _MODELO_PATTERN.fullmatch(modelo):
                issues.append(
                    VerificationIssue(
                        level="error",
                        code="invalid_modelo",
                        message=f"declares_in_modelos {modelo!r} is not a 3-digit modelo number",
                        category_id=regulation.category.value,
                    )
                )

    _logger.info("verify_catalogue produced %d issue(s)", len(issues))
    return VerificationReport(issues=tuple(issues))


__all__ = ["verify_catalogue"]
