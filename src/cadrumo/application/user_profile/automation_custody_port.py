"""Secret-store capabilities for optional automation custody.

Implementations are selected by trusted composition, never by client input or
keyring plugin priority. No operation may prompt, fall back to files or expose
native exception details. Password authentication does not depend on this port.
"""

from contextlib import AbstractContextManager
from enum import StrEnum
from typing import Annotated, Protocol

from pydantic import BaseModel, Field, SecretBytes

from ...core.errors.hierarchy import CadrumoError
from ...core.models import STRICT_FROZEN_HIDDEN_INPUT_CONFIG
from ...core.time.utc import UtcInstant
from .access_contracts import ApiKeyRecord, AutomationGrant, ProfileAccessBinding


class AutomationKeyVerifier(BaseModel):
    """Private persistence operand, never a public key projection."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    key: ApiKeyRecord
    verifier: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")] = Field(repr=False)


class AutomationGrantMaterial(BaseModel):
    """Trusted secret handoff for custody publication, never a frontend operand."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    grant: AutomationGrant = Field(repr=False)
    keys: tuple[AutomationKeyVerifier, ...] = Field(repr=False)
    dek: SecretBytes | None = Field(repr=False)


class AutomationCustodySnapshot(BaseModel):
    """Current application facts without native locators, verifiers or key material."""

    model_config = STRICT_FROZEN_HIDDEN_INPUT_CONFIG
    revision: Annotated[int, Field(ge=1)]
    binding: ProfileAccessBinding
    profile_lock_generation: Annotated[int, Field(ge=0)]
    automation_enabled: bool
    grants: tuple[AutomationGrant, ...]
    keys: tuple[ApiKeyRecord, ...]


class AutomationCustodyPort(Protocol):
    """Application-owned optional custody door, distinct from session admission."""

    def snapshot(self) -> AutomationCustodySnapshot:
        """Reconcile and read verified current control facts."""
        ...

    def publish(
        self,
        *,
        grants: tuple[AutomationGrantMaterial, ...],
        expected_revision: int,
        profile_lock_generation: int,
        automation_enabled: bool,
    ) -> int:
        """Publish reviewed secret custody operands through staged recovery."""
        ...

    def unwrap(self, *, credential: SecretBytes, now: UtcInstant) -> bytearray:
        """Prove possession and return wipeable custody material to its trusted owner."""
        ...

    def unlocked(self, *, credential: SecretBytes, now: UtcInstant) -> AbstractContextManager[bytearray]:
        """Lend verified material to a trusted owner and wipe it on every exit."""
        ...


class AutomationCustodyCode(StrEnum):
    """Credential-free automation custody failures."""

    UNAVAILABLE = "unavailable"
    NEEDS_USER = "needs_user"
    UNSUPPORTED = "unsupported"
    MISSING = "missing"
    INVALID = "invalid"
    CONFLICT = "conflict"
    CREDENTIAL_REJECTED = "credential_rejected"


class AutomationCustodyError(CadrumoError):
    """Safe failure code with no native error or secret-bearing input."""

    def __init__(self, code: AutomationCustodyCode) -> None:
        """Retain only a safe code."""
        self.reason = code
        super().__init__(code.value)


class NativeSecretBackend(StrEnum):
    """The only native facilities eligible for explicit adapter composition."""

    WINDOWS_CREDENTIAL_MANAGER = "windows_credential_manager"
    MACOS_KEYCHAIN = "macos_keychain"
    LINUX_DBUS = "linux_secret_service"


class AutomationSecretStore(Protocol):
    """Non-prompting native store with replacement and verified deletion.

    Missing reads return None. Unavailable/locked/unsupported stores raise a typed
    failure. A failed write may have committed: callers reconcile by reading back.
    Only the production composition may attest the concrete native backend.
    """

    @property
    def backend(self) -> NativeSecretBackend:
        """Identify the explicitly selected native facility."""
        ...

    def read(self, namespace: str, account: str) -> SecretBytes | None:
        """Read a single owned item without prompting."""
        ...

    def replace(self, namespace: str, account: str, value: SecretBytes) -> None:
        """Replace and read-back-verify one item."""
        ...

    def delete(self, namespace: str, account: str) -> None:
        """Delete one owned item and verify absence."""
        ...
