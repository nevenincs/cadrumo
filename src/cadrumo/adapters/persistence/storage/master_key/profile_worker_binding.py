"""One immutable profile/root target for the lifetime of a runtime worker."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock

from .....application.runtime.profile_worker import ProfileWorkerIdentity
from .....application.user_profile.automation_custody_port import AutomationCustodyCode, AutomationCustodyError
from .bucket_session import BucketSession


@dataclass(frozen=True)
class ProfileWorkerBinding:
    """The process target persists when its last live custody session closes."""

    identity: ProfileWorkerIdentity
    storage_root: Path
    root_device: int
    root_inode: int


class ProfileWorkerBindingOwner:
    """A single-assignment owner; no reset or scoped override can retarget it."""

    def __init__(self) -> None:
        """Start without a worker target; construction admits no custody."""
        self._binding: ProfileWorkerBinding | None = None
        self._lock = RLock()

    def bind(self, identity: ProfileWorkerIdentity, *, storage_root: Path) -> None:
        """Pin an exact physical root and identity, refusing any later retargeting."""
        if not storage_root.is_absolute():
            raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        try:
            target = storage_root.resolve(strict=True)
            if not target.is_dir():
                raise AutomationCustodyError(AutomationCustodyCode.INVALID)
        except OSError:
            raise AutomationCustodyError(AutomationCustodyCode.INVALID) from None
        metadata = target.stat()
        binding = ProfileWorkerBinding(identity, target, metadata.st_dev, metadata.st_ino)
        with self._lock:
            if self._binding is not None and self._binding != binding:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            self._binding = binding

    def require_session(self, session: BucketSession | None) -> None:
        """Check both process-wide publication and every scoped storage override."""
        with self._lock:
            binding = self._binding
            if binding is None or session is None:
                return
            if (
                session.bucket_id != str(binding.identity.binding.profile_id)
                or session.storage_root is None
                or session.storage_root.resolve() != binding.storage_root
            ):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)
            try:
                current = binding.storage_root.stat()
            except OSError:
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT) from None
            if (current.st_dev, current.st_ino) != (binding.root_device, binding.root_inode):
                raise AutomationCustodyError(AutomationCustodyCode.CONFLICT)


profile_worker_binding = ProfileWorkerBindingOwner()
"""The worker's one identity owner; ordinary frontend processes remain unpinned."""
