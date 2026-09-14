"""In-memory apoderado persistence for application service tests."""

from __future__ import annotations

from ....core.config import Settings
from ....core.identity.bucket import canonical_bucket_id
from ..apoderado_repository import ApoderadoConfigurationRepository
from ..apoderado_service import ApoderadoConfiguration


class InMemoryApoderadoConfigurationRepository(ApoderadoConfigurationRepository):
    """One bucket-bound in-memory implementation of the application port."""

    def __init__(self, *, bucket_id: str, records: dict[str, ApoderadoConfiguration]) -> None:
        self._bucket_id = canonical_bucket_id(bucket_id)
        self._records = records

    def load(self) -> ApoderadoConfiguration | None:
        return self._records.get(self._bucket_id)

    def save(self, configuration: ApoderadoConfiguration) -> None:
        self._records[self._bucket_id] = configuration

    def delete(self) -> bool:
        return self._records.pop(self._bucket_id, None) is not None


class InMemoryApoderadoConfigurationRepositoryFactory:
    """Explicit factory that records routed settings for service tests."""

    def __init__(self) -> None:
        self.records: dict[str, ApoderadoConfiguration] = {}
        self.settings_by_bucket: dict[str, Settings] = {}
        self.calls: list[str] = []

    def __call__(self, *, bucket_id: str, settings: Settings) -> ApoderadoConfigurationRepository:
        canonical_id = canonical_bucket_id(bucket_id)
        self.calls.append(canonical_id)
        self.settings_by_bucket[canonical_id] = settings
        return InMemoryApoderadoConfigurationRepository(bucket_id=canonical_id, records=self.records)


__all__ = [
    "InMemoryApoderadoConfigurationRepository",
    "InMemoryApoderadoConfigurationRepositoryFactory",
]
