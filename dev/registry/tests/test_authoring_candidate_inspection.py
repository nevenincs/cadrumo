"""Pre-publication inspection remains diagnostic and source-backed."""

from __future__ import annotations

import pytest

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry import authority as runtime_authority
from cadrumo.domain.calculations.registry.errors import RegistryValidationError
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts

from ..compiler.authority import AuthoringCandidateInspection, inspect_authoring_candidate
from ..compiler.validator import RegistryValidator

pytestmark = [pytest.mark.integration, pytest.mark.hex_domain]


@pytest.fixture(scope="module")
def inspected_live_candidate() -> AuthoringCandidateInspection:
    return inspect_authoring_candidate(bundled_path("registry", "aeat"), bundled_path())


def test_inspection_does_not_require_a_published_pointer() -> None:
    inspected_live_candidate = inspect_authoring_candidate(bundled_path("registry", "aeat"), bundled_path())

    assert inspected_live_candidate.publication_valid
    assert inspected_live_candidate.findings == ()
    assert inspected_live_candidate.registry_fingerprint
    assert inspected_live_candidate.source_evidence_fingerprint
    assert not isinstance(inspected_live_candidate.components, runtime_authority.ValidatedRegistryAuthority)


def test_unresolved_inspected_candidate_still_fails_publication_validation(
    inspected_live_candidate: AuthoringCandidateInspection,
) -> None:
    components = inspected_live_candidate.components
    modelo = next(item for item in components.modelos if item.id == "100")
    revision = modelo.revisions["2025"]
    casillas = tuple(
        item.model_copy(update={"continuidad_id": None}) if str(item.id) == "0456" else item
        for item in revision.casillas
    )
    revisions = dict(modelo.revisions)
    revisions["2025"] = revision.model_copy(update={"casillas": casillas})
    mutated = modelo.model_copy(update={"revisions": revisions})
    modelos = tuple(mutated if item.id == "100" else item for item in components.modelos)
    validator = RegistryValidator(
        components.catalogues,
        source_root=bundled_path(),
        user_profile_schema=components.profile_schema,
        source_evidence_fingerprint=inspected_live_candidate.source_evidence_fingerprint,
    )

    with validating_governed_facts(CandidateFactAuthority(components.catalogues.facts)):
        findings = validator.registry_failures(modelos)
        with pytest.raises(RegistryValidationError, match="registry validation failed"):
            validator.validate_registry(modelos)

    assert any("0456" in finding for finding in findings)
