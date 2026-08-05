"""Real-registry proofs for the conformance provenance projection."""

from __future__ import annotations

import pytest

from ....domain.calculations.registry import ValidatedRegistryAuthority, bundled_authority
from .. import RegistryConformanceProfile, audit_bundled_registry_conformance

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.fixture(scope="module")
def validated_profile() -> RegistryConformanceProfile:
    """Compose the shipped profile through the validating authority."""
    return audit_bundled_registry_conformance()


@pytest.fixture(scope="module")
def degraded_profile() -> RegistryConformanceProfile:
    """Compose the shipped profile through the non-validating loader."""
    return audit_bundled_registry_conformance(validate=False)


@pytest.fixture(scope="module")
def registry_authority() -> ValidatedRegistryAuthority:
    """Use the real bundled authority to resolve each projected revision."""
    return bundled_authority()


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
        assert row.construct_evidence.gaps == ()

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
