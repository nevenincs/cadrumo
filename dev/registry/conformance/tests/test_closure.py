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
from cadrumo.core import (
    RegistryAuthorityGrade,
    SourceConnectivityEncryptedRevisionProof,
    SourceConnectivityExecutableEvidence,
    SourceConnectivityOperatorReachabilityProof,
)
from cadrumo.core.source_connectivity import SourceConnectivityConnectionIdentity
from cadrumo.domain.calculations.registry import ModeloId, RevisionId, bundled_authority

from ..authorities import RegistryClosureAuthorities
from ..cli import app
from ..closure import (
    build_registry_closure_report,
    check_registry_closure_release,
    render_registry_closure_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AS_OF = date(2026, 8, 24)


class _HostileSourceConnectivityAuthority:
    """Protocol-complete context authority that must never be consumed by the CLI."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def source_is_enrolled(self, connection: SourceConnectivityConnectionIdentity) -> bool:
        self._reject("source_is_enrolled")

    def operator_workflow_reaches_source(
        self,
        connection: SourceConnectivityConnectionIdentity,
        proof: SourceConnectivityOperatorReachabilityProof,
    ) -> bool:
        self._reject("operator_workflow_reaches_source")

    def encrypted_revision_matches(self, proof: SourceConnectivityEncryptedRevisionProof) -> bool:
        self._reject("encrypted_revision_matches")

    def executable_evidence_digest(self, evidence: SourceConnectivityExecutableEvidence) -> str | None:
        self._reject("executable_evidence_digest")

    def _reject(self, port: str) -> None:
        self.calls.append(port)
        raise AssertionError(f"hostile closure context invoked {port}")


class _HostileFilingExportAuthority:
    """Protocol-complete context authority with no invented filing-proof success."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def proof_for(
        self,
        *,
        modelo: ModeloId,
        revision: RevisionId,
        layout_ids: tuple[str, ...],
    ) -> None:
        self.calls.append(f"{modelo}/{revision}/{','.join(layout_ids)}")
        raise AssertionError("hostile closure context invoked proof_for")


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


def test_cli_live_mode_uses_canonical_loaders_but_blocks_without_durable_filing_proof() -> None:
    """Live canonical loading cannot infer filing proof from an unenrolled layout."""
    result = CliRunner().invoke(app, ["closure", "--check", "--as-of", _AS_OF.isoformat()])

    assert result.exit_code == 1, result.output
    assert "release_eligible=false" in result.output
    assert "revisions=102" in result.output
    assert "canonical generation or successful production emitted-byte evidence is absent" in result.output
    assert "no canonical generation and production emitted-byte proof authority was supplied" not in result.output


def test_cli_offline_mode_explicitly_restores_the_no_proof_refusal() -> None:
    """Offline mode keeps authority absence distinct from live unenrolled proof."""
    result = CliRunner().invoke(
        app,
        ["closure", "--offline", "--check", "--as-of", _AS_OF.isoformat()],
    )

    assert result.exit_code == 1, result.output
    assert "release_eligible=false" in result.output
    assert "no canonical generation and production emitted-byte proof authority was supplied" in result.output
    assert "canonical generation or successful production emitted-byte evidence is absent" not in result.output


def test_actual_cli_ignores_a_precomposed_eligible_context_claim() -> None:
    """A canned typed claim cannot bypass canonical live proof composition."""
    canned_claim = _report(
        temporal=(_temporal(),),
        source=(_limb(name="source_connectivity"),),
        filing=(_limb(name="filing_export"),),
    )

    result = CliRunner().invoke(
        app,
        ["closure", "--check", "--as-of", _AS_OF.isoformat()],
        obj=canned_claim,
    )

    assert canned_claim.release_eligible
    assert result.exit_code == 1, result.output
    assert "release_eligible=false" in result.output
    assert "closure as_of=2026-08-24 registry_validated=true release_eligible=false" in result.output


def test_actual_cli_ignores_exact_hostile_authority_context() -> None:
    """Only canonical live authorities may compose the public closure command.

    The context has the precise ``RegistryClosureAuthorities`` shape that the
    removed branch accepted.  Its protocol-complete ports are tripwires, not
    substitute proof: consuming either proves that command context has regained
    authority-selection power.  The real registry has no durably enrolled
    filing proof, so the intact command must remain ineligible.
    """
    source = _HostileSourceConnectivityAuthority()
    filing = _HostileFilingExportAuthority()
    hostile = RegistryClosureAuthorities(
        registry=bundled_authority(),
        source_connectivity=source,
        filing_export=filing,
    )

    result = CliRunner().invoke(
        app,
        ["closure", "--check", "--as-of", _AS_OF.isoformat()],
        obj=hostile,
    )

    assert result.exit_code == 1, result.output
    assert "release_eligible=false" in result.output
    assert "canonical generation or successful production emitted-byte evidence is absent" in result.output
    assert source.calls == []
    assert filing.calls == []
