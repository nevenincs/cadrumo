"""UserProfileSchemaRepository: singleton :class:`ProfileSchemaDefinition`."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ....domain.user_profile.schema import ProfileSchemaDefinition


class UserProfileSchemaRepository(ResourceCacheRepository["ProfileSchemaDefinition", None]):
    """Singleton-keyed repository for the bundled user-profile schema.

    Wraps :func:`cadrumo.domain.user_profile.loader.load_user_profile_schema`
    and returns the :class:`ProfileSchemaDefinition` aggregate.
    """

    @override
    def _load(self, key: None) -> ProfileSchemaDefinition:
        from ....domain.user_profile.loader import load_user_profile_schema

        return load_user_profile_schema()

    @property
    def singleton(self) -> ProfileSchemaDefinition:
        schema: ProfileSchemaDefinition = self.get(None)
        return schema
