"""Conformance entrypoints acquire facts from their own source candidate."""

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.facts.schema import GovernedFactCatalogue
from cadrumo.domain.calculations.registry.governed_fact_scope import (
    CandidateFactAuthority,
    governed_facts_in_scope,
    outside_governed_fact_validation,
    validating_governed_facts,
)

from ...compiler.authority import compiled_bundled_authority
from ...compiler.loader import load_registry_tree
from .. import manager
from .. import profile as profile_module
from ..profile import audit_bundled_registry_conformance

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@pytest.mark.parametrize("validate", [True, False])
def test_profile_composes_without_ambient_authority(validate: bool) -> None:
    """The real entrypoint works outside the test suite's validation fixture."""
    with outside_governed_fact_validation():
        profile = audit_bundled_registry_conformance(validate=validate)
        assert profile.rows
        assert profile.registry_validated is validate
        assert governed_facts_in_scope() is None


@pytest.mark.parametrize("validate", [True, False])
def test_profile_does_not_borrow_an_unrelated_fact_scope(validate: bool) -> None:
    """An enclosing empty catalogue cannot supply the profile's scope facts."""
    authority = compiled_bundled_authority()
    unrelated = CandidateFactAuthority(GovernedFactCatalogue(), authority.supported_filing_years())
    with validating_governed_facts(unrelated):
        profile = audit_bundled_registry_conformance(validate=validate)
        assert profile.rows
        assert profile.registry_validated is validate
        assert governed_facts_in_scope() is unrelated


def test_report_rereads_changed_candidate_in_the_same_process(monkeypatch: pytest.MonkeyPatch) -> None:
    """A new source review stamp replaces the prior report without a manual cache reset."""
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = modelos[0]
    revision = next(iter(modelo.revisions.values()))
    selected = modelo.model_copy(update={"revisions": {revision.id: revision}})
    monkeypatch.setattr(profile_module, "_load_registry_tree", lambda _root: ((selected,), catalogues))
    monkeypatch.setattr(manager, "_cached_locale_index", lambda: ({}, ()))
    with outside_governed_fact_validation():
        before = manager.load_conformance_report(validate=False)
        changed_revision = revision.model_copy(update={"reviewed_by": "changed-candidate-reviewer"})
        selected = modelo.model_copy(update={"revisions": {revision.id: changed_revision}})
        after = manager.load_conformance_report(validate=False)
    assert before.rows[0].reviewed_by == revision.reviewed_by
    assert after.rows[0].reviewed_by == "changed-candidate-reviewer"
    assert before.rows[0].reviewed_by != after.rows[0].reviewed_by
