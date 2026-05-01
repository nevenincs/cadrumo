"""Unit tests for :func:`aeat.financial.vat.verify_catalogue`."""

from __future__ import annotations

import pytest

from . import (
    VAT_CATALOGUE_2025,
    VATCatalogue,
    VATCategory,
    verify_catalogue,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_model]


def test_shipped_catalogue_is_clean() -> None:
    """The shipped VAT_CATALOGUE_2025 must verify without errors."""
    report = verify_catalogue(VAT_CATALOGUE_2025)
    assert report.clean, [issue.model_dump() for issue in report.errors]


def test_empty_catalogue_reports_missing_categories() -> None:
    """An empty catalogue flags every VATCategory as missing."""
    empty = VATCatalogue()
    report = verify_catalogue(empty)
    codes = {issue.code for issue in report.errors}
    assert "missing_category" in codes
    assert len(report.errors) >= len(list(VATCategory))


def test_partial_catalogue_reports_only_the_gaps() -> None:
    """A catalogue missing one category yields one missing_category error."""
    reduced = VATCatalogue(
        regulations={cat: reg for cat, reg in VAT_CATALOGUE_2025.regulations.items() if cat is not VATCategory.UNKNOWN}
    )
    report = verify_catalogue(reduced)
    missing = [
        issue
        for issue in report.errors
        if issue.code == "missing_category" and issue.category_id == VATCategory.UNKNOWN.value
    ]
    assert len(missing) == 1
