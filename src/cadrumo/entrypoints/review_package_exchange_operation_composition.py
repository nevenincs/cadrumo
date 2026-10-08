"""Compose canonical review-package custody and explicit human final artifacts."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from uuid import UUID

from ..adapters.persistence.profile.buckets import BucketEventHistoryRepository
from ..adapters.persistence.profile.recipient_replay_guard import RecipientReplayGuardRepository
from ..adapters.persistence.profile.review_package_recipient_encryption import RecipientEncryptionAdapter
from ..adapters.persistence.profile.review_package_recipient_registry import RecipientFingerprintRegistryAdapter
from ..adapters.persistence.profile.review_package_signing import ReviewPackageSigningKeypairAdapter
from ..adapters.persistence.storage.errors import SecureObjectRevisionConflictError
from ..adapters.persistence.storage.runtime_repository import secure_object_repository_for_bucket
from ..application.ledger.persistence_ports import LedgerPersistenceConflictError
from ..application.modelo.review_package_exchange_operation_ports import ReviewPackageExchangeOperationPorts
from ..application.modelo.review_package_recipient_registry_ports import RecipientFingerprintRegistryPorts
from ..application.user_profile.access_contracts import AccessDenialCode
from ..application.user_profile.access_errors import ProfileAccessRefusedError
from ..core.bucket_pointer import require_active_bucket_id
from ..core.external_constants import UTF_8_ENCODING
from ..domain.calculations.registry.authority import PinnedAuthorityOperation


class ReviewPackageExchangeLocalFiles:
    """Local source reads and short fenced final writes; no plaintext staging."""

    def __init__(self, write: Callable[[Callable[[], None]], None]) -> None:
        """Bind only concrete mkdir/write calls to the operation writer boundary."""
        self._write = write

    def require_exists(self, path: Path) -> None:
        """Retain existence validation without opening unused archives."""
        if not path.exists():
            raise FileNotFoundError(path)

    def read_bytes(self, path: Path) -> bytes:
        """Read the operator-authorized file into transient memory."""
        return path.read_bytes()

    def read_text(self, path: Path) -> str:
        """Read canonical UTF-8 JSON including existing decode behavior."""
        return path.read_text(encoding=UTF_8_ENCODING)

    def write_bytes(self, path: Path, data: bytes) -> None:
        """Write the existing explicit final output under COMMIT authority."""

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)

        self._write(write)

    def write_text(self, path: Path, text: str) -> None:
        """Preserve existing UTF-8/LF final wire bytes and output replacement."""

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding=UTF_8_ENCODING, newline="\n")

        self._write(write)


def build_review_package_exchange_operation_ports(
    *, profile_id: UUID, operation: PinnedAuthorityOperation, write: Callable[[Callable[[], None]], None]
) -> ReviewPackageExchangeOperationPorts:
    """Reuse the exact worker's encrypted store, canonical algorithms and one pin."""
    if require_active_bucket_id() != str(profile_id):
        raise ProfileAccessRefusedError(AccessDenialCode.PROFILE_MISMATCH)
    objects = secure_object_repository_for_bucket(str(profile_id))

    def secure_write(callback: Callable[[], None]) -> None:
        # Secure-object CAS conflict is an established guaranteed no-write
        # outcome. Translate at the fence, then restore the canonical exception
        # so each existing adapter retains its winner-read/retry algorithm.
        def translated() -> None:
            try:
                callback()
            except SecureObjectRevisionConflictError as exc:
                raise LedgerPersistenceConflictError("review-package secure write revision changed") from exc

        try:
            write(translated)
        except LedgerPersistenceConflictError as exc:
            if isinstance(exc.__cause__, SecureObjectRevisionConflictError):
                raise exc.__cause__ from None
            raise

    return ReviewPackageExchangeOperationPorts(
        profile_id=profile_id,
        operation=operation,
        signing=ReviewPackageSigningKeypairAdapter(
            repository=objects, bucket_id=str(profile_id), mutation_writer=secure_write
        ),
        encryption=RecipientEncryptionAdapter(
            repository=objects, bucket_id=str(profile_id), mutation_writer=secure_write
        ),
        recipients=RecipientFingerprintRegistryPorts(
            registry_repository=RecipientFingerprintRegistryAdapter(repository=objects)
        ),
        replay=RecipientReplayGuardRepository(objects=objects, mutation_writer=secure_write),
        history=BucketEventHistoryRepository(objects=objects, mutation_writer=secure_write),
        files=ReviewPackageExchangeLocalFiles(write),
    )
