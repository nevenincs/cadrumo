"""Provider-settings status and the person's credential actions.

The service is bound to one store, itself bound to one exact admitted profile.
It reads every provider in one answer and performs the person's acts:

* set or replace a direct credential (and any base URL);
* choose how the assistant authenticates, without touching a stored key;
* remove, which persists ``disabled`` and so blocks the development fallback;
* reset, which deletes the record and returns the provider to ``unset``.

Every action carries the revision the caller read as its guard and is
committed with a compare-and-swap, then read back. Setting only stores: there
is no remote validation, so a freshly set key reads ``not_verified``.

Registered operations, frontends and the person-act enrolment call this
service; it holds no frontend or transport concern.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime
from enum import StrEnum

from pydantic import SecretStr

from ...core.storage_environment import StorageMode
from ...core.time.clock import now
from ...domain.provider_settings.catalog import (
    CliProgram,
    ProviderCatalogEntry,
    ProviderConsumer,
    validate_https_base_url,
)
from ...domain.provider_settings.record import (
    PROVIDER_SETTINGS_RECORD_SCHEMA_VERSION,
    AssistantAuth,
    CredentialKind,
    CredentialState,
    ProviderCredential,
    ProviderSettingsRecord,
    credential_secret_refusal,
    new_settings_generation,
)
from .contracts import (
    CliState,
    ProviderSettingsActionAccepted,
    ProviderSettingsActionResult,
    ProviderSettingsRefusal,
    ProviderSettingsRefusalCode,
    ProviderSettingsStatus,
    is_provider_settings_revision,
)
from .ports import (
    ProviderCatalogSource,
    ProviderCatalogUnavailableError,
    ProviderRecordRead,
    ProviderSettingsStore,
    StoredProviderRecord,
    StoreRefusal,
    StoreRefusalCode,
    UnreadableProviderRecord,
)
from .resolution import read_revision, status_entry


class AssistantAuthChoice(StrEnum):
    """The assistant-authentication choices a person can make."""

    DIRECT_API = "direct_api"
    PROVIDER_SIGN_IN = "provider_sign_in"


class BaseUrlChange(StrEnum):
    """What a set does with the stored base URL when it is not given a new one."""

    KEEP = "keep"
    CLEAR = "clear"


class ProviderSettingsService:
    """Masked status and guarded credential actions for one admitted profile."""

    def __init__(
        self,
        *,
        store: ProviderSettingsStore,
        catalog_source: ProviderCatalogSource,
        environment: Mapping[str, str],
        storage_mode: StorageMode,
        clock: Callable[[], datetime] = now,
        cli_state_probe: Callable[[CliProgram], CliState] | None = None,
    ) -> None:
        """Bind the service to one profile's store and the process's storage mode."""
        self._store = store
        self._catalog_source = catalog_source
        self._environment = environment
        self._storage_mode = storage_mode
        self._clock = clock
        self._cli_state_probe = cli_state_probe

    def status(self) -> ProviderSettingsStatus | ProviderSettingsRefusal:
        """Return masked status of every catalogued provider, or a typed refusal."""
        try:
            catalog = self._catalog_source.catalog()
        except ProviderCatalogUnavailableError:
            return _refused(ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE)
        reads = self._store.read(catalog.provider_ids)
        if isinstance(reads, StoreRefusal):
            return _refusal_for_store(reads.code)
        return ProviderSettingsStatus(
            development=self._storage_mode is StorageMode.DEVELOPMENT,
            providers=tuple(
                status_entry(
                    entry,
                    read,
                    environment=self._environment,
                    storage_mode=self._storage_mode,
                    cli_state=self._cli_state(entry),
                )
                for entry, read in zip(catalog.providers, reads, strict=True)
            ),
        )

    def set_credential(
        self,
        provider_id: str,
        *,
        secret: SecretStr,
        expected_revision: str,
        base_url: str | BaseUrlChange = BaseUrlChange.KEEP,
    ) -> ProviderSettingsActionResult:
        """Store or replace the provider's direct credential.

        ``base_url`` is tri-state: a URL stores it, ``CLEAR`` reverts to the
        catalog default, and ``KEEP`` keeps whatever URL is stored. Changing
        only the URL still takes the key, so the record is written whole in
        one guarded write. A provider with no default refuses a key that ends
        up without a URL. A provider-sign-in choice for the assistant is
        preserved while the key is stored for direct use.
        """
        entry = self._lane(provider_id)
        if isinstance(entry, ProviderSettingsRefusal):
            return entry
        if not entry.auth_kind.accepts_direct_credential:
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        if credential_secret_refusal(secret.get_secret_value()) is not None:
            return _refused(ProviderSettingsRefusalCode.INVALID_KEY_FORMAT)
        if not isinstance(base_url, BaseUrlChange) and not _base_url_acceptable(entry, base_url):
            return _refused(ProviderSettingsRefusalCode.BASE_URL_REJECTED)
        current = self._current(entry, expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        stored_base_url = _resolved_base_url(current, base_url)
        if stored_base_url is None and entry.auth_kind.accepts_base_url and entry.default_base_url is None:
            return _refused(ProviderSettingsRefusalCode.BASE_URL_REJECTED)
        previous = current.record if isinstance(current, StoredProviderRecord) else None
        assistant_auth = (
            previous.assistant_auth
            if previous is not None and previous.assistant_auth is not AssistantAuth.DISABLED
            else AssistantAuth.DIRECT_API
        )
        record = self._record(
            entry,
            assistant_auth=assistant_auth,
            credential_state=CredentialState.CONFIGURED,
            credential=ProviderCredential(kind=CredentialKind.API_KEY, secret=secret, base_url=stored_base_url),
        )
        return self._commit(entry, record, expected_revision)

    def set_assistant_auth(
        self,
        provider_id: str,
        *,
        choice: AssistantAuthChoice,
        expected_revision: str,
    ) -> ProviderSettingsActionResult:
        """Choose how the assistant authenticates, leaving any stored credential intact."""
        entry = self._lane(provider_id)
        if isinstance(entry, ProviderSettingsRefusal):
            return entry
        if not entry.serves(ProviderConsumer.ASSISTANT):
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        if choice is AssistantAuthChoice.PROVIDER_SIGN_IN and not entry.auth_kind.accepts_provider_sign_in:
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        if choice is AssistantAuthChoice.DIRECT_API and not entry.auth_kind.accepts_direct_credential:
            return _refused(ProviderSettingsRefusalCode.UNKNOWN)
        current = self._current(entry, expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        previous = current.record if isinstance(current, StoredProviderRecord) else None
        record = self._record(
            entry,
            assistant_auth=AssistantAuth(choice.value),
            credential_state=previous.credential_state if previous is not None else CredentialState.UNSET,
            credential=previous.credential if previous is not None else None,
        )
        return self._commit(entry, record, expected_revision)

    def remove_credential(self, provider_id: str, *, expected_revision: str) -> ProviderSettingsActionResult:
        """Persist ``disabled``: the stored credential is dropped and no fallback applies."""
        entry = self._lane(provider_id)
        if isinstance(entry, ProviderSettingsRefusal):
            return entry
        current = self._current(entry, expected_revision)
        if isinstance(current, ProviderSettingsRefusal):
            return current
        record = self._record(
            entry,
            assistant_auth=AssistantAuth.DISABLED,
            credential_state=CredentialState.DISABLED,
            credential=None,
        )
        return self._commit(entry, record, expected_revision)

    def reset(self, provider_id: str, *, expected_revision: str) -> ProviderSettingsActionResult:
        """Delete the provider's record, returning it to ``unset``.

        It also clears an unreadable record, guarded by the revision status
        reported for it.
        """
        entry = self._lane(provider_id)
        if isinstance(entry, ProviderSettingsRefusal):
            return entry
        if not is_provider_settings_revision(expected_revision):
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        refusal = self._store.delete(entry.id, expected_revision=expected_revision)
        if refusal is not None:
            return _refusal_for_store(refusal.code)
        reads = self._store.read((entry.id,))
        if isinstance(reads, StoreRefusal) or isinstance(reads[0], StoredProviderRecord | UnreadableProviderRecord):
            return _refused(ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED)
        return self._accepted(entry, reads[0])

    def _lane(self, provider_id: str) -> ProviderCatalogEntry | ProviderSettingsRefusal:
        """Return the lane the agent reports under ``provider_id``, or the refusal that stopped the lookup."""
        try:
            entry = self._catalog_source.catalog().entry(provider_id)
        except ProviderCatalogUnavailableError:
            return _refused(ProviderSettingsRefusalCode.CATALOG_UNAVAILABLE)
        return _refused(ProviderSettingsRefusalCode.UNKNOWN) if entry is None else entry

    def _current(
        self,
        entry: ProviderCatalogEntry,
        expected_revision: str,
    ) -> ProviderRecordRead | ProviderSettingsRefusal:
        """Read the provider's record and check the caller's guard against it."""
        if not is_provider_settings_revision(expected_revision):
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        reads = self._store.read((entry.id,))
        if isinstance(reads, StoreRefusal):
            return _refusal_for_store(reads.code)
        (read,) = reads
        if read_revision(read) != expected_revision:
            return _refused(ProviderSettingsRefusalCode.REVISION_CONFLICT)
        return read

    def _record(
        self,
        entry: ProviderCatalogEntry,
        *,
        assistant_auth: AssistantAuth,
        credential_state: CredentialState,
        credential: ProviderCredential | None,
    ) -> ProviderSettingsRecord:
        return ProviderSettingsRecord(
            schema_version=PROVIDER_SETTINGS_RECORD_SCHEMA_VERSION,
            provider=entry.id,
            assistant_auth=assistant_auth,
            credential_state=credential_state,
            credential=credential,
            generation=new_settings_generation(),
            updated_at=self._clock(),
        )

    def _commit(
        self,
        entry: ProviderCatalogEntry,
        record: ProviderSettingsRecord,
        expected_revision: str,
    ) -> ProviderSettingsActionResult:
        refusal = self._store.write(record, expected_revision=expected_revision)
        if refusal is not None:
            return _refusal_for_store(refusal.code)
        reads = self._store.read((entry.id,))
        if isinstance(reads, StoreRefusal):
            return _refused(ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED)
        (read,) = reads
        if not isinstance(read, StoredProviderRecord) or read.record.generation != record.generation:
            return _refused(ProviderSettingsRefusalCode.COMMITTED_READBACK_FAILED)
        return self._accepted(entry, read)

    def _cli_state(self, entry: ProviderCatalogEntry) -> CliState | None:
        """Return a cli lane's program state; ``unknown`` until a safe probe is supplied."""
        if not entry.cli_programs:
            return None
        if self._cli_state_probe is None:
            return CliState.UNKNOWN
        # The lane's primary program is the first the agent lists.
        return self._cli_state_probe(entry.cli_programs[0])

    def _accepted(self, entry: ProviderCatalogEntry, read: ProviderRecordRead) -> ProviderSettingsActionAccepted:
        return ProviderSettingsActionAccepted(
            entry=status_entry(
                entry,
                read,
                environment=self._environment,
                storage_mode=self._storage_mode,
                cli_state=self._cli_state(entry),
            ),
        )


def _resolved_base_url(current: ProviderRecordRead, change: str | BaseUrlChange) -> str | None:
    """Return the base URL the new record stores under ``change``."""
    if not isinstance(change, BaseUrlChange):
        return change
    if change is BaseUrlChange.CLEAR or not isinstance(current, StoredProviderRecord):
        return None
    credential = current.record.credential
    return credential.base_url if credential is not None else None


def _base_url_acceptable(entry: ProviderCatalogEntry, base_url: str) -> bool:
    if not entry.auth_kind.accepts_base_url:
        return False
    try:
        validate_https_base_url(base_url)
    except ValueError:
        return False
    return True


def _refused(code: ProviderSettingsRefusalCode) -> ProviderSettingsRefusal:
    return ProviderSettingsRefusal(code=code)


def _refusal_for_store(code: StoreRefusalCode) -> ProviderSettingsRefusal:
    return _refused(ProviderSettingsRefusalCode(code.value))


__all__ = [
    "AssistantAuthChoice",
    "BaseUrlChange",
    "ProviderSettingsService",
]
