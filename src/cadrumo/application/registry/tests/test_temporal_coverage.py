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
    row = TemporalRevisionCoverage(
        **_temporal_refusal_payload(
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
        TemporalRevisionCoverage(
            **(_temporal_refusal_payload(failure_code=failure_code) | mutation),
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
    row = TemporalRevisionCoverage(**_temporal_refusal_payload(failure_code=failure_code))
    mutated_row = row.model_copy(update=mutation)

    with pytest.raises(ValidationError, match=message):
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
        TemporalRevisionCoverage(**payload)


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

    row = _single_refusal(compose_temporal_coverage(authority=authority), "law_selection_refused")

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

    row = _single_refusal(compose_temporal_coverage(authority=authority), "selected_revision_mismatch")

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

    row = _single_refusal(compose_temporal_coverage(authority=authority), "undeclared_authority_grade")

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

    row = _single_refusal(compose_temporal_coverage(authority=authority), "declared_grade_snapshot_refused")

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

    row = _single_refusal(compose_temporal_coverage(authority=authority), "snapshot_revision_mismatch")

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


def _single_refusal(report, expected_failure_code: str) -> TemporalRevisionCoverage:
    """Assert one retained denominator row and return it for its identity proof."""
    assert report.fully_validated is False
    assert len(report.rows) == 1
    assert len(report.refused_rows) == 1
    row = report.refused_rows[0]
    assert row.status == "refused"
    assert row.failure_code == expected_failure_code
    assert row.failure_detail
    return row


def _temporal_refusal_payload(
    *,
    failure_code: str,
    selected_revision: str | None = None,
    declared_authority_grade: RegistryAuthorityGrade | None = RegistryAuthorityGrade.APPLICABILITY,
) -> dict[str, str | RegistryAuthorityGrade | None]:
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
