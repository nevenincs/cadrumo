"""Real-behaviour tests for the six singleton-keyed Repositories."""

from __future__ import annotations

import pytest

from .. import (
    ApoderamientosRepository,
    IvaRateTableRepository,
    LegalParameterRepository,
    RecargoBandsRepository,
    TopicCatalogueRepository,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_apoderamientos_singleton_loads_real_catalogue() -> None:
    from .....domain.auth.apoderamientos import ApoderamientosCatalogue

    repo = ApoderamientosRepository()

    result = repo.singleton

    assert isinstance(result, ApoderamientosCatalogue), f"Expected ApoderamientosCatalogue, got {type(result).__name__}"
    assert repo.singleton is result  # cached identity
    assert repo.get(None) is result
    assert len(result.scopes) > 0, "Apoderamientos catalogue must declare at least one scope"
    scope_codes = {s.code for s in result.scopes}
    assert "GENERALNT" in scope_codes, f"Expected canonical 'GENERALNT' scope in catalogue; got codes: {scope_codes}"
    first = result.scopes[0]
    assert first.code, "Scope must have a non-empty code"
    assert first.name_es, "Scope must have a non-empty Spanish name"


def test_topics_singleton_loads_real_catalogue() -> None:
    from ....topics import TopicCatalogue

    repo = TopicCatalogueRepository()

    result = repo.singleton

    assert isinstance(result, TopicCatalogue), f"Expected TopicCatalogue, got {type(result).__name__}"
    assert len(result.topics) > 0, "Topic catalogue must contain at least one topic"
    assert repo.singleton is result  # cached identity

    repo.clear_cache()
    reloaded = repo.singleton

    # Same content, but cache was cleared between calls so the repository invoked
    # _load twice. Equality holds because the bundled data is immutable.
    assert reloaded == result


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
    from .....domain.calculations.registry import LegalParameter

    repo = LegalParameterRepository()

    result = repo.singleton

    assert len(result) > 0, "Legal parameter mapping must contain at least one entry"
    first_key, first_value = next(iter(result.items()))
    assert isinstance(first_key, str) and first_key, "Mapping keys must be non-empty strings"
    assert isinstance(first_value, LegalParameter), (
        f"Mapping values must be LegalParameter, got {type(first_value).__name__}"
    )
    assert repo.singleton is result  # cached identity
