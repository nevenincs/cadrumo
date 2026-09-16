"""Look up secure-object namespace definitions for tests."""

from __future__ import annotations

from ..namespace_registry import STORAGE_NAMESPACE_REGISTRY
from ..secure_object_namespaces import SecureObjectNamespaceDefinition


def lookup_namespace_definition(key: str) -> SecureObjectNamespaceDefinition:
    """Return the registered namespace definition whose registry key is ``key``."""
    for namespace in STORAGE_NAMESPACE_REGISTRY.namespaces:
        if namespace.key == key:
            return namespace
    raise KeyError(key)
