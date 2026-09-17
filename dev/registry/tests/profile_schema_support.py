"""Development-only access to the committed user-profile schema."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority_artifact import ProfileCreateContext
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.schema import ModeloDefinition, RegistryCatalogues
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition
from dev.registry.compiler.profile_schema import capture_profile_schema
from dev.registry.compiler.validator import RegistryValidator


def load_user_profile_schema(path: Path | None = None) -> ProfileSchemaDefinition:
    """Capture and parse the profile schema for tests and development checks.

    Production code does not depend on this helper.  Every call captures one
    source path and delegates validation to the development parser, so tests
    exercise the same typed envelope contract as registry compilation.
    """
    source = path or bundled_path("registry", "cadrumo", "user_profile", "schema.toml")
    _payload, schema = capture_profile_schema(source)
    return schema


def profile_creation_context_for_test() -> ProfileCreateContext:
    """Pin the committed schema in the same explicit test authority used by capsule fixtures."""
    from cadrumo.domain.calculations.registry.authority import PinnedAuthorityOperation
    from cadrumo.domain.calculations.registry.authority_artifact import ProfileSchemaComponentQuery
    from cadrumo.domain.calculations.registry.tests.authority_fakes import FakeAuthorityComponentReader

    reader = FakeAuthorityComponentReader({ProfileSchemaComponentQuery(): load_user_profile_schema()})
    operation = PinnedAuthorityOperation(reader, reader.pin())
    return operation.profile_create_context()


class CommittedRegistryValidator:
    """The validator registry compilation builds, scoped as compilation scopes it.

    Compilation validates against the captured profile schema and the bundled
    evidence root, with governed facts resolved from the catalogue under
    validation; a test validating committed modelos needs all three.
    """

    def __init__(self, catalogues: RegistryCatalogues) -> None:
        """Bind the validator and the candidate facts it resolves against.

        A test's catalogues come from a partial loader that does not run the
        fact providers, so the compiled facts stand in for theirs: validation
        checks every provider-owned fact, exactly as compilation does.
        """
        from dev.registry.compiler.authority import compiled_bundled_authority

        compiled = compiled_bundled_authority().catalogues
        facts = compiled.facts
        # The test's own legal and source entries win, so a deliberately
        # mutated declaration is still the one validated.
        completed = catalogues.model_copy(
            update={
                "facts": facts,
                "legal": {**compiled.legal, **catalogues.legal},
                "sources": {**compiled.sources, **catalogues.sources},
            },
        )
        self._validator = RegistryValidator(
            completed,
            source_root=bundled_path(),
            user_profile_schema=load_user_profile_schema(),
        )
        self._facts = CandidateFactAuthority(facts)

    def validate_modelo(self, modelo: ModeloDefinition) -> None:
        """Validate one modelo inside the candidate-fact scope."""
        with validating_governed_facts(self._facts):
            self._validator.validate_modelo(modelo)

    def validate_registry(self, modelos: Iterable[ModeloDefinition]) -> None:
        """Validate every modelo and their relations inside the candidate-fact scope."""
        with validating_governed_facts(self._facts):
            self._validator.validate_registry(modelos)

    def registry_failures(self, modelos: Iterable[ModeloDefinition]) -> tuple[str, ...]:
        """Return candidate findings inside the candidate-fact scope."""
        with validating_governed_facts(self._facts):
            return self._validator.registry_failures(modelos)


def committed_registry_validator(catalogues: RegistryCatalogues) -> CommittedRegistryValidator:
    """Return the scoped validator for committed-registry catalogues."""
    return CommittedRegistryValidator(catalogues)
