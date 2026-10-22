"""AutomationNativeBinding for exact witnessed profile automation custody."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from threading import Lock

from cadrumo_client.contracts.automation_codes import AutomationCustodyCode, AutomationCustodyError

from .....application.user_profile.access_contracts import (
    ProfileAccessBinding,
)
from .....application.user_profile.automation_custody_port import AutomationSecretStore, NativeSecretBackend
from .....application.user_profile.automation_enrollment import EnrollmentControlState
from .....application.user_profile.automation_lifecycle import ProfileGlobalLockState
from .....core.hashing import sha256_hex
from .....core.storage_taxonomy import StorageCategory
from .automation_native_identity import CONTROL_NAMESPACE, automation_native_account
from .change_witness import CustodyChangeWitness, WatchedDirectory
from .paths import profile_custody_path


class AutomationNativeBinding:
    """Own the native custody stages for this capability."""

    def __init__(
        self,
        *,
        root: Path,
        binding: ProfileAccessBinding,
        secrets_store: AutomationSecretStore | None = None,
        secrets_store_factory: Callable[[], AutomationSecretStore] | None = None,
    ) -> None:
        """Bind trusted composition to one local custody owner."""
        if (
            not root.is_absolute()
            or (secrets_store is None) == (secrets_store_factory is None)
            or (secrets_store_factory is not None and not callable(secrets_store_factory))
        ):
            raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
        self.root = root
        self.binding = binding
        self._secrets_lock = Lock()
        self._secrets_store: AutomationSecretStore | None = None
        self._secrets_store_factory = secrets_store_factory
        if secrets_store is not None:
            self.secrets = secrets_store
        self.directory = root / ".automation-v1" / str(binding.installation_id) / str(binding.profile_id)
        self.account = automation_native_account(root, binding.installation_id, binding.profile_id)
        bucket = profile_custody_path(binding.profile_id, StorageCategory.PROFILE_CAPSULE_COMMIT, root=root).parent
        self.custody_witness: CustodyChangeWitness[tuple[ProfileGlobalLockState, EnrollmentControlState]] = (
            CustodyChangeWitness(
                (
                    WatchedDirectory(self.directory, subtree=True),
                    WatchedDirectory(bucket, subtree=False),
                    WatchedDirectory(
                        profile_custody_path(binding.profile_id, StorageCategory.PROFILE_CAPSULE_CUSTODY, root=root),
                        subtree=True,
                    ),
                    WatchedDirectory(
                        profile_custody_path(binding.profile_id, StorageCategory.PROFILE_CAPSULE_DATA, root=root),
                        subtree=True,
                    ),
                ),
                unnotified=self._native_control,
            )
        )

    def _native_control(self) -> str | None:
        """The digest of the control anchor in the native store, which no directory notification covers."""
        anchor = self.secrets.read(CONTROL_NAMESPACE, self.account)
        return None if anchor is None else sha256_hex(anchor.get_secret_value())

    @property
    def secrets(self) -> AutomationSecretStore:
        """Acquire optional native custody only when an automation operation needs it."""
        with self._secrets_lock:
            if self._secrets_store is None:
                factory = self._secrets_store_factory
                if factory is None:
                    raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
                acquired = factory()
                if not isinstance(acquired.backend, NativeSecretBackend):
                    raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
                self._secrets_store = acquired
            return self._secrets_store

    @secrets.setter
    def secrets(self, value: AutomationSecretStore) -> None:
        """Replace the native port supplied by trusted custody composition."""
        with self._secrets_lock:
            if not isinstance(value.backend, NativeSecretBackend):
                raise AutomationCustodyError(AutomationCustodyCode.UNSUPPORTED)
            self._secrets_store = value
