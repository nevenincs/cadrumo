"""Real-behaviour tests for StaticModeloRepository."""

from __future__ import annotations

import pytest

from ...errors import ResourceNotFoundError
from ..modelos import StaticModeloRepository

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_modelo_repository_loads_real_modelos_and_caches_authority() -> None:
    repo = StaticModeloRepository()

    modelo = repo.get("100")
    modelo_again = repo.get("100")
    modelos = repo.all()
    authority = repo.authority

    assert modelo.id == "100"
    assert modelo is modelo_again  # Identity Map cached
    assert len(modelos) > 0
    ids = {m.id for m in modelos}
    assert "100" in ids
    assert "303" in ids
    assert authority is not None
    assert authority is repo.authority  # cached


def test_modelo_repository_unknown_id_raises_resource_not_found() -> None:
    repo = StaticModeloRepository()

    with pytest.raises(ResourceNotFoundError):
        repo.get("999999")


def test_modelo_repository_clear_cache_resets_authority_and_identity_map() -> None:
    repo = StaticModeloRepository()
    repo.get("100")

    repo.clear_cache()

    assert repo._cache == {}
    assert repo._authority is None
