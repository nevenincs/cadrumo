"""Focused proof of the derived temporal and authority-grade evidence."""

from __future__ import annotations

from dataclasses import replace

import pytest
from pydantic import ValidationError

from ....core import RegistryAuthorityGrade
from ....domain.calculations.registry.authority import bundled_authority
from ....domain.calculations.registry.errors import RegistryValidationError
from ....domain.calculations.registry.temporal import coverage_assessment_horizon, revision_selection_coordinates
from ..temporal_coverage import (
    TemporalCoverageReport,
    TemporalRevisionCoverage,
    TemporalRevisionCoverageSummary,
    compose_temporal_coverage,
)

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
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    expected_coordinates = {
        (modelo.id, revision.id, filing_year, period)
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        for filing_year, period in revision_selection_coordinates(
            revision,
            assessment_horizon=assessment_horizon,
        )
    }

    assert {(row.modelo, row.revision, row.filing_year, row.period) for row in report.rows} == expected_coordinates
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


def test_temporal_coverage_derives_the_complete_registered_matrix_from_authority(
    registry_authority,
) -> None:
    """Every selector cell through the registry horizon remains in the denominator."""
    assessment_horizon = coverage_assessment_horizon(registry_authority.catalogues)
    report = compose_temporal_coverage(authority=registry_authority)
    expected_coordinates = {
        (modelo.id, revision.id, filing_year, period)
        for modelo in registry_authority.modelos
        for revision in modelo.revisions.values()
        for filing_year, period in revision_selection_coordinates(
            revision,
            assessment_horizon=assessment_horizon,
        )
    }

    actual_coordinates = {(row.modelo, row.revision, row.filing_year, row.period) for row in report.rows}
    assert actual_coordinates == expected_coordinates
    assert len(report.rows) == len(expected_coordinates)
    assert len(report.rows) > len(report.revision_summaries)
    assert {
        (summary.modelo, summary.revision, coordinate.filing_year, coordinate.period)
        for summary in report.revision_summaries
        for coordinate in summary.coordinates
    } == expected_coordinates


def test_temporal_coverage_expands_open_selectors_through_the_supported_horizon(
    registry_authority,
) -> None:
    """A real long-span selector proves later years are not silently skipped."""
    modelo = registry_authority.modelo("341")
    # Select the OPEN revision by its defining property, never by position.
    # Modelo 341 declares two -- 2005-2015 closed at year_to 2015, and
    # 2016-y-siguientes open -- and dictionary order yields the CLOSED one
    # first, so this test was exercising a bounded selector while its name and
    # docstring both claim it proves an OPEN selector expands to the horizon.
    revision = next(candidate for candidate in modelo.revisions.values() if candidate.period_selector.year_to is None)
    # Compose the authority from the OPEN revision alone. The assertions below
    # compare every report row against this one revision's coordinates, which
    # is only meaningful when it is the only revision composed -- modelo 341's
    # closed 2005-2015 sibling otherwise contributes rows such as (2014, "2T")
    # that no open-selector expectation can or should account for.
    open_only_modelo = modelo.model_copy(update={"revisions": {revision.id: revision}})
    authority = _authority_with_single_model(registry_authority, composed_modelo=open_only_modelo)
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)

    report = compose_temporal_coverage(authority=authority)
    expected_coordinates = revision_selection_coordinates(revision, assessment_horizon=assessment_horizon)

    assert {(row.filing_year, row.period) for row in report.rows} == set(expected_coordinates)
    assert {row.filing_year for row in report.rows} == set(
        range(revision.period_selector.year_from, assessment_horizon + 1)
    )
    assert len(report.rows) > len(revision.period_selector.periods)


def test_temporal_coverage_uses_the_catalogue_horizon_not_a_copied_year_list(
    registry_authority,
) -> None:
    """A shortened supported-year declaration removes only its later derived cells."""
    modelo = registry_authority.modelo("036")
    revision = next(iter(modelo.revisions.values()))
    original_years = registry_authority.catalogues.supported_filing_years.years
    shortened_catalogues = registry_authority.catalogues.model_copy(
        update={
            "supported_filing_years": registry_authority.catalogues.supported_filing_years.model_copy(
                update={"years": original_years[:-1]},
            ),
        },
    )
    authority = replace(
        _authority_with_single_model(registry_authority, composed_modelo=modelo),
        catalogues=shortened_catalogues,
    )
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)

    report = compose_temporal_coverage(authority=authority)

    assert {(row.filing_year, row.period) for row in report.rows} == set(
        revision_selection_coordinates(revision, assessment_horizon=assessment_horizon),
    )
    assert all(row.filing_year <= assessment_horizon for row in report.rows)


def test_temporal_coverage_preserves_declared_period_alias_tokens_without_manufacturing_cells(
    registry_authority,
) -> None:
    """The matrix retains a selector's canonical EVENT-N token, never its request aliases."""
    modelo = registry_authority.modelo("210")
    authority = _authority_with_single_model(registry_authority, composed_modelo=modelo)
    assessment_horizon = coverage_assessment_horizon(authority.catalogues)
    report = compose_temporal_coverage(authority=authority)
    expected_coordinates = {
        (revision.id, filing_year, period)
        for revision in modelo.revisions.values()
        for filing_year, period in revision_selection_coordinates(
            revision,
            assessment_horizon=assessment_horizon,
        )
    }

    assert {(row.revision, row.filing_year, row.period) for row in report.rows} == expected_coordinates
    assert "EVENT-N" in {row.period for row in report.rows}
    assert "EVENT-1" not in {row.period for row in report.rows}


def test_revision_coordinate_derivation_fails_closed_when_no_declared_year_reaches_the_horizon(
    registry_authority,
) -> None:
    """A revision beyond a requested assessment horizon cannot disappear as an empty span."""
    revision = next(
        revision
        for modelo in registry_authority.modelos
        for revision in modelo.revisions.values()
        if revision.period_selector.year_from is not None
    )
    with pytest.raises(RegistryValidationError, match="declares no filing year through coverage horizon"):
        revision_selection_coordinates(
            revision,
            assessment_horizon=revision.period_selector.year_from - 1,
        )


def test_temporal_coverage_retains_a_hidden_later_cell_refusal_from_an_authority_mutation(
    registry_authority,
) -> None:
    """A first-year success cannot mask a later selector cell removed from lookup authority."""
    modelo = registry_authority.modelo("036")
    revision = next(iter(modelo.revisions.values()))
    assessment_horizon = coverage_assessment_horizon(registry_authority.catalogues)
    lookup_revision = revision.model_copy(
        update={"period_selector": revision.period_selector.model_copy(update={"year_to": assessment_horizon - 1})},
    )
    lookup_modelo = modelo.model_copy(update={"revisions": {lookup_revision.id: lookup_revision}})
    authority = _authority_with_single_model(
        registry_authority,
        composed_modelo=modelo,
        lookup_modelo=lookup_modelo,
    )

    report = compose_temporal_coverage(authority=authority)

    late_rows = tuple(row for row in report.rows if row.filing_year == assessment_horizon)
    assert late_rows
    assert all(row.failure_code == "law_selection_refused" for row in late_rows)
    assert all(row.status == "validated" for row in report.rows if row.filing_year < assessment_horizon)


def test_temporal_revision_summary_refuses_duplicate_or_cross_revision_cells() -> None:
    """The revision-facing projection cannot re-hide matrix cells during aggregation."""
    row = TemporalRevisionCoverage(
        modelo="036",
        revision="2025-02-03-y-siguientes",
        filing_year=2025,
        period="alta",
        selected_revision="2025-02-03-y-siguientes",
        declared_authority_grade=RegistryAuthorityGrade.APPLICABILITY,
        status="validated",
    )
    with pytest.raises(ValidationError, match="cannot contain a coordinate more than once"):
        TemporalRevisionCoverageSummary(
            modelo=row.modelo,
            revision=row.revision,
            declared_authority_grade=row.declared_authority_grade,
            coordinates=(row, row),
        )
    with pytest.raises(ValidationError, match="must match its summary revision"):
        TemporalRevisionCoverageSummary(
            modelo=row.modelo,
            revision="2024-01-01-a-2024-12-31",
            declared_authority_grade=row.declared_authority_grade,
            coordinates=(row,),
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


@pytest.mark.parametrize(
    ("failure_code", "selected_revision", "declared_authority_grade"),
    [
        ("law_selection_refused", None, RegistryAuthorityGrade.APPLICABILITY),
        ("selected_revision_mismatch", "2024-01-01-a-2024-12-31", None),
        ("undeclared_authority_grade", "2025-02-03-y-siguientes", None),
        (
            "declared_grade_snapshot_refused",
            "2025-02-03-y-siguientes",
            RegistryAuthorityGrade.APPLICABILITY,
        ),
        (
            "snapshot_revision_mismatch",
            "2024-01-01-a-2024-12-31",
            RegistryAuthorityGrade.APPLICABILITY,
        ),
    ],
)
def test_temporal_coverage_row_constructs_only_real_refusal_branch_shapes(
    failure_code: str,
    selected_revision: str | None,
    declared_authority_grade: RegistryAuthorityGrade | None,
) -> None:
    row = TemporalRevisionCoverage.model_validate(
        _temporal_refusal_payload(
            failure_code=failure_code,
            selected_revision=selected_revision,
            declared_authority_grade=declared_authority_grade,
        ),
    )

    assert row.status == "refused"
    assert row.failure_code == failure_code
    assert row.selected_revision == selected_revision
    assert row.declared_authority_grade == declared_authority_grade


@pytest.mark.parametrize(
    ("failure_code", "mutation", "message"),
    [
        (
            "selected_revision_mismatch",
            {"selected_revision": None},
            "selected-revision mismatch requires",
        ),
        (
            "snapshot_revision_mismatch",
            {"selected_revision": None},
            "snapshot-revision mismatch requires",
        ),
        (
            "declared_grade_snapshot_refused",
            {"selected_revision": None},
            "declared-grade snapshot refusal requires the registered",
        ),
        (
            "declared_grade_snapshot_refused",
            {"declared_authority_grade": None},
            "declared-grade snapshot refusal requires a declared",
        ),
    ],
)
def test_temporal_coverage_row_refuses_impossible_branch_evidence_at_construction(
    failure_code: str,
    mutation: dict[str, str | RegistryAuthorityGrade | None],
    message: str,
) -> None:
    with pytest.raises(ValidationError, match=message):
        TemporalRevisionCoverage.model_validate(_temporal_refusal_payload(failure_code=failure_code) | mutation)


@pytest.mark.parametrize("declared_authority_grade", tuple(RegistryAuthorityGrade))
def test_undeclared_grade_refusal_rejects_every_non_null_grade_at_construction(
    declared_authority_grade: RegistryAuthorityGrade,
) -> None:
    """Every declared ladder rung contradicts an undeclared-grade refusal."""
    with pytest.raises(ValidationError, match="undeclared-grade refusal cannot carry a declared authority grade"):
        TemporalRevisionCoverage.model_validate(
            _temporal_refusal_payload(failure_code="undeclared_authority_grade")
            | {"declared_authority_grade": declared_authority_grade},
        )


@pytest.mark.parametrize(
    ("failure_code", "mutation", "message"),
    [
        (
            "law_selection_refused",
            {"selected_revision": "2025-02-03-y-siguientes"},
            "law-selection refusal cannot retain",
        ),
        (
            "selected_revision_mismatch",
            {"selected_revision": None},
            "selected-revision mismatch requires",
        ),
        (
            "undeclared_authority_grade",
            {"selected_revision": None},
            "undeclared-grade refusal requires",
        ),
        (
            "declared_grade_snapshot_refused",
            {"declared_authority_grade": None},
            "declared-grade snapshot refusal requires a declared",
        ),
        (
            "snapshot_revision_mismatch",
            {"selected_revision": "2025-02-03-y-siguientes"},
            "snapshot-revision mismatch requires",
        ),
    ],
)
def test_temporal_coverage_validator_bites_each_refusal_branch_mutation(
    failure_code: str,
    mutation: dict[str, str | RegistryAuthorityGrade | None],
    message: str,
) -> None:
    row = TemporalRevisionCoverage.model_validate(_temporal_refusal_payload(failure_code=failure_code))
    mutated_row = row.model_copy(update=mutation)

    with pytest.raises(ValidationError, match=message):
        TemporalRevisionCoverage.model_validate(mutated_row.model_dump())


@pytest.mark.parametrize("declared_authority_grade", tuple(RegistryAuthorityGrade))
def test_undeclared_grade_refusal_revalidates_every_non_null_grade_contradiction(
    declared_authority_grade: RegistryAuthorityGrade,
) -> None:
    """Frozen-row mutation must not evade the all-rungs contradiction guard."""
    row = TemporalRevisionCoverage.model_validate(
        _temporal_refusal_payload(failure_code="undeclared_authority_grade"),
    )
    mutated_row = row.model_copy(update={"declared_authority_grade": declared_authority_grade})

    with pytest.raises(ValidationError, match="undeclared-grade refusal cannot carry a declared authority grade"):
        TemporalRevisionCoverage.model_validate(mutated_row.model_dump())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("modelo", "not a modelo", "String should match pattern"),
        ("revision", "revision with spaces", "String should match pattern"),
        ("filing_year", 1, "greater than or equal"),
        ("period", "not-a-registry-period", "invalid period code"),
        ("selected_revision", "selected revision with spaces", "String should match pattern"),
    ],
)
def test_temporal_coverage_row_refuses_fabricated_registry_coordinates(
    field: str,
    value: int | str,
    message: str,
) -> None:
    payload = {
        "modelo": "036",
        "revision": "2025-02-03-y-siguientes",
        "filing_year": 2025,
        "period": "alta",
        "selected_revision": "2025-02-03-y-siguientes",
        "declared_authority_grade": RegistryAuthorityGrade.APPLICABILITY,
        "status": "validated",
    }
    payload[field] = value

    with pytest.raises(ValidationError, match=message):
        TemporalRevisionCoverage.model_validate(payload)


def test_temporal_coverage_retains_law_selection_refusal_from_an_authority_mutation(
    registry_authority,
) -> None:
    modelo = registry_authority.modelo("100")
    target = modelo.revisions["2020"]
    selected_elsewhere = modelo.revisions["2021"]
    composed_modelo = modelo.model_copy(update={"revisions": {target.id: target}})
    lookup_modelo = modelo.model_copy(update={"revisions": {selected_elsewhere.id: selected_elsewhere}})
    authority = _authority_with_single_model(
        registry_authority,
        composed_modelo=composed_modelo,
        lookup_modelo=lookup_modelo,
    )

    row = _refusals(compose_temporal_coverage(authority=authority), "law_selection_refused")[0]

    assert (row.modelo, row.revision, row.selected_revision) == ("100", "2020", None)


def test_temporal_coverage_retains_selection_identity_mismatch_from_an_authority_mutation(
    registry_authority,
) -> None:
    modelo = registry_authority.modelo("100")
    target = modelo.revisions["2020"]
    selected_elsewhere = modelo.revisions["2021"].model_copy(
        update={"period_selector": target.period_selector},
    )
    composed_modelo = modelo.model_copy(update={"revisions": {target.id: target}})
    lookup_modelo = modelo.model_copy(update={"revisions": {selected_elsewhere.id: selected_elsewhere}})
    authority = _authority_with_single_model(
        registry_authority,
        composed_modelo=composed_modelo,
        lookup_modelo=lookup_modelo,
    )

    row = _refusals(compose_temporal_coverage(authority=authority), "selected_revision_mismatch")[0]

    assert (row.modelo, row.revision, row.selected_revision) == ("100", "2020", "2021")


def test_temporal_coverage_retains_undeclared_grade_refusal_from_an_authority_mutation(
    registry_authority,
) -> None:
    modelo = registry_authority.modelo("036")
    revision = next(iter(modelo.revisions.values()))
    ungraded = revision.model_copy(update={"authority_grade": None})
    authority = _authority_with_single_model(
        registry_authority,
        composed_modelo=modelo.model_copy(update={"revisions": {ungraded.id: ungraded}}),
    )

    refusals = _refusals(compose_temporal_coverage(authority=authority), "undeclared_authority_grade")
    row = refusals[0]

    assert len(refusals) == len(
        revision_selection_coordinates(
            ungraded,
            assessment_horizon=coverage_assessment_horizon(authority.catalogues),
        )
    )

    assert (row.modelo, row.revision, row.selected_revision) == ("036", revision.id, revision.id)


def test_temporal_coverage_retains_declared_grade_snapshot_refusal_from_an_authority_mutation(
    registry_authority,
) -> None:
    modelo = registry_authority.modelo("036")
    revision = next(iter(modelo.revisions.values()))
    filing_grade = revision.model_copy(update={"authority_grade": RegistryAuthorityGrade.FILING})
    authority = _authority_with_single_model(
        registry_authority,
        composed_modelo=modelo.model_copy(update={"revisions": {filing_grade.id: filing_grade}}),
    )

    refusals = _refusals(compose_temporal_coverage(authority=authority), "declared_grade_snapshot_refused")
    row = refusals[0]

    assert len(refusals) == len(
        revision_selection_coordinates(
            filing_grade,
            assessment_horizon=coverage_assessment_horizon(authority.catalogues),
        )
    )

    assert (row.modelo, row.revision, row.selected_revision) == ("036", revision.id, revision.id)


def test_temporal_coverage_retains_snapshot_identity_mismatch_from_an_authority_cache_mutation(
    registry_authority,
) -> None:
    modelo = registry_authority.modelo("100")
    target = modelo.revisions["2020"]
    cached_snapshot = registry_authority.snapshot("100", filing_year=2021, period="0A")
    assert target.authority_grade is not None
    composed_modelo = modelo.model_copy(update={"revisions": {target.id: target}})
    authority = _authority_with_single_model(
        registry_authority,
        composed_modelo=composed_modelo,
        snapshots={
            ("100", 2020, "0A", None, None, target.authority_grade): cached_snapshot,
        },
    )

    row = _refusals(compose_temporal_coverage(authority=authority), "snapshot_revision_mismatch")[0]

    assert (row.modelo, row.revision, row.selected_revision) == ("100", "2020", "2021")


def _authority_with_single_model(
    authority,
    *,
    composed_modelo,
    lookup_modelo=None,
    snapshots=None,
):
    """Return one real authority with independently mutated enumeration and lookup paths."""
    resolved_lookup_modelo = composed_modelo if lookup_modelo is None else lookup_modelo
    return replace(
        authority,
        modelos=(composed_modelo,),
        _modelos_by_id={composed_modelo.id: resolved_lookup_modelo},
        _snapshots={} if snapshots is None else snapshots,
    )


def _refusals(report: TemporalCoverageReport, expected_failure_code: str) -> tuple[TemporalRevisionCoverage, ...]:
    """Return every retained refusal for one mutation without discarding later cells."""
    assert report.fully_validated is False
    rows = tuple(row for row in report.refused_rows if row.failure_code == expected_failure_code)
    assert rows
    assert all(row.status == "refused" for row in rows)
    assert all(row.failure_detail for row in rows)
    return rows


def _temporal_refusal_payload(
    *,
    failure_code: str,
    selected_revision: str | None = None,
    declared_authority_grade: RegistryAuthorityGrade | None = RegistryAuthorityGrade.APPLICABILITY,
) -> dict[str, int | str | RegistryAuthorityGrade | None]:
    """Return one direct-construction payload shaped like a composer refusal branch."""
    revision = "2025-02-03-y-siguientes"
    if failure_code == "selected_revision_mismatch":
        selected_revision = "2024-01-01-a-2024-12-31" if selected_revision is None else selected_revision
    elif failure_code in {"undeclared_authority_grade", "declared_grade_snapshot_refused"}:
        selected_revision = revision if selected_revision is None else selected_revision
    elif failure_code == "snapshot_revision_mismatch":
        selected_revision = "2024-01-01-a-2024-12-31" if selected_revision is None else selected_revision
    if failure_code == "undeclared_authority_grade":
        declared_authority_grade = None
    return {
        "modelo": "036",
        "revision": revision,
        "filing_year": 2025,
        "period": "alta",
        "selected_revision": selected_revision,
        "declared_authority_grade": declared_authority_grade,
        "status": "refused",
        "failure_code": failure_code,
        "failure_detail": "the derived temporal boundary refused this revision",
    }
