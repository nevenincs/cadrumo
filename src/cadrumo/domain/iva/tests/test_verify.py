"""IVA catalogue verification tests."""

from __future__ import annotations

from datetime import date

import pytest

from .. import IvaCatalogue, IvaCategory, IvaCitation, IvaRegulation, resolve_catalogue, verify_catalogue

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_CATALOGUE = resolve_catalogue(on=date(2025, 1, 1))


def test_shipped_catalogue_is_clean() -> None:
    assert len(_CATALOGUE) > 0, "catalogue must be non-empty for the clean check to be meaningful"
    report = verify_catalogue(_CATALOGUE)
    assert report.ok is True, [issue.model_dump() for issue in report.errors]
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


def test_a_plausible_quotation_absent_from_the_corpus_is_reported() -> None:
    """The clean result above is only worth reading if this one reds.

    The substituted text is deliberately plausible -- correct article, correct
    sentence shape, wrong rate -- because that is the failure the check exists
    for. A non-emptiness check, which is what this replaced, passes it happily.
    """
    original = _CATALOGUE.regulations[IvaCategory.DOMESTIC_GENERAL]
    fabricated = IvaCitation.model_validate(
        {
            "legal_reference": original.citations[0].legal_reference,
            "quoted_text": "El Impuesto se exigira al tipo del 25 por ciento",
            "valid_from": date(2022, 1, 1),
            "valid_to": date(2026, 12, 31),
        },
    )
    report = verify_catalogue(
        IvaCatalogue(
            regulations={
                **_CATALOGUE.regulations,
                IvaCategory.DOMESTIC_GENERAL: original.model_copy(
                    update={"citations": (fabricated, *original.citations[1:])},
                ),
            },
        ),
    )
    assert [issue.code for issue in report.errors] == ["quotation_absent_from_corpus"], [
        issue.model_dump() for issue in report.errors
    ]


def test_unknown_registry_legal_reference_is_reported() -> None:
    original = _CATALOGUE.regulations[IvaCategory.DOMESTIC_GENERAL]
    invalid_citation = IvaCitation.model_validate(
        {
            "legal_reference": "ley-37-1992:art-not-in-registry",
            "quoted_text": original.citations[0].quoted_text,
            "valid_from": date(2022, 1, 1),
            "valid_to": date(2026, 12, 31),
        },
    )
    invalid_regulation = IvaRegulation.model_validate(
        {
            **original.model_dump(),
            "citations": (invalid_citation, *original.citations[1:]),
        },
    )
    report = verify_catalogue(
        IvaCatalogue(
            regulations={
                **_CATALOGUE.regulations,
                IvaCategory.DOMESTIC_GENERAL: invalid_regulation,
            },
        ),
    )
    assert any(
        issue.code == "unknown_legal_reference" and issue.category_id == IvaCategory.DOMESTIC_GENERAL.value
        for issue in report.errors
    )
