"""Register a test-only namespace onto a real active-profile repository.

Two independent test suites -- one in ``application.operations.tests``, one
in ``adapters.persistence.operations.tests`` -- each needed to bind a real
:class:`~adapters.persistence.storage.SecureObjectRepository` to a registry
that additionally carries the suite's own bespoke namespace, so a real
round-trip test can write into it. Both wrote the exact same rebind, closing
over their own module-level namespace constant. Neither package may reach
into the other's private test module, and the concept itself is not
"operations"-specific -- any suite exercising a real profile repository
against a namespace the shipped registry does not already carry needs the
same rebind -- so it lives here rather than in either package's private
scaffolding.
"""

from __future__ import annotations

from ..adapters.persistence.storage._secure_object_namespaces import (
    SecureObjectNamespaceDefinition,
    StorageHierarchyRegistry,
)
from ..adapters.persistence.storage.sql.secure_objects import SecureObjectRepository

__all__ = ["registered_objects"]


def registered_objects(
    profile_objects: SecureObjectRepository,
    namespace: SecureObjectNamespaceDefinition,
) -> SecureObjectRepository:
    """Register `namespace` on the genuine active-profile repository.

    Args:
        profile_objects: The real repository bound to the test's isolated
            profile, whose engine and existing namespaces are preserved.
        namespace: The caller's own test-only namespace to add.

    Returns:
        A repository over the SAME engine, with `namespace` additionally
        registered.
    """
    registry = profile_objects.namespace_registry
    assert registry is not None
    return SecureObjectRepository(
        engine=profile_objects.engine,
        namespace_registry=StorageHierarchyRegistry(
            namespaces=(*registry.namespaces, namespace),
            paths=registry.paths,
        ),
    )
