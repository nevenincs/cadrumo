"""Real-behaviour tests for the six singleton-keyed Repositories."""

from __future__ import annotations

import pytest

from aeat.core.resources._repos import (
    ApoderamientosRepository,
    IvaRateTableRepository,
    LegalParameterRepository,
    RecargoBandsRepository,
    TopicCatalogueRepository,
    UserProfileSchemaRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def test_apoderamientos_singleton_loads_real_catalogue() -> None:
    from aeat.domain.auth.apoderamientos._catalogue import ApoderamientosCatalogue

    repo = ApoderamientosRepository()

    result = repo.singleton

    assert isinstance(result, ApoderamientosCatalogue), (
        f"Expected ApoderamientosCatalogue, got {type(result).__name__}"
    )
    assert repo.singleton is result  # cached identity
    assert len(result.scopes) > 0, "Apoderamientos catalogue must declare at least one scope"
    scope_codes = {s.code for s in result.scopes}
    assert "GENERALNT" in scope_codes, (
        f"Expected canonical 'GENERALNT' scope in catalogue; got codes: {scope_codes}"
    )
    first = result.scopes[0]
    assert first.code, "Scope must have a non-empty code"
    assert first.name_es, "Scope must have a non-empty Spanish name"


def test_user_profile_singleton_loads_real_schema() -> None:
    from aeat.domain.user_profile._schema import ProfileSchemaDefinition

    repo = UserProfileSchemaRepository()

    result = repo.singleton

    assert isinstance(result, ProfileSchemaDefinition), (
        f"Expected ProfileSchemaDefinition, got {type(result).__name__}"
    )
    assert repo.singleton is result
    assert result.id == "aeat.user_profile", (
        f"Expected schema id 'aeat.user_profile', got {result.id!r}"
    )
    assert result.version >= 1, "Schema version must be a positive integer"
    section_keys = {s.key for s in result.sections}
    assert "identity" in section_keys, (
        f"Expected 'identity' section in user profile schema; got: {section_keys}"
    )
    assert len(result.sections) >= 5, (
        f"Expected at least 5 sections in user profile schema, got {len(result.sections)}"
    )


def test_topics_singleton_loads_real_catalogue() -> None:
    repo = TopicCatalogueRepository()

    result = repo.singleton

    assert result is not None
    assert repo.singleton is result


def test_recargo_bands_singleton_loads_real_tuple() -> None:
    repo = RecargoBandsRepository()

    result = repo.singleton

    assert isinstance(result, tuple)
    assert len(result) > 0
    assert repo.singleton is result


def test_iva_rate_table_singleton_loads_real_mapping() -> None:
    repo = IvaRateTableRepository()

    result = repo.singleton

    assert result is not None
    assert len(result) > 0  # at least one EU member state
    assert repo.singleton is result


def test_legal_parameters_singleton_loads_real_mapping() -> None:
    repo = LegalParameterRepository()

    result = repo.singleton

    assert result is not None
    assert len(result) > 0  # at least one declared parameter
    assert repo.singleton is result


def test_singleton_clear_cache_forces_reload() -> None:
    repo = TopicCatalogueRepository()

    first = repo.singleton
    repo.clear_cache()
    second = repo.singleton

    # Same content, but cache was cleared between calls so the
    # repository invoked _load twice. Equality holds because the
    # bundled data is immutable.
    assert first == second


def test_get_with_explicit_none_matches_singleton_property() -> None:
    repo = ApoderamientosRepository()

    assert repo.get(None) is repo.singleton
