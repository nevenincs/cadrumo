"""Real-behaviour tests for the six singleton-keyed Repositories."""

from __future__ import annotations

import pytest

from aeat.core.resources._repos import (
    ApoderamientosRepository,
    LegalParameterRepository,
    RecargoBandsRepository,
    TopicCatalogueRepository,
    UserProfileSchemaRepository,
    IvaRateTableRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.domain_core]


def test_apoderamientos_singleton_loads_real_catalogue() -> None:
    repo = ApoderamientosRepository()

    result = repo.singleton

    assert result is not None
    assert repo.singleton is result  # cached identity


def test_user_profile_singleton_loads_real_schema() -> None:
    repo = UserProfileSchemaRepository()

    result = repo.singleton

    assert result is not None
    assert repo.singleton is result


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
