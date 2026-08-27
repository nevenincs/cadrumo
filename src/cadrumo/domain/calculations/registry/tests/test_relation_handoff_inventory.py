"""Real-registry tests for the canonical relation handoff inventory."""

from __future__ import annotations

import pytest

from .....core.resources import bundled_path
from .._relation_aggregation import relation_aggregation_op
from ..authority import bundled_authority
from ..bindings import bound_casilla_binding_ids
from ..handoffs import (
    RegistryRelationHandoffApplicabilityAudit,
    RegistryRelationHandoffAudit,
    RelationHandoffRecord,
    audit_registry_relation_handoff_applicability,
    audit_registry_relation_handoffs,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_relation_handoff_inventory_enumerates_every_validated_relation() -> None:
    """Each real relation keeps source, target, period, aggregation, and refs."""
    authority = bundled_authority()
    audit = audit_registry_relation_handoffs(
        authority.modelos,
        authority.catalogues,
        source_root=bundled_path(),
    )

    relations = {
        (modelo.id, revision.id, relation.id): (modelo, revision, relation)
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        for relation in revision.relations
    }
    assert isinstance(audit, RegistryRelationHandoffAudit)
    assert audit.relation_count == len(relations)
    assert len({(record.target_modelo, record.target_revision, record.relation_id) for record in audit.records}) == len(
        audit.records,
    )

    for record in audit.records:
        modelo, revision, relation = relations[(record.target_modelo, record.target_revision, record.relation_id)]
        target_binding = next(binding for binding in revision.bindings if binding.id == relation.target_binding)
        expected_target_casillas = tuple(
            sorted(
                casilla.id
                for casilla in revision.casillas
                if relation.target_binding in bound_casilla_binding_ids(casilla)
            ),
        )

        assert record.target_modelo == modelo.id
        assert record.target_revision == revision.id
        assert record.relation_kind == relation.kind
        assert record.dependency_role == relation.dependency_role
        assert record.source_modelo == relation.source_modelo
        assert record.source_revision_selector == relation.source_revision_selector
        assert record.source_casilla_id == relation.source_casilla_id
        assert record.target_binding == relation.target_binding
        assert record.target_binding_source == target_binding.source
        assert record.target_casilla_ids == expected_target_casillas
        assert record.period_alignment == relation.period_alignment
        assert record.source_periods == relation.source_periods
        assert record.target_periods == relation.target_periods
        assert record.source_period_offset_from_target == relation.source_period_offset_from_target
        assert record.aggregation_op == relation_aggregation_op(relation)
        assert record.legal_refs == relation.legal_refs
        assert record.source_refs == relation.source_refs
        assert record.target_binding_legal_refs == target_binding.legal_refs
        assert record.target_binding_source_refs == target_binding.source_refs


def test_relation_handoff_inventory_is_finite_and_grouped_by_target_revision() -> None:
    """The audit exposes a revision-keyed finite denominator, including zero rows."""
    authority = bundled_authority()
    audit = audit_registry_relation_handoffs(
        authority.modelos,
        authority.catalogues,
        source_root=bundled_path(),
    )

    grouped = audit.by_revision
    declared_revision_keys = {
        (modelo.id, revision.id) for modelo in authority.modelos for revision in modelo.revisions.values()
    }
    assert set(grouped) <= declared_revision_keys
    assert sum(len(rows) for rows in grouped.values()) == audit.relation_count
    assert all(isinstance(record, RelationHandoffRecord) for record in audit.records)
    assert all(record.consumption_channels for record in audit.records)

    alternate = next(
        record for record in audit.records if record.relation_id == "renta-2025-rel-193-retenciones-anuales"
    )
    assert alternate.consumption_channels == ("alternate_binding",)

    formula = next(record for record in audit.records if record.relation_id == "renta-2024-rel-130-pagos-fraccionados")
    assert formula.consumption_channels == ("formula_relation",)


def test_relation_handoff_applicability_measures_period_and_clean_state_contract() -> None:
    """Authority-selected periods preserve active, excluded, and conditional rows."""
    authority = bundled_authority()
    audit = audit_registry_relation_handoff_applicability(authority)

    assert isinstance(audit, RegistryRelationHandoffApplicabilityAudit)

    # Totality against the registry, not against a tally. The expanded row set
    # is the full product of every relation-bearing revision's declared periods
    # and its declared relations, read off the authority the audit consumed; a
    # dropped revision, period or relation moves both sides apart.
    expected_rows = {
        (modelo.id, revision.id, relation.id, period)
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        if revision.relations
        for period in revision.period_selector.periods
        for relation in revision.relations
    }
    assert {
        (record.target_modelo, record.target_revision, record.relation_id, record.target_period)
        for record in audit.records
    } == expected_rows
    assert audit.row_count == len(expected_rows)
    assert audit.active_count + audit.not_applicable_count + audit.unresolved_count == audit.row_count
    assert audit.unresolved_count == 0
    assert all(record.runtime_clean_state == "unmeasured" for record in audit.records)

    # Modelo 200's 2024 span intentionally remains calculation-grade: this
    # audit reads its relation contract, not a filing layout.  Keeping its
    # direct annual-settlement row in the live result proves the audit asks the
    # canonical authority for that truthful grade rather than skipping it.
    modelo_200_202 = next(
        record
        for record in audit.records
        if (
            record.target_modelo,
            record.target_revision,
            record.relation_id,
            record.target_period,
        )
        == (
            "200",
            "2024",
            "modelo-200-2024-rel-202-pagos-fraccionados",
            "0A",
        )
    )
    assert modelo_200_202.source_modelo == "202"
    assert modelo_200_202.applicability == "active"

    # The corpus populates every closed state, so no branch below passes vacuously.
    assert {record.applicability for record in audit.records} == {"active", "not_applicable"}
    assert {record.clean_state_mode for record in audit.records} == {"required", "conditional", "advisory"}

    classifications = {
        (modelo.id, revision.id, classification.source_modelo): classification
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        for classification in revision.dependency_classifications
    }
    for record in audit.records:
        classification = classifications[(record.target_modelo, record.target_revision, record.source_modelo)]
        assert record.taxpayer_files_source == classification.taxpayer_files_source
        assert record.conditional_on_economic_activity == classification.conditional_on_economic_activity
        assert record.dependency_treatment == classification.treatment

        # The clean-state contract is decided by the registry classification: a
        # source the taxpayer does not file can only be advisory, one gated on
        # economic activity is conditional, and everything else is required.
        if not record.taxpayer_files_source:
            assert record.clean_state_mode == "advisory"
        elif record.conditional_on_economic_activity:
            assert record.clean_state_mode == "conditional"
        else:
            assert record.clean_state_mode == "required"

        # Applicability is observable in the source contract it carries, not in
        # a count: an active row resolved a requirement, an excluded row is
        # excluded by the relation's own declared target periods and carries none.
        if record.applicability == "active":
            assert record.source_filing_year is not None
            assert record.requirement_relation_ids
        else:
            assert record.relation_target_periods
            assert record.target_period not in record.relation_target_periods
            assert record.source_filing_year is None
            assert record.source_periods == ()
            assert record.requirement_relation_ids == ()

    m100_2025_193 = next(
        record
        for record in audit.records
        if (
            record.target_modelo,
            record.target_revision,
            record.relation_id,
            record.target_period,
        )
        == (
            "100",
            "2025",
            "renta-2025-rel-193-retenciones-anuales",
            "0A",
        )
    )
    assert m100_2025_193.applicability == "active"
    assert m100_2025_193.source_modelo == "193"
    assert m100_2025_193.source_filing_year == 2025
    assert m100_2025_193.source_periods == ("0A",)
    assert m100_2025_193.clean_state_mode == "advisory"

    m100_2025_130 = next(
        record
        for record in audit.records
        if (
            record.target_modelo,
            record.target_revision,
            record.relation_id,
            record.target_period,
        )
        == (
            "100",
            "2025",
            "renta-2025-rel-130-pagos-fraccionados",
            "0A",
        )
    )
    assert m100_2025_130.applicability == "active"
    assert m100_2025_130.clean_state_mode == "conditional"
    assert m100_2025_130.conditional_on_economic_activity is True
