"""Development-only access to the committed user-profile schema."""

from __future__ import annotations

from collections.abc import Iterable
from functools import cache
from pathlib import Path

from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import ValidatedRegistryAuthority
from cadrumo.domain.calculations.registry.governed_fact_scope import CandidateFactAuthority, validating_governed_facts
from cadrumo.domain.calculations.registry.schema import (
    ModeloDefinition,
    ModeloRevision,
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


@cache
def authored_history_floor() -> int:
    """Return the earliest coordinate the committed corpus authors anything for.

    DERIVED, never pinned. A hand-written year here is a second, unverified
    declaration of the corpus's own reach: it is correct only until someone
    authors an older variant or retires the oldest one, and nothing fails when
    it stops being correct -- the escape hatch simply stops reaching the source
    it exists to reach, silently. Reading the floor off the compiled corpus
    makes it true by construction.

    Both authored axes count. A governed-fact variant opens on a date, a modelo
    revision on a filing year, and the authored history is the earlier of the
    two.
    """
    from ..compiler.authority import compiled_bundled_authority

    authority = compiled_bundled_authority()
    years = {
        variant.valid_from.year
        for fact in authority.catalogues.facts.facts.values()
        for variant in fact.variants
        if variant.valid_from is not None
    }
    years.update(
        year
        for modelo in authority.modelos
        for revision in modelo.revisions.values()
        for year in _authored_selector_years(revision)
    )
    if not years:
        raise AssertionError("the committed corpus authors no temporal coordinate at all")
    return min(years)


def _authored_selector_years(revision: ModeloRevision) -> tuple[int, ...]:
    """Return the explicitly authored lower coordinates of one revision selector."""
    selector = revision.period_selector
    if selector.years:
        return selector.years
    return () if selector.year_from is None else (selector.year_from,)


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
        floor=authored_history_floor(),
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


def _overlay_is_inert(catalogues: RegistryCatalogues, compiled: RegistryCatalogues) -> bool:
    """Whether overlaying ``catalogues`` onto ``compiled`` would change nothing.

    Compared by object identity per entry, which is what the authority's own
    catalogues satisfy and a mutated fixture does not: a fixture that replaced
    one declaration carries a different object for it and takes the copy path.
    """
    if catalogues is compiled:
        return True
    return all(compiled.legal.get(key) is value for key, value in catalogues.legal.items()) and all(
        compiled.sources.get(key) is value for key, value in catalogues.sources.items()
    )


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
        # A caller validating the committed corpus unchanged gets the
        # authority's OWN catalogues, not a copy of them. The validator memoizes
        # per catalogue object, so a copy that overlays nothing still guaranteed
        # a miss and re-validated the corpus the authority had just validated.
        if _overlay_is_inert(catalogues, compiled):
            completed = compiled
        else:
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


@cache
def authored_history_authority() -> ValidatedRegistryAuthority:
    """Return the compiled authority scoped to the AUTHORED history, not the filing span.

    The committed envelope gates what the product resolves, so a governed-fact
    query below its floor is refused for being out of support. A case whose
    subject IS the authored source of an older ejercicio has to reach those
    stored variants, and it reaches them through the authority it resolves
    against: an ambient scope alone does not widen an authority handed to a
    resolution context.
    """
    from dataclasses import replace

    from ..compiler.authority import compiled_bundled_authority

    authority = compiled_bundled_authority()
    return replace(
        authority,
        catalogues=authority.catalogues.model_copy(
            update={"supported_filing_years": authored_history_supported_filing_years()}
        ),
        _snapshots={},
    )
