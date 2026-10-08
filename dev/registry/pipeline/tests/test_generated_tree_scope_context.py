"""Candidate revisions retain global role context without borrowing target facts."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts

from ...compiler.authority import compile_validated_authority
from ...compiler.registry_scope import validate_registry_scope
from .._tree_validation import _candidate_scope_modelos
from ..candidate_staging import stage_generated_export_candidate
from ..cli import GeneratedTreeInvocation, check_prepared_invocation, prepare_generated_tree_invocation

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.fixture(scope="module")
def scope_authority(tmp_path_factory) -> ValidatedRegistryAuthority:
    source = bundled_path("registry", "aeat")
    staged = tmp_path_factory.mktemp("scope-source") / "registry/aeat"
    stage_generated_export_candidate(
        source,
        staged,
        modelo="115",
        revision="2019-y-siguientes",
        supporting_modelos={"123"},
    )
    shutil.copytree(
        source / "modelos/115/revisions/2019-y-siguientes/export",
        staged / "modelos/115/revisions/2019-y-siguientes/export",
    )
    return compile_validated_authority(staged, bundled_path())


def _candidate(authority: ValidatedRegistryAuthority):
    source = authority.modelo("123")
    revision = source.revisions["2019-2023"].model_copy(update={"reviewed_by": "candidate-scope-proof"})
    return source.model_copy(update={"revisions": {"2019-2023": revision}})


def test_shared_role_scope_keeps_fresh_candidate_and_other_source_revisions(scope_authority) -> None:
    candidate = _candidate(scope_authority)
    scoped = _candidate_scope_modelos(scope_authority, (candidate,), modelo_id="123", revision_id="2019-2023")
    target = next(modelo for modelo in scoped if str(modelo.id) == "123")
    assert target.revisions["2019-2023"].reviewed_by == "candidate-scope-proof"
    assert target.revisions["2024-y-siguientes"] == scope_authority.modelo("123").revisions["2024-y-siguientes"]
    with validating_governed_facts(
        CandidateFactAuthority(scope_authority.catalogues.facts, scope_authority.supported_filing_years())
    ):
        assert validate_registry_scope(scoped) == ()


def test_source_scope_cannot_hide_a_candidate_role_typo(scope_authority) -> None:
    candidate = _candidate(scope_authority)
    revision = candidate.revisions["2019-2023"]
    original = next(
        casilla for casilla in revision.casillas if casilla.semantic_role == "base_retenciones_ingresos_a_cuenta"
    )
    changed = original.model_copy(update={"semantic_role": "base_retenciones_ingresos_a_cuent"})
    broken = candidate.model_copy(
        update={
            "revisions": {
                "2019-2023": revision.model_copy(
                    update={
                        "casillas": tuple(changed if casilla == original else casilla for casilla in revision.casillas),
                    }
                )
            }
        }
    )
    scoped = _candidate_scope_modelos(scope_authority, (broken,), modelo_id="123", revision_id="2019-2023")
    with validating_governed_facts(
        CandidateFactAuthority(scope_authority.catalogues.facts, scope_authority.supported_filing_years())
    ):
        assert any("base_retenciones_ingresos_a_cuent" in failure for failure in validate_registry_scope(scoped))


def test_scope_refuses_changed_modelo_metadata_and_supporting_facts(scope_authority) -> None:
    candidate = _candidate(scope_authority)
    with pytest.raises(RegistryValidationError, match="modelo metadata"):
        _candidate_scope_modelos(
            scope_authority,
            (candidate.model_copy(update={"source_refs": ()}),),
            modelo_id="123",
            revision_id="2019-2023",
        )
    support = scope_authority.modelo("115")
    altered = support.model_copy(update={"source_refs": ()})
    with pytest.raises(RegistryValidationError, match="supporting modelo facts"):
        _candidate_scope_modelos(scope_authority, (candidate, altered), modelo_id="123", revision_id="2019-2023")


def test_real_123_bootstrap_candidate_uses_validated_shared_role_scope(scope_authority, tmp_path: Path) -> None:
    invocation = GeneratedTreeInvocation("123", "2019-2023", "aeat-dr-123-2019-2023-v13", 2022, "1T")
    prepared = prepare_generated_tree_invocation(invocation, tmp_path, authority=scope_authority)
    state, rendered, _receipt = check_prepared_invocation(prepared)
    assert state == "matched"
    assert prepared.validation.scope_authority is scope_authority
    assert rendered.layout.filing_envelope is not None
