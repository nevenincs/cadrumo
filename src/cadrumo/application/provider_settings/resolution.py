"""Effective provider credentials under one admitted profile.

One precedence serves both masked status and the private resolver, so what a
frontend shows and what a consumer receives cannot disagree:

1. A record that cannot be read refuses; it is never treated as absent.
2. A removed (``disabled``) credential wins over everything, including the
   development environment.
3. For the assistant, a provider-sign-in choice selects the provider's own CLI
   sign-in. It never erases a stored key, which extraction keeps using.
4. A stored key or token wins over the environment.
5. An unset credential falls back to the provider's named Cadrumo setting in
   development storage mode only. Installed builds have no environment path.

The resolver's result carries the secret. It is for in-process consumers
(extraction, the hosted-agent controller) and never for frontend output.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Final

from pydantic import BaseModel, SecretStr

from ...core.config import Settings
from ...core.hex import Hex64Str
from ...core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG as _STRICT_FROZEN_HIDDEN_INPUT
from ...core.storage_environment import StorageMode
from ...domain.provider_settings.catalog import (
    ProviderAuthKind,
    ProviderCatalog,
    ProviderCatalogEntry,
    ProviderConsumer,
    ProviderId,
)
from ...domain.provider_settings.record import (
    AssistantAuth,
    CredentialKind,
    CredentialState,
    ProviderSettingsRecord,
    new_settings_generation,
)
from .contracts import (
    ABSENT_REVISION,
    ProviderCredentialSource,
    ProviderReadiness,
    ProviderSettingsMode,
    ProviderStatusEntry,
    ProviderStatusReason,
)
from .ports import (
    ProviderRecordRead,
    ProviderSettingsStore,
    StoredProviderRecord,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableProviderRecord,
)

_PROCESS_GENERATION: Final[str] = new_settings_generation()
"""Generation for a resolution no record backs: random per process, never key-derived."""


class ProviderCredentialUnavailableReason(StrEnum):
    """Why no credential resolves for a provider and consumer."""

    NOT_SIGNED_IN = "not_signed_in"
    PROFILE_LOCKED = "profile_locked"
    UNKNOWN_PROVIDER = "unknown_provider"
    CONSUMER_NOT_SUPPORTED = "consumer_not_supported"
    PROVIDER_DISABLED = "provider_disabled"
    CREDENTIAL_MISSING = "credential_missing"
    RECORD_UNREADABLE = "record_unreadable"
    UNKNOWN = "unknown"


class ResolvedDirectCredential(BaseModel):
    """A direct key or token a consumer may use. Its repr masks the secret."""

    model_config = _STRICT_FROZEN_HIDDEN_INPUT

    provider: ProviderId
    consumer: ProviderConsumer
    kind: CredentialKind
    secret: SecretStr
    base_url: str | None
    """The effective URL: the stored one, else the catalog default."""
    source: ProviderCredentialSource
    generation: Hex64Str


class ResolvedProviderSignIn(BaseModel):
    """The assistant uses the provider's own CLI sign-in; Cadrumo hands over no secret."""

    model_config = _STRICT_FROZEN

    provider: ProviderId
    consumer: ProviderConsumer
    generation: Hex64Str


class ProviderCredentialUnavailable(BaseModel):
    """No credential resolves, for a typed reason."""

    model_config = _STRICT_FROZEN

    provider: str
    consumer: ProviderConsumer
    reason: ProviderCredentialUnavailableReason


type ProviderCredentialResolution = ResolvedDirectCredential | ResolvedProviderSignIn | ProviderCredentialUnavailable


def provider_mode(read: ProviderRecordRead) -> ProviderSettingsMode:
    """Return the person's chosen mode for one provider."""
    if not isinstance(read, StoredProviderRecord):
        return ProviderSettingsMode.UNSET
    record = read.record
    if record.assistant_auth is AssistantAuth.PROVIDER_SIGN_IN:
        return ProviderSettingsMode.PROVIDER_SIGN_IN
    if record.credential_state is CredentialState.DISABLED or record.assistant_auth is AssistantAuth.DISABLED:
        return ProviderSettingsMode.DISABLED
    if record.credential is not None:
        if record.credential.kind is CredentialKind.OAUTH:
            return ProviderSettingsMode.OAUTH
        return ProviderSettingsMode.KEY
    return ProviderSettingsMode.UNSET


def read_revision(read: ProviderRecordRead) -> str:
    """Return the guard an action must send for this read."""
    if isinstance(read, StoredProviderRecord):
        return read.revision
    if isinstance(read, UnreadableProviderRecord) and read.revision is not None:
        return read.revision
    return ABSENT_REVISION


def _environment_secret(entry: ProviderCatalogEntry, settings: Settings, storage_mode: StorageMode) -> SecretStr | None:
    """Return the development fallback secret, or ``None`` outside development."""
    if storage_mode is not StorageMode.DEVELOPMENT or entry.development_setting is None:
        return None
    if entry.auth_kind.accepts_base_url and entry.default_base_url is None:
        # The environment carries no gateway URL, so such a key could reach nothing.
        return None
    value = getattr(settings, entry.development_setting, None)
    if not isinstance(value, SecretStr) or not value.get_secret_value().strip():
        return None
    return value


def status_entry(
    entry: ProviderCatalogEntry,
    read: ProviderRecordRead,
    *,
    settings: Settings,
    storage_mode: StorageMode,
) -> ProviderStatusEntry:
    """Project one provider's read into masked status."""
    mode = provider_mode(read)
    stored = read.record if isinstance(read, StoredProviderRecord) else None
    available, source, readiness, reason = _availability(
        entry, read, mode, settings=settings, storage_mode=storage_mode
    )
    return ProviderStatusEntry(
        id=entry.id,
        display_name=entry.display_name,
        auth_kind=entry.auth_kind,
        consumers=entry.consumers,
        mode=mode,
        available=available,
        source=source,
        readiness=readiness,
        reason=reason,
        base_url=stored.credential.base_url if stored is not None and stored.credential is not None else None,
        default_base_url=entry.default_base_url,
        revision=read_revision(read),
    )


def _availability(
    entry: ProviderCatalogEntry,
    read: ProviderRecordRead,
    mode: ProviderSettingsMode,
    *,
    settings: Settings,
    storage_mode: StorageMode,
) -> tuple[bool, ProviderCredentialSource, ProviderReadiness, ProviderStatusReason | None]:
    none = ProviderCredentialSource.NONE
    if isinstance(read, UnreadableProviderRecord):
        return False, none, ProviderReadiness.UNUSABLE, ProviderStatusReason.RECORD_UNREADABLE
    if mode is ProviderSettingsMode.DISABLED:
        return False, none, ProviderReadiness.DISABLED, ProviderStatusReason.TURNED_OFF
    if mode is ProviderSettingsMode.PROVIDER_SIGN_IN or entry.auth_kind is ProviderAuthKind.PROVIDER_SIGN_IN_ONLY:
        return True, none, ProviderReadiness.SIGN_IN_REQUIRED, ProviderStatusReason.SIGN_IN_WITH_PROVIDER_TOOL
    if mode in {ProviderSettingsMode.KEY, ProviderSettingsMode.OAUTH}:
        return True, ProviderCredentialSource.PROFILE, ProviderReadiness.NOT_VERIFIED, None
    if _environment_secret(entry, settings, storage_mode) is not None:
        return (
            True,
            ProviderCredentialSource.ENVIRONMENT,
            ProviderReadiness.NOT_VERIFIED,
            None,
        )
    return False, none, ProviderReadiness.MISSING, ProviderStatusReason.NOT_CONFIGURED


class ProviderCredentialResolver:
    """Resolve the effective credential for one provider and consumer.

    Bound to one store, which is itself bound to one exact admitted profile:
    every resolution re-reads the encrypted record through that store, so a
    locked or signed-out profile refuses rather than serving a cached key.
    Never mutates the process-wide settings.
    """

    def __init__(
        self,
        *,
        store: ProviderSettingsStore,
        catalog: ProviderCatalog,
        settings: Settings,
        storage_mode: StorageMode,
    ) -> None:
        """Bind the resolver to one profile's store and the process's storage mode."""
        self._store = store
        self._catalog = catalog
        self._settings = settings
        self._storage_mode = storage_mode

    def resolve(self, provider_id: str, consumer: ProviderConsumer) -> ProviderCredentialResolution:
        """Return the effective credential, the sign-in choice, or a typed unavailability."""
        entry = self._catalog.entry(provider_id)
        if entry is None:
            return _unavailable(provider_id, consumer, ProviderCredentialUnavailableReason.UNKNOWN_PROVIDER)
        if not entry.serves(consumer):
            return _unavailable(provider_id, consumer, ProviderCredentialUnavailableReason.CONSUMER_NOT_SUPPORTED)
        reads = self._store.read((entry.id,))
        if isinstance(reads, StoreRefusal):
            return _unavailable(provider_id, consumer, _unavailable_reason_for_store(reads.code))
        (read,) = reads
        return self._resolve_read(entry, consumer, read)

    def _resolve_read(
        self,
        entry: ProviderCatalogEntry,
        consumer: ProviderConsumer,
        read: ProviderRecordRead,
    ) -> ProviderCredentialResolution:
        if isinstance(read, UnreadableProviderRecord):
            return _unavailable(entry.id, consumer, ProviderCredentialUnavailableReason.RECORD_UNREADABLE)
        record = read.record if isinstance(read, StoredProviderRecord) else None
        if record is not None and record.credential_state is CredentialState.DISABLED:
            if consumer is ProviderConsumer.ASSISTANT and record.assistant_auth is AssistantAuth.PROVIDER_SIGN_IN:
                return ResolvedProviderSignIn(provider=entry.id, consumer=consumer, generation=record.generation)
            return _unavailable(entry.id, consumer, ProviderCredentialUnavailableReason.PROVIDER_DISABLED)
        if consumer is ProviderConsumer.ASSISTANT:
            sign_in = self._assistant_sign_in(entry, record)
            if sign_in is not None:
                return sign_in
            if record is not None and record.assistant_auth is AssistantAuth.DISABLED:
                return _unavailable(entry.id, consumer, ProviderCredentialUnavailableReason.PROVIDER_DISABLED)
        if record is not None and record.credential is not None:
            return ResolvedDirectCredential(
                provider=entry.id,
                consumer=consumer,
                kind=record.credential.kind,
                secret=record.credential.secret,
                base_url=record.credential.base_url or entry.default_base_url,
                source=ProviderCredentialSource.PROFILE,
                generation=record.generation,
            )
        secret = _environment_secret(entry, self._settings, self._storage_mode)
        if secret is None:
            return _unavailable(entry.id, consumer, ProviderCredentialUnavailableReason.CREDENTIAL_MISSING)
        return ResolvedDirectCredential(
            provider=entry.id,
            consumer=consumer,
            kind=CredentialKind.API_KEY,
            secret=secret,
            base_url=entry.default_base_url,
            source=ProviderCredentialSource.ENVIRONMENT,
            generation=_PROCESS_GENERATION,
        )

    @staticmethod
    def _assistant_sign_in(
        entry: ProviderCatalogEntry,
        record: ProviderSettingsRecord | None,
    ) -> ResolvedProviderSignIn | None:
        if record is not None and record.assistant_auth is AssistantAuth.PROVIDER_SIGN_IN:
            return ResolvedProviderSignIn(
                provider=entry.id, consumer=ProviderConsumer.ASSISTANT, generation=record.generation
            )
        if entry.auth_kind is ProviderAuthKind.PROVIDER_SIGN_IN_ONLY and (
            record is None or record.assistant_auth is not AssistantAuth.DISABLED
        ):
            generation = record.generation if record is not None else _PROCESS_GENERATION
            return ResolvedProviderSignIn(provider=entry.id, consumer=ProviderConsumer.ASSISTANT, generation=generation)
        return None


def _unavailable(
    provider_id: str,
    consumer: ProviderConsumer,
    reason: ProviderCredentialUnavailableReason,
) -> ProviderCredentialUnavailable:
    return ProviderCredentialUnavailable(provider=provider_id, consumer=consumer, reason=reason)


def _unavailable_reason_for_store(code: StoreRefusalCode) -> ProviderCredentialUnavailableReason:
    if code is StoreRefusalCode.NOT_SIGNED_IN:
        return ProviderCredentialUnavailableReason.NOT_SIGNED_IN
    if code is StoreRefusalCode.PROFILE_LOCKED:
        return ProviderCredentialUnavailableReason.PROFILE_LOCKED
    return ProviderCredentialUnavailableReason.UNKNOWN


__all__ = [
    "ProviderCredentialResolution",
    "ProviderCredentialResolver",
    "ProviderCredentialUnavailable",
    "ProviderCredentialUnavailableReason",
    "ResolvedDirectCredential",
    "ResolvedProviderSignIn",
    "provider_mode",
    "read_revision",
    "status_entry",
]
