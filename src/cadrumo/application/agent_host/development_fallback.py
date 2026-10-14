"""Development mode's environment fallback for a provider whose profile record holds no credential.

The profile worker resolves every stored record, but it is started without
Cadrumo's provider settings in its environment, so it cannot apply the
fallback itself. It names the providers whose record is unset and does not
block the fallback; the runtime then applies that last step of the one
resolution precedence here, against a record known to be unset. In an
installed build the precedence has no environment path, so nothing resolves.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import override

from ...core.storage_environment import StorageMode
from ...domain.provider_settings.catalog import ProviderConsumer
from ...domain.provider_settings.record import ProviderSettingsRecord
from ..provider_settings.ports import (
    AbsentProviderRecord,
    ProviderCatalogSource,
    ProviderRecordRead,
    ProviderSettingsStore,
    StoreRefusal,
    StoreRefusalCode,
)
from ..provider_settings.resolution import ProviderCredentialResolver, ResolvedDirectCredential


class _UnsetRecords(ProviderSettingsStore):
    """Records the worker reported unset: every read is absent, and nothing can be written."""

    @override
    def read(self, provider_ids: tuple[str, ...]) -> tuple[ProviderRecordRead, ...] | StoreRefusal:
        return tuple(AbsentProviderRecord(provider=provider_id) for provider_id in provider_ids)

    @override
    def write(self, record: ProviderSettingsRecord, *, expected_revision: str) -> StoreRefusal | None:
        return StoreRefusal(code=StoreRefusalCode.UNKNOWN)

    @override
    def delete(self, provider_id: str, *, expected_revision: str) -> StoreRefusal | None:
        return StoreRefusal(code=StoreRefusalCode.UNKNOWN)

    @override
    def observe_generations(self) -> None:
        """The absent-only store owns no profile generations."""
        return None


def development_fallback(
    provider_id: str,
    *,
    catalog_source: ProviderCatalogSource,
    environment: Mapping[str, str],
    storage_mode: StorageMode,
) -> ResolvedDirectCredential | None:
    """Return the assistant credential the fallback supplies for an unset provider, or ``None``."""
    resolved = ProviderCredentialResolver(
        store=_UnsetRecords(), catalog_source=catalog_source, environment=environment, storage_mode=storage_mode
    ).resolve(provider_id, ProviderConsumer.ASSISTANT)
    return resolved if isinstance(resolved, ResolvedDirectCredential) else None
