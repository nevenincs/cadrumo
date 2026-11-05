"""The registry carrying the known secure-storage hierarchy contracts."""

from __future__ import annotations

from pydantic import BaseModel, model_validator

from ....core.errors.hierarchy import pydantic_validation_boundary
from ....core.models import STRICT_FROZEN_CONFIG
from ....core.storage_taxonomy import StorageCustodyProfile
from .errors import NamespaceRegistryError
from .namespace_taxonomy import CUSTODY_PROFILE_DISPOSITIONS
from .secure_object_namespaces import SecureObjectNamespaceDefinition, pydantic_namespace_validator
from .storage_path_definitions import StoragePathDefinition


class StorageHierarchyRegistry(BaseModel):
    """Registry carrying the known secure-storage hierarchy contracts."""

    model_config = STRICT_FROZEN_CONFIG

    namespaces: tuple[SecureObjectNamespaceDefinition, ...]
    paths: tuple[StoragePathDefinition, ...]

    @model_validator(mode="after")
    @pydantic_namespace_validator
    @pydantic_validation_boundary
    def _reject_duplicate_keys_and_namespaces(self) -> StorageHierarchyRegistry:
        namespace_keys = [item.key for item in self.namespaces]
        namespace_values = [item.namespace for item in self.namespaces]
        path_keys = [item.key for item in self.paths]
        if len(namespace_keys) != len(set(namespace_keys)):
            raise NamespaceRegistryError("duplicate secure-object namespace registry key")
        if len(namespace_values) != len(set(namespace_values)):
            raise NamespaceRegistryError("duplicate secure-object namespace value")
        if len(path_keys) != len(set(path_keys)):
            raise NamespaceRegistryError("duplicate storage path registry key")
        return self

    def namespace_by_value(self, value: str) -> SecureObjectNamespaceDefinition:
        """Return a :class:`SecureObjectNamespaceDefinition` by persisted namespace value."""
        for namespace in self.namespaces:
            if namespace.namespace == value:
                return namespace
        raise KeyError(value)

    def path_by_key(self, key: str) -> StoragePathDefinition:
        """Return a :class:`StoragePathDefinition` by registry key."""
        for path in self.paths:
            if path.key == key:
                return path
        raise KeyError(key)

    def namespaces_for_custody_profile(
        self,
        profile: StorageCustodyProfile,
    ) -> tuple[SecureObjectNamespaceDefinition, ...]:
        """Return carried :class:`SecureObjectNamespaceDefinition` rows for a custody profile."""
        dispositions = CUSTODY_PROFILE_DISPOSITIONS[profile]
        return tuple(namespace for namespace in self.namespaces if namespace.custody_disposition in dispositions)
