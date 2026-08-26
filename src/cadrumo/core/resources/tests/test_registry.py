"""Real-behaviour tests for the resource-management API foundation."""

from __future__ import annotations

from typing import override

import pytest
from pydantic import ValidationError

from .. import (
    ResourceBackendError,
    ResourceCacheRepository,
    ResourceLoadError,
    ResourceNotFoundError,
    ResourceRegistry,
    ResourceRepository,
    ResourceValidationError,
    TypedResourceKey,
    as_path,
    bundled_path,
    packaged_data,
    resources,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_boundary_surface_remains_exported() -> None:
    """The corpus-registry-packaging boundary stays accessible through the package."""

    assert packaged_data is not None
    assert bundled_path is not None
    assert as_path is not None


def test_resources_factory_returns_cached_registry_that_can_be_cleared() -> None:
    """The factory returns a cached registry whose aggregate clear is safe."""

    registry = resources()

    assert isinstance(registry, ResourceRegistry)
    assert registry is resources()
    registry.clear()


class _NamedResourceKey(TypedResourceKey):
    """A test-only key for exercising the Repository contract."""

    name: str

    @override
    def __hash__(self) -> int:
        """Explicit hash to make this class Hashable for type checking."""
        return hash(self.name)


class _UppercaseResourceRepository(ResourceCacheRepository[str, _NamedResourceKey]):
    """A minimal ResourceCacheRepository subclass returning the key's name uppercased."""

    def __init__(self) -> None:
        super().__init__()
        self._load_calls = 0

    @override
    def _load(self, key: _NamedResourceKey) -> str:
        self._load_calls += 1
        return key.name.upper()


def test_repository_identity_map_caches_distinct_keys_and_clear_forces_reload() -> None:
    """Repository get caches by key, separates distinct keys, and clear_cache reloads."""

    repo = _UppercaseResourceRepository()
    alpha = _NamedResourceKey(name="alpha")
    beta = _NamedResourceKey(name="beta")

    first = repo.get(alpha)
    second = repo.get(alpha)

    assert first == "ALPHA"
    assert first is second
    assert repo._load_calls == 1
    assert repo.get(beta) == "BETA"
    assert repo._load_calls == 2

    repo.clear_cache()
    repo.get(alpha)
    assert repo._load_calls == 3


def test_typed_resource_key_is_frozen_and_hashable() -> None:
    """Frozen Pydantic key models are hashable; Identity Map dict use depends on this."""

    a = _NamedResourceKey(name="alpha")
    b = _NamedResourceKey(name="alpha")
    c = _NamedResourceKey(name="beta")

    container = {a: "first"}
    assert container[b] == "first"  # same value -> same hash
    assert c not in container
    with pytest.raises(ValidationError):
        a.__setattr__("name", "beta")


def test_error_hierarchy_subclasses_resource_load_error() -> None:
    """All three failure-mode errors share :class:`ResourceLoadError` as a base."""

    assert issubclass(ResourceNotFoundError, ResourceLoadError)
    assert issubclass(ResourceValidationError, ResourceLoadError)
    assert issubclass(ResourceBackendError, ResourceLoadError)


def test_resource_repository_protocol_recognises_default_base() -> None:
    """A :class:`ResourceCacheRepository` subclass satisfies the :class:`ResourceRepository` protocol."""

    repo = _UppercaseResourceRepository()

    assert isinstance(repo, ResourceRepository)


def test_registry_clear_tolerates_empty_dataclass() -> None:
    """The foundation registry has no Repository fields; clear is a no-op."""

    registry = ResourceRegistry()
    registry.clear()


def test_unimplemented_repository_defaults_raise_not_implemented_error() -> None:
    """Repositories must override _load and all when they expose a finite key space."""

    class _MissingRepo(ResourceCacheRepository[str, _NamedResourceKey]):
        pass

    with pytest.raises(NotImplementedError):
        _MissingRepo().get(_NamedResourceKey(name="x"))

    repo = _UppercaseResourceRepository()

    with pytest.raises(NotImplementedError):
        list(repo.all())


def test_resources_factory_composes_every_repository() -> None:
    """The factory wires every current Repository into the registry."""

    resources.cache_clear()
    registry = resources()

    expected_fields = {
        "apoderamientos",
        "category_profiles",
        "holiday_calendars",
        "manuals",
        "modelos",
        "recargo_bands",
        "topics",
        "iva_catalogues",
        "iva_rate_tables",
    }
    assert set(registry.__dataclass_fields__.keys()) == expected_fields


def test_resources_modelos_repository_loads_real_modelo() -> None:
    """The composed registry's modelos surface backs onto real bundled data."""

    resources.cache_clear()

    modelo = resources().modelos.get("100")

    assert modelo.id == "100"


def test_resources_registry_clear_empties_every_repository() -> None:
    """The aggregate clear() empties every Repository's Identity Map."""

    resources.cache_clear()
    registry = resources()
    registry.modelos.get("100")
    assert registry.modelos._cache != {}

    registry.clear()

    assert registry.modelos._cache == {}
