"""Unit coverage for the cross-authority registry closure release predicate."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from cadrumo.application.registry import (
    FilingExportCoverageReport,
    RegistryClosureEvidence,
    RegistryClosureLimb,
    SourceConnectivityCoverageReport,
    TemporalCoverageReport,
    TemporalRevisionCoverage,
)
from cadrumo.core import RegistryAuthorityGrade

from ..cli import app
from ..closure import (
    build_registry_closure_report,
    check_registry_closure_release,
    render_registry_closure_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AS_OF = date(2026, 8, 24)


def _temporal(*, modelo: str = "303", revision: str = "2026", refused: bool = False) -> TemporalRevisionCoverage:
    """Build one exact temporal limb fixture without weakening its model contract."""
    base = {
        "modelo": modelo,
        "revision": revision,
        "filing_year": 2026,
        "period": "1T",
        "selected_revision": revision,
        "declared_authority_grade": RegistryAuthorityGrade.FILING,
    }
    if refused:
        return TemporalRevisionCoverage(
            **base,
            status="refused",
            failure_code="declared_grade_snapshot_refused",
            failure_detail="the declared grade could not open its validated snapshot",
        )
    return TemporalRevisionCoverage(**base, status="validated")


def _limb(
    *,
    modelo: str = "303",
    revision: str = "2026",
    name: str,
) -> RegistryClosureLimb:
    """Build one real satisfied app-limb shape for deterministic join tests."""
    return RegistryClosureLimb(
        modelo=modelo,
        revision=revision,
        name=name,  # type: ignore[arg-type]  # Fixed test literals exercise both accepted limb names.
        outcome="satisfied",
        evidence=(RegistryClosureEvidence(authority=f"test.{name}", locator="test://evidence"),),
    )


def _report(
    *,
    temporal: tuple[TemporalRevisionCoverage, ...],
    source: tuple[RegistryClosureLimb, ...],
    filing: tuple[RegistryClosureLimb, ...],
):
    """Compose one report from the real application-boundary report types."""
    return build_registry_closure_report(
        temporal_coverage=TemporalCoverageReport(rows=temporal),
        source_connectivity=SourceConnectivityCoverageReport(limbs=source),
        filing_export=FilingExportCoverageReport(limbs=filing),
        as_of=_AS_OF,
    )


def test_exact_three_limb_join_satisfies_the_blocking_release_predicate() -> None:
    """A complete row is eligible only when every independently owned limb is satisfied."""
    report = _report(
        temporal=(_temporal(),),
        source=(_limb(name="source_connectivity"),),
        filing=(_limb(name="filing_export"),),
    )

    result = check_registry_closure_release(report)

    assert result.passed
    assert report.release_eligible
    assert report.satisfied_revision_count == 1
    assert report.refused_revision_count == 0
    rendered = render_registry_closure_report(report)
    assert "release_eligible=true" in rendered
    assert "closure_row modelo=303 revision=2026 predicate_outcome=satisfied" in rendered


def test_typed_temporal_failure_is_retained_as_an_owned_release_refusal() -> None:
    """The release renderer must not collapse a grade-snapshot failure to incomplete."""
    report = _report(
        temporal=(_temporal(refused=True),),
        source=(_limb(name="source_connectivity"),),
        filing=(_limb(name="filing_export"),),
    )

    refusal = report.rows[0].refusals[0]

    assert not check_registry_closure_release(report).passed
    assert refusal.model_dump() == {
        "limb": "temporal_coverage",
        "reason": "declared_grade_snapshot_refused",
        "detail": "the declared grade could not open its validated snapshot",
        "disposition": {
            "limb": "temporal_coverage",
            "state": "blocked",
            "owner": "registry-temporal-coverage",
            "work_item": "registry-temporal-coverage:authority-grade",
            "reconsideration_condition": (
                "Revalidate the exact law-selected revision and its declared authority-grade snapshot."
            ),
        },
    }
    assert report.refusal_reason_census == {"declared_grade_snapshot_refused": 1}


def test_missing_and_extra_limb_coordinates_remain_visible_cross_authority_disagreements() -> None:
    """A join cannot hide either a missing temporal coordinate or an unexpected limb."""
    report = _report(
        temporal=(_temporal(modelo="999"),),
        source=(_limb(modelo="100", name="source_connectivity"),),
        filing=(_limb(modelo="999", name="filing_export"),),
    )

    row = report.rows[0]

    assert row.source_connectivity is None
    assert row.predicate_outcome == "refused"
    assert row.refusals[0].reason == "cross_limb_disagreement"
    assert [
        (item.modelo, item.revision, item.limb, item.kind)
        for item in report.join_disagreements
    ] == [
        ("100", "2026", "source_connectivity", "unexpected_limb_coordinate"),
        ("999", "2026", "source_connectivity", "missing_from_limb"),
    ]
    assert not report.release_eligible


def test_row_constructor_refuses_a_present_limb_at_a_different_coordinate() -> None:
    """A model mutation cannot cross-satisfy another revision's source evidence."""
    report = _report(
        temporal=(_temporal(),),
        source=(_limb(name="source_connectivity"),),
        filing=(_limb(name="filing_export"),),
    )
    row = report.rows[0]

    with pytest.raises(ValidationError, match="source_connectivity limb coordinate must match"):
        row.__class__(
            modelo=row.modelo,
            revision=row.revision,
            temporal_coverage=row.temporal_coverage,
            source_connectivity=_limb(modelo="100", name="source_connectivity"),
            filing_export=row.filing_export,
        )


def test_cli_check_blocks_the_live_bundled_report() -> None:
    """The real CLI gate blocks the current bundled registry's incomplete claim."""
    result = CliRunner().invoke(app, ["closure", "--check", "--as-of", _AS_OF.isoformat()])

    assert result.exit_code == 1, result.output
    assert "release_eligible=false" in result.output
    assert "revisions=102" in result.output
    assert "reason=missing_evidence" in result.output
