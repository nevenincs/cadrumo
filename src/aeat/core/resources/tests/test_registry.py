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


def test_resources_returns_a_registry() -> None:
    """The factory returns a :class:`ResourceRegistry` instance."""

    registry = resources()

    assert isinstance(registry, ResourceRegistry)


def test_resources_is_cached() -> None:
    """Repeat calls return the identical registry instance."""

    assert resources() is resources()


def test_registry_clear_is_safe_when_empty() -> None:
    """The aggregate :meth:`clear` tolerates the empty foundation registry."""

    resources().clear()


class _DummyKey(TypedResourceKey):
    """A test-only key for exercising the Repository contract."""

    name: str

    @override
    def __hash__(self) -> int:
        """Explicit hash to make this class Hashable for type checking."""
        return hash(self.name)


class _DummyRepository(ResourceCacheRepository[str, _DummyKey]):
    """A minimal ResourceCacheRepository subclass returning the key's name uppercased."""

    def __init__(self) -> None:
        super().__init__()
        self._load_calls = 0

    @override
    def _load(self, key: _DummyKey) -> str:
        self._load_calls += 1
        return key.name.upper()


def test_repository_caches_after_first_load() -> None:
    """A second :meth:`get` for the same key returns the cached value."""

    repo = _DummyRepository()
    key = _DummyKey(name="alpha")

    first = repo.get(key)
    second = repo.get(key)

    assert first == "ALPHA"
    assert first is second
    assert repo._load_calls == 1


def test_repository_loads_distinct_keys_independently() -> None:
    """Distinct keys yield distinct cached values."""

    repo = _DummyRepository()

    assert repo.get(_DummyKey(name="a")) == "A"
    assert repo.get(_DummyKey(name="b")) == "B"
    assert repo._load_calls == 2


def test_repository_clear_cache_forces_reload() -> None:
    """:meth:`clear_cache` empties the Identity Map."""

    repo = _DummyRepository()
    key = _DummyKey(name="alpha")

    repo.get(key)
    repo.clear_cache()
    repo.get(key)

    assert repo._load_calls == 2


def test_typed_resource_key_is_frozen() -> None:
    """Typed keys are frozen so they can serve as Identity Map dict keys."""

    key = _DummyKey(name="alpha")

    with pytest.raises(ValidationError):
        key.name = "beta"  # type: ignore[misc]


def test_typed_resource_key_is_hashable() -> None:
    """Frozen Pydantic key models are hashable; Identity Map dict use depends on this."""

    a = _DummyKey(name="alpha")
    b = _DummyKey(name="alpha")
    c = _DummyKey(name="beta")

    container = {a: "first"}
    assert container[b] == "first"  # same value -> same hash
    assert c not in container


def test_error_hierarchy_subclasses_resource_load_error() -> None:
    """All three failure-mode errors share :class:`ResourceLoadError` as a base."""

    assert issubclass(ResourceNotFoundError, ResourceLoadError)
    assert issubclass(ResourceValidationError, ResourceLoadError)
    assert issubclass(ResourceBackendError, ResourceLoadError)


def test_resource_repository_protocol_recognises_default_base() -> None:
    """A :class:`ResourceCacheRepository` subclass satisfies the :class:`ResourceRepository` protocol."""

    repo = _DummyRepository()

    assert isinstance(repo, ResourceRepository)


def test_registry_clear_tolerates_empty_dataclass() -> None:
    """The foundation registry has no Repository fields; clear is a no-op."""

    registry = ResourceRegistry()
    registry.clear()


def test_unimplemented_repository_get_raises_not_implemented_error() -> None:
    """A ResourceCacheRepository that forgets to override _load raises on first get."""

    class _MissingRepo(ResourceCacheRepository[str, _DummyKey]):
        pass

    with pytest.raises(NotImplementedError):
        _MissingRepo().get(_DummyKey(name="x"))


def test_unimplemented_repository_all_raises_not_implemented_error() -> None:
    """The default :meth:`all` is unsafe; Repositories with a finite key space override."""

    repo = _DummyRepository()

    with pytest.raises(NotImplementedError):
        list(repo.all())


def test_resources_factory_composes_every_repository() -> None:
    """The factory wires all twelve Repositories into the registry."""

    resources.cache_clear()
    registry = resources()

    expected_fields = {
        "apoderamientos",
        "category_profiles",
        "holiday_calendars",
        "legal_parameters",
        "manuals",
        "modelos",
        "normatives",
        "recargo_bands",
        "topics",
        "user_profile_schema",
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
