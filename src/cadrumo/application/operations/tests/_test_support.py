"""Shared scaffolding for the operations supervisor test suite."""

from __future__ import annotations

from ....adapters.persistence.storage import (
    SecureObjectNamespaceDefinition,
    SecureObjectRepository,
    StorageHierarchyRegistry,
)


def registered_objects(
    profile_objects: SecureObjectRepository,
    namespace: SecureObjectNamespaceDefinition,
) -> SecureObjectRepository:
    """Register `namespace` on the genuine active-profile repository."""
    registry = profile_objects.namespace_registry
    assert registry is not None
    return SecureObjectRepository(
        engine=profile_objects.engine,
        namespace_registry=StorageHierarchyRegistry(
            namespaces=(*registry.namespaces, namespace),
            paths=registry.paths,
        ),
    )
