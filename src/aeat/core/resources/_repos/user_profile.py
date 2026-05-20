"""UserProfileSchemaRepository: singleton user-profile schema."""

from __future__ import annotations

from .._repository import ResourceCacheRepository


class UserProfileSchemaRepository(ResourceCacheRepository[object, type(None)]):
    """Singleton-keyed repository for the bundled user-profile schema.

    Wraps :func:`aeat.domain.user_profile.load_user_profile_schema`.
    """

    def _load(self, key: None) -> object:
        from ....domain.user_profile import load_user_profile_schema

        return load_user_profile_schema()

    @property
    def singleton(self) -> object:
        return self.get(None)
