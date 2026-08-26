"""Real-registry proofs for the conformance provenance projection."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority

from .. import RegistryConformanceProfile
from ._conformance_profile_fixtures import degraded_profile, validated_profile

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_validated_rows_keep_construct_floor_and_casilla_provenance_as_separate_axes(
    validated_profile: RegistryConformanceProfile,
    registry_authority: ValidatedRegistryAuthority,
) -> None:
    """The public profile preserves both finite construct and casilla ledgers."""
    revisions = {
        (modelo.id, revision.id): revision
        for modelo in registry_authority.modelos
        for revision in modelo.revisions.values()
    }

    for row in validated_profile.rows:
        revision = revisions[(row.modelo, row.revision)]
        assert row.model_law_coverage is not None, "revision evidence floor was not measured"
        assert row.construct_evidence is not None, "construct evidence was not projected"
        assert row.construct_evidence.ledger.modelo == row.modelo
        assert row.construct_evidence.ledger.revision == row.revision

        expected_constructs = {
            (kind, declaration.id)
            for kind, declarations in (
                ("formula", revision.formulas),
                ("parameter", revision.parameters),
                ("binding", revision.bindings),
                ("relation", revision.relations),
            )
            for declaration in declarations
        }
        expected_constructs.update(("selector", binding.id) for binding in revision.bindings)
        assert {(item.kind, item.construct_id) for item in row.construct_evidence.rows} == expected_constructs
        if row.construct_evidence.filing_eligible:
            assert row.construct_evidence.gaps == ()
            assert row.construct_evidence.filing_gaps == ()
            assert row.construct_evidence.inspection_gaps == ()
        else:
            # Inspection preserves any incomplete construct rows that exist,
            # but a revision with no construct declarations is legitimately
            # empty.  Either way, none can become filing-grade gaps.
            assert row.construct_evidence.filing_gaps == ()
            assert row.construct_evidence.inspection_gaps == row.construct_evidence.gaps

        inventory = revision.producer_inventory()
        expected_traces = tuple(
            (
                trace.casilla.id,
                trace.casilla.input_kind,
                trace.producer_kind,
                trace.reason,
                None if trace.formula is None else trace.formula.id,
                None if trace.binding is None else trace.binding.id,
                None if trace.relation is None else trace.relation.id,
                trace.casilla.legal_refs,
                trace.casilla.source_refs,
                trace.producer_legal_refs,
                trace.producer_source_refs,
            )
            for casilla in sorted(revision.casillas, key=lambda item: item.id)
            for trace in inventory.producer_provenance_by_casilla[casilla.id]
        )
        actual_traces = tuple(
            (
                trace.casilla_id,
                trace.input_kind,
                trace.producer_kind,
                trace.reason,
                trace.formula_id,
                trace.binding_id,
                trace.relation_id,
                trace.casilla_legal_refs,
                trace.casilla_source_refs,
                trace.producer_legal_refs,
                trace.producer_source_refs,
            )
            for trace in row.casilla_provenance
        )
        assert actual_traces == expected_traces


def test_degraded_rows_keep_schema_traces_but_mark_construct_evidence_unmeasured(
    degraded_profile: RegistryConformanceProfile,
    validated_profile: RegistryConformanceProfile,
) -> None:
    """A degraded read does not invent validated construct evidence."""
    assert degraded_profile.construct_evidence_unmeasured_rows == degraded_profile.rows
    assert all(row.construct_evidence is None for row in degraded_profile.rows)
    assert all(row.model_law_coverage is None for row in degraded_profile.rows)

    validated_traces = {(row.modelo, row.revision): row.casilla_provenance for row in validated_profile.rows}
    for row in degraded_profile.rows:
        assert row.registry_validated is False
        assert row.casilla_provenance == validated_traces[(row.modelo, row.revision)]


def test_scope_keeps_inspection_ledgers_visible_without_filing_grade_gap_counts(
    validated_profile: RegistryConformanceProfile,
) -> None:
    """Inspection ledgers remain measured while filing-grade counters stay strict."""
    scoped_rows = [
        row
        for row in validated_profile.rows
        if row.model_law_coverage is not None and row.model_law_coverage.authority_scope == "inspection_only"
    ]
    assert scoped_rows, "the registry must retain an inspection-only revision"

    rows_with_inspection_construct_gaps = []
    rows_with_inspection_law_gaps = []
    for row in scoped_rows:
        assert row.construct_evidence is not None
        assert row.construct_evidence.authority_scope == "inspection_only"
        assert row.model_law_coverage is not None
        assert row.model_law_coverage.required_tier_gaps == ()
        assert row.has_required_coverage_gap is False
        assert row.construct_evidence.filing_gaps == ()
        if row.model_law_coverage.gap_tiers:
            rows_with_inspection_law_gaps.append(row)
        if row.construct_evidence.gaps:
            rows_with_inspection_construct_gaps.append(row)

    assert not set(scoped_rows) & set(validated_profile.required_coverage_gap_rows)
    assert not set(scoped_rows) & set(validated_profile.construct_evidence_gap_rows)
    assert rows_with_inspection_law_gaps, "inspection evidence must retain visible law gaps where declared"
    assert rows_with_inspection_construct_gaps, "inspection evidence must retain visible construct gaps where declared"
    assert set(rows_with_inspection_construct_gaps) <= set(validated_profile.construct_evidence_inspection_gap_rows)


__all__ = ["degraded_profile", "validated_profile"]
