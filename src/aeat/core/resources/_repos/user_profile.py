"""UserProfileSchemaRepository: singleton user-profile schema."""

from __future__ import annotations

from typing import TYPE_CHECKING, override

from .._repository import ResourceCacheRepository

if TYPE_CHECKING:
    from ....domain.user_profile import ProfileSchemaDefinition


class UserProfileSchemaRepository(ResourceCacheRepository["ProfileSchemaDefinition", None]):
    """Singleton-keyed repository for the bundled user-profile schema.

    Wraps :func:`aeat.domain.user_profile.load_user_profile_schema`.
    """

    @override
    def _load(self, key: None) -> ProfileSchemaDefinition:
        from ....domain.user_profile import load_user_profile_schema

        return load_user_profile_schema()

    @property
    def singleton(self) -> ProfileSchemaDefinition:
        schema: ProfileSchemaDefinition = self.get(None)
        return schema
