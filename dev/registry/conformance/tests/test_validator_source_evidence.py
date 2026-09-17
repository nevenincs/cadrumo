"""Real-authority tests for registry source-reference validation."""

from __future__ import annotations

import pytest

from cadrumo.domain.calculations.registry.errors import RegistryValidationError

from ...compiler.authority import compiled_bundled_authority
from ...tests.profile_schema_support import committed_registry_validator
from ..coverage import build_construct_evidence_ledger

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_compiler_validation_rejects_invalid_source_ref_on_model_copy() -> None:
    """An invalid source id fails the compiler validation that admits a candidate.

    The runtime authority consumes already-validated material and does not
    revalidate, so the refusal belongs to the development compiler.
    """
    authority = compiled_bundled_authority()
    modelo = authority.modelo("130")

    revision = next(revision for revision in modelo.revisions.values() if revision.formulas)
    formula = revision.formulas[0]
    mutated_formula = formula.model_copy(update={"source_refs": ("s09-invalid-source",)})
    mutated_revision = revision.model_copy(update={"formulas": (mutated_formula, *revision.formulas[1:])})
    mutated_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: mutated_revision}},
    )
    validator = committed_registry_validator(authority.catalogues)
    validator.validate_modelo(modelo)

    with pytest.raises(
        RegistryValidationError,
        match=r"formula .* references unknown source id 's09-invalid-source'",
    ):
        validator.validate_modelo(mutated_modelo)


def test_construct_evidence_classifies_incomplete_model_copy_refs_as_unresolved() -> None:
    """An incomplete construct row remains visible and is marked unresolved."""
    authority = compiled_bundled_authority()
    snapshot = authority.snapshot("130", filing_year=2026, period="1T")
    formula = snapshot.revision.formulas[0]
    mutated_formula = formula.model_copy(update={"source_refs": ()})
    mutated_revision = snapshot.revision.model_copy(
        update={"formulas": (mutated_formula, *snapshot.revision.formulas[1:])},
    )
    mutated_snapshot = snapshot.model_copy(update={"revision": mutated_revision})

    ledger = build_construct_evidence_ledger(mutated_snapshot)
    row = next(row for row in ledger.rows if row.kind == "formula" and row.construct_id == formula.id)

    assert row.status == "unresolved"
    assert row.legal_refs == formula.legal_refs
    assert row.source_refs == ()
    assert row in ledger.gaps
