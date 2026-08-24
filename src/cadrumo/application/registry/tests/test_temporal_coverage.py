"""Focused proof of the derived temporal and authority-grade evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from ....core import RegistryAuthorityGrade
from ....domain.calculations.registry import RegistryValidationError, bundled_authority
from .. import TemporalRevisionCoverage, compose_temporal_coverage

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_temporal_coverage_reselects_every_registered_revision_and_checks_its_declared_grade() -> None:
    full_authority = bundled_authority()
    full_authority.validate_registry()
    authority = replace(
        full_authority,
        modelos=(full_authority.modelo("036"),),
        _snapshots={},
    )
    report = compose_temporal_coverage(authority=authority)
    expected_coordinates = {
        (modelo.id, revision.id)
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
    }

    assert {(row.modelo, row.revision) for row in report.rows} == expected_coordinates
    assert report.fully_validated is True
    assert report.refused_rows == ()
    for row in report.rows:
        inspection = authority.inspect_revision(row.modelo, filing_year=row.filing_year, period=row.period)
        assert str(inspection.revision_id) == row.selected_revision
        if row.status == "validated":
            assert row.declared_authority_grade is not None
            snapshot = authority.snapshot(
                row.modelo,
                filing_year=row.filing_year,
                period=row.period,
                grade=row.declared_authority_grade,
            )
            assert str(snapshot.revision.id) == row.revision
        elif row.declared_authority_grade is None:
            with pytest.raises(RegistryValidationError):
                authority.snapshot(
                    row.modelo,
                    filing_year=row.filing_year,
                    period=row.period,
                    grade=RegistryAuthorityGrade.APPLICABILITY,
                )
        else:
            with pytest.raises(RegistryValidationError):
                authority.snapshot(
                    row.modelo,
                    filing_year=row.filing_year,
                    period=row.period,
                    grade=row.declared_authority_grade,
                )


def test_temporal_coverage_row_refuses_a_claim_without_its_required_evidence() -> None:
    with pytest.raises(ValidationError, match="declared authority grade"):
        TemporalRevisionCoverage(
            modelo="036",
            revision="2025-02-03-y-siguientes",
            filing_year=2025,
            period="alta",
            selected_revision="2025-02-03-y-siguientes",
            status="validated",
        )
