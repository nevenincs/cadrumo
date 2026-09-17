"""Development-only access to the committed user-profile schema."""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    RegistryCatalogues,
    SupportedFilingYearsCatalogue,
)
from cadrumo.domain.user_profile.schema import ProfileSchemaDefinition
from dev.registry.compiler.loader import load_shared_catalogues
from dev.registry.compiler.profile_schema import capture_profile_schema
from dev.registry.compiler.validator import RegistryValidator


@cache
def committed_supported_filing_years() -> SupportedFilingYearsCatalogue:
    """Return the committed registry's single filing-year support envelope."""
    return load_shared_catalogues(bundled_path("registry", "aeat")).require_supported_filing_years()


AUTHORED_HISTORY_FLOOR = 1972
"""The earliest year any stored governed-fact variant is authored for."""


@cache
def authored_history_supported_filing_years() -> SupportedFilingYearsCatalogue:
    """Return the committed envelope with its floor moved back to the stored history.

    The committed floor gates what the product resolves. Tests that prove the
    authored source itself -- every historical redaction and its exact window --
    resolve the stored variants below that floor, so they use the same horizon
    and ceiling with a floor reaching the oldest stored variant. The floor
    precedes the runtime filing-year type's lower bound, so it is assembled
    without that bound.
    """
    committed = committed_supported_filing_years()
    return SupportedFilingYearsCatalogue.model_construct(
        floor=AUTHORED_HISTORY_FLOOR,
        horizon=committed.horizon,
        hard_ceiling=committed.hard_ceiling,
    )


def load_user_profile_schema(path: Path | None = None) -> ProfileSchemaDefinition:
    """Capture and parse the profile schema for tests and development checks.

    Production code does not depend on this helper.  Every call captures one
    source path and delegates validation to the development parser, so tests
    exercise the same typed envelope contract as registry compilation.
    """
    source = path or bundled_path("registry", "cadrumo", "user_profile", "schema.toml")
    _payload, schema = capture_profile_schema(source)
    return schema


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
        self._facts = CandidateFactAuthority(facts, compiled.require_supported_filing_years())

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
