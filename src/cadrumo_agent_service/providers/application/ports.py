"""The persistence ports the provider-settings and model-role services read and write through.

The application owns these contracts; the encrypted secure-object adapters
implement them for one exact admitted profile. Each port speaks in typed values
rather than storage exceptions, so a locked profile, a revision conflict and an
unreadable record each reach the service as a value it must handle, and none of
them can read as an absent record.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol

from pydantic import BaseModel

from cadrumo.core.hex import Hex64Str
from cadrumo.core.models import STRICT_FROZEN_CONFIG as _STRICT_FROZEN
from cadrumo.core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG as _STRICT_FROZEN_HIDDEN_INPUT

from ..domain.catalog import ProviderCatalog, ProviderId
from ..domain.record import ModelRoleSelectionsRecord, ProviderSettingsRecord


class StoredProviderRecord(BaseModel):
    """A present record that decrypted and validated, with its row revision."""

    model_config = _STRICT_FROZEN_HIDDEN_INPUT

    record: ProviderSettingsRecord
    revision: Hex64Str


class AbsentProviderRecord(BaseModel):
    """No record is stored for the provider: both axes are unset."""

    model_config = _STRICT_FROZEN

    provider: ProviderId


class UnreadableProviderRecord(BaseModel):
    """A record is stored but cannot be decrypted or validated.

    It fails closed: it is never treated as absent, and only a guarded reset
    may remove it.
    """

    model_config = _STRICT_FROZEN

    provider: ProviderId
    revision: Hex64Str | None


type ProviderRecordRead = StoredProviderRecord | AbsentProviderRecord | UnreadableProviderRecord


class StoredModelRoleSelections(BaseModel):
    """The per-role selections record decrypted and validated, with its row revision."""

    model_config = _STRICT_FROZEN

    record: ModelRoleSelectionsRecord
    revision: Hex64Str


class AbsentModelRoleSelections(BaseModel):
    """No selections record is stored: no role has a selection."""

    model_config = _STRICT_FROZEN


class UnreadableModelRoleSelections(BaseModel):
    """A selections record is stored but cannot be decrypted or validated.

    It fails closed: no role reads as selected or as unselected, and only a
    guarded reset may remove it.
    """

    model_config = _STRICT_FROZEN

    revision: Hex64Str | None


type ModelRoleSelectionsRead = StoredModelRoleSelections | AbsentModelRoleSelections | UnreadableModelRoleSelections


class StoreRefusalCode(StrEnum):
    """Why the store could not serve a read or a write."""

    NOT_SIGNED_IN = "not_signed_in"
    PROFILE_LOCKED = "profile_locked"
    REVISION_CONFLICT = "revision_conflict"
    UNKNOWN = "unknown"


class StoreRefusal(BaseModel):
    """A typed store refusal carrying no storage detail."""

    model_config = _STRICT_FROZEN

    code: StoreRefusalCode


class StoreGenerations(BaseModel):
    """The current sign-in and provider-settings generations; neither is secret.

    ``sign_in`` changes with every sign-in of the profile; ``provider_settings``
    changes with every committed provider-settings write or deletion.
    """

    model_config = _STRICT_FROZEN

    sign_in: Hex64Str
    provider_settings: Hex64Str


class ProviderCatalogUnavailableReason(StrEnum):
    """Why cadrumo-agent could not report its providers."""

    AGENT_NOT_FOUND = "agent_not_found"
    AGENT_FAILED = "agent_failed"
    AGENT_TIMED_OUT = "agent_timed_out"
    CATALOG_MALFORMED = "catalog_malformed"


class ProviderCatalogUnavailableError(Exception):
    """cadrumo-agent did not report a usable provider catalog; carries only a closed reason."""

    def __init__(self, reason: ProviderCatalogUnavailableReason) -> None:
        """Keep the closed reason."""
        super().__init__(reason.value)
        self.reason = reason


class ProviderCatalogSource(Protocol):
    """Where the provider catalog comes from: cadrumo-agent, at run time.

    There is no stored copy to fall back on. An agent that cannot report its
    providers makes provider settings unavailable.
    """

    def catalog(self) -> ProviderCatalog:
        """Return the catalog the agent reports.

        Raises:
            ProviderCatalogUnavailableError: When the agent cannot be run or its
                document is refused.
        """
        ...


class ProviderSettingsStore(Protocol):
    """Encrypted per-profile provider-settings records for one admitted profile."""

    def read(self, provider_ids: tuple[str, ...]) -> tuple[ProviderRecordRead, ...] | StoreRefusal:
        """Return one read per requested provider, in request order, or a refusal."""
        ...

    def write(self, record: ProviderSettingsRecord, *, expected_revision: str) -> StoreRefusal | None:
        """Commit ``record`` only if the stored revision still equals ``expected_revision``."""
        ...

    def delete(self, provider_id: str, *, expected_revision: str) -> StoreRefusal | None:
        """Remove the provider's record only if its revision still equals ``expected_revision``."""
        ...

    def observe_generations(self) -> StoreGenerations | None:
        """Return the current generations, or ``None`` when the profile is not usable.

        Never extends the session's idle time, so a background observer cannot
        keep a sign-in alive.
        """
        ...


class ModelRoleSelectionsStore(Protocol):
    """The encrypted per-role model selections record of one admitted profile.

    It is a record capability of its own, apart from the provider records, so a
    selection change never moves the provider-settings generation a running
    agent tree was started under.
    """

    def read(self) -> ModelRoleSelectionsRead | StoreRefusal:
        """Return the profile's selections record, absent, or unreadable, or a refusal."""
        ...

    def write(self, record: ModelRoleSelectionsRecord, *, expected_revision: str) -> StoreRefusal | None:
        """Commit ``record`` only if the stored revision still equals ``expected_revision``."""
        ...

    def delete(self, *, expected_revision: str) -> StoreRefusal | None:
        """Remove the record, readable or not, only if its revision still equals ``expected_revision``."""
        ...


__all__ = [
    "AbsentModelRoleSelections",
    "AbsentProviderRecord",
    "ModelRoleSelectionsRead",
    "ModelRoleSelectionsStore",
    "ProviderCatalogSource",
    "ProviderCatalogUnavailableError",
    "ProviderCatalogUnavailableReason",
    "ProviderRecordRead",
    "ProviderSettingsStore",
    "StoreGenerations",
    "StoreRefusal",
    "StoreRefusalCode",
    "StoredModelRoleSelections",
    "StoredProviderRecord",
    "UnreadableModelRoleSelections",
    "UnreadableProviderRecord",
]
