"""IVA catalogue verification tests."""

from __future__ import annotations

from datetime import date

import pytest

from .. import IvaCatalogue, IvaCategory, resolve_catalogue, verify_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATALOGUE = resolve_catalogue(on=date(2025, 1, 1))


def test_shipped_catalogue_is_clean() -> None:
    assert len(_CATALOGUE) > 0, "catalogue must be non-empty for the clean check to be meaningful"
    report = verify_catalogue(_CATALOGUE)
    assert report.clean is True, [issue.model_dump() for issue in report.errors]
    assert report.errors == ()


def test_empty_catalogue_reports_missing_categories() -> None:
    empty = IvaCatalogue()
    report = verify_catalogue(empty)
    codes = {issue.code for issue in report.errors}
    assert "missing_category" in codes
    assert len(report.errors) >= len(list(IvaCategory))


def test_partial_catalogue_reports_only_the_gaps() -> None:
    reduced = IvaCatalogue(
        regulations={cat: reg for cat, reg in _CATALOGUE.regulations.items() if cat is not IvaCategory.UNKNOWN},
    )
    report = verify_catalogue(reduced)
    missing = [
        issue
        for issue in report.errors
        if issue.code == "missing_category" and issue.category_id == IvaCategory.UNKNOWN.value
    ]
    assert len(missing) == 1
