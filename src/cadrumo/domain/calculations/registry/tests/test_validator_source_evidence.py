"""Real-authority tests for registry source-reference validation."""

from __future__ import annotations

from dataclasses import replace

import pytest

from .....tests.registry_coverage import build_construct_evidence_ledger
from ..authority import ValidatedRegistryAuthority, bundled_authority
from ..errors import RegistryValidationError

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def test_validated_authority_rejects_invalid_source_ref_on_model_copy() -> None:
    """An invalid source id fails through the public validated-authority flow."""
    authority = bundled_authority()
    modelo = authority.modelo("130")
    assert authority.validate_modelo(modelo.id) is modelo

    revision = next(revision for revision in modelo.revisions.values() if revision.formulas)
    formula = revision.formulas[0]
    mutated_formula = formula.model_copy(update={"source_refs": ("s09-invalid-source",)})
    mutated_revision = revision.model_copy(update={"formulas": (mutated_formula, *revision.formulas[1:])})
    mutated_modelo = modelo.model_copy(
        update={"revisions": {**modelo.revisions, revision.id: mutated_revision}},
    )
    mutated_authority: ValidatedRegistryAuthority = replace(
        authority,
        modelos=(mutated_modelo,),
        _modelos_by_id={mutated_modelo.id: mutated_modelo},
        _registry_validated=False,
        _validated_modelos=set(),
        _snapshots={},
    )

    with pytest.raises(
        RegistryValidationError,
        match=r"formula .* references unknown source id 's09-invalid-source'",
    ):
        mutated_authority.validate_modelo(modelo.id)


def test_construct_evidence_classifies_incomplete_model_copy_refs_as_unresolved() -> None:
    """An incomplete construct row remains visible and is marked unresolved."""
    authority = bundled_authority()
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
