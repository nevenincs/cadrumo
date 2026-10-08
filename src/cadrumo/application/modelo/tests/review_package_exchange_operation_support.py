"""Inward exchange fixtures with genuine signatures and observable writer fences.

Encryption is a delegation double, not cryptographic/native acceptance evidence.
The existing outward adapter suites own those actual guarantees.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import cast, override
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey

from ....core.operations import profile_operation_subject
from ....domain.buckets.event import BucketEventHistoryCatalogue
from ....domain.calculations.registry.authority import PinnedAuthorityOperation
from ...operations.owner import OperationExecutorContext
from ..recipient_encryption import RecipientDecryptedPackage, RecipientEncryptedPackage, RecipientEncryptionKeypair
from ..review_package_exchange_operation_ports import ReviewPackageExchangeOperationPorts
from ..review_package_recipient_encryption import RecipientDecryptionError
from ..review_package_recipient_registry import RecipientFingerprintRecord, RecipientFingerprintRegister
from ..review_package_recipient_registry_ports import RecipientFingerprintRegistryPorts
from ..review_package_signing import ReviewPackageSigningKeypair
from ._review_package_bytes_support import build_package_path
from ._review_package_signing_support import InMemoryReviewPackageSigningKeypairCapability
from .m036_operation_support import INSTANT, PROFILE_ID, CommitFence, Events, Operands
from .test_m036_lifecycle_service import _EventRepository
from .test_review_package_signing import _revision, _work_unit


class Signing:
    """Prepare a genuine keypair outside COMMIT; detect only its persisted mint."""

    def __init__(self, fence: CommitFence) -> None:
        self.fence = fence
        self.keypair: ReviewPackageSigningKeypair | None = None
        self.prepared = InMemoryReviewPackageSigningKeypairCapability().ensure_keypair(
            bucket_id=str(PROFILE_ID), generated_at=INSTANT
        )
        self.write: Callable[[Callable[[], None]], None] | None = None

    def ensure_keypair(self, *, bucket_id: str, generated_at: datetime | None = None) -> ReviewPackageSigningKeypair:
        assert bucket_id == str(PROFILE_ID) and not self.fence.active
        if self.keypair is None:
            assert self.write is not None

            def save() -> None:
                assert self.fence.active
                self.keypair = self.prepared

            self.write(save)
        assert self.keypair is not None
        return self.keypair


class Encryption:
    """Memory-only protocol double; makes no claim about encryption primitives."""

    def __init__(self, fence: CommitFence) -> None:
        private = X25519PrivateKey.generate()
        self.prepared = RecipientEncryptionKeypair(
            bucket_id=str(PROFILE_ID),
            private_key_hex=private.private_bytes_raw().hex(),
            public_key_hex=private.public_key().public_bytes_raw().hex(),
            created_at=INSTANT,
        )
        self.keypair: RecipientEncryptionKeypair | None = None
        self.fence = fence
        self.write: Callable[[Callable[[], None]], None] | None = None
        self.values: dict[bytes, bytes] = {}
        self.encrypt_calls = 0
        self.decrypt_calls = 0

    def ensure_keypair(self, *, bucket_id: str, generated_at: datetime | None = None) -> RecipientEncryptionKeypair:
        assert bucket_id == str(PROFILE_ID) and not self.fence.active
        if self.keypair is None:
            assert self.write is not None

            def save() -> None:
                assert self.fence.active
                self.keypair = self.prepared

            self.write(save)
        assert self.keypair is not None
        return self.keypair

    def encrypt(
        self,
        package_bytes: bytes,
        *,
        recipient_public_key_hex: str,
        review_only: bool = False,
        valid_for: timedelta | None = None,
        issued_at: datetime | None = None,
    ) -> RecipientEncryptedPackage:
        assert not self.fence.active and recipient_public_key_hex == self.prepared.public_key_hex
        self.encrypt_calls += 1
        ciphertext = secrets.token_bytes(32)
        self.values[ciphertext] = package_bytes
        instant = issued_at or INSTANT
        return RecipientEncryptedPackage(
            ephemeral_public_key_hex="e" * 64,
            recipient_public_key_hex=recipient_public_key_hex,
            ciphertext=ciphertext,
            envelope_nonce_hex=secrets.token_hex(32),
            issued_at=instant,
            valid_until=instant + valid_for if valid_for is not None else None,
            review_only=review_only,
        )

    def decrypt(
        self, envelope: RecipientEncryptedPackage, *, recipient_private_key_hex: str, now: datetime | None = None
    ) -> RecipientDecryptedPackage:
        assert not self.fence.active
        self.decrypt_calls += 1
        if recipient_private_key_hex != self.prepared.private_key_hex or envelope.ciphertext not in self.values:
            raise RecipientDecryptionError("synthetic encryption capability refusal")
        return RecipientDecryptedPackage(
            package_bytes=self.values[envelope.ciphertext], review_only=envelope.review_only
        )


class Recipients:
    """One actual typed trusted fingerprint, whose read cannot hold COMMIT."""

    def __init__(self, encryption: Encryption) -> None:
        self.encryption = encryption
        self.reads = 0
        self.register = RecipientFingerprintRegister(
            records=(
                RecipientFingerprintRecord(
                    recipient_id=str(PROFILE_ID), public_key_hex=encryption.prepared.public_key_hex, added_at=INSTANT
                ),
            )
        )

    def load(self) -> RecipientFingerprintRegister:
        assert not self.encryption.fence.active
        self.reads += 1
        return self.register

    def save(self, register: RecipientFingerprintRegister) -> None:
        raise AssertionError("exchange must not mutate trusted recipient policy")


class History(_EventRepository):
    """Canonical domain event builder uses the established inward catalogue fixture."""

    def __init__(self, fence: CommitFence) -> None:
        super().__init__()
        self.fence = fence
        self.write: Callable[[Callable[[], None]], None] | None = None

    @override
    def load(self) -> BucketEventHistoryCatalogue:
        assert not self.fence.active
        return super().load()

    @override
    def save(self, catalogue: BucketEventHistoryCatalogue) -> None:
        assert not self.fence.active and self.write is not None

        def save() -> None:
            assert self.fence.active
            super(History, self).save(catalogue)

        self.write(save)


class Replay:
    """Detect established audit-before-consume ordering and consumption-before-output."""

    def __init__(self, fence: CommitFence) -> None:
        self.fence = fence
        self.consumed: set[str] = set()
        self.write: Callable[[Callable[[], None]], None] | None = None

    def mark_consumed(self, nonce_hex: str) -> object:
        assert not self.fence.active and self.write is not None
        if nonce_hex in self.consumed:
            raise ValueError("synthetic already-consumed nonce")

        def save() -> None:
            assert self.fence.active
            self.consumed.add(nonce_hex)

        self.write(save)
        return None


class Files:
    """Real disposable final artifacts plus I/O and uncertain-write detectors."""

    def __init__(self, fence: CommitFence) -> None:
        self.fence = fence
        self.write: Callable[[Callable[[], None]], None] | None = None
        self.fail_after_write = False

    def require_exists(self, path: Path) -> None:
        assert not self.fence.active
        if not path.exists():
            raise FileNotFoundError(path)

    def read_bytes(self, path: Path) -> bytes:
        assert not self.fence.active
        return path.read_bytes()

    def read_text(self, path: Path) -> str:
        assert not self.fence.active
        return path.read_text(encoding="utf-8")

    def write_bytes(self, path: Path, data: bytes) -> None:
        assert not self.fence.active and self.write is not None

        def save() -> None:
            assert self.fence.active
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if self.fail_after_write:
                raise OSError("synthetic final writer committed before failing")

        self.write(save)

    def write_text(self, path: Path, text: str) -> None:
        self.write_bytes(path, text.encode("utf-8"))


class Subject:
    """Real published pin and canonical built ZIP, with explicit inward effect ports."""

    def __init__(self, operation: PinnedAuthorityOperation, tmp_path: Path) -> None:
        self.operation = operation
        self.fence = CommitFence()
        self.events = Events()
        self.operands = Operands()
        self.signing = Signing(self.fence)
        self.encryption = Encryption(self.fence)
        self.recipients = Recipients(self.encryption)
        self.history = History(self.fence)
        self.replay = Replay(self.fence)
        self.files = Files(self.fence)
        self.package = build_package_path(
            tmp_path,
            bucket_id=str(PROFILE_ID),
            work_unit_factory=_work_unit,
            revision_factory=_revision,
            draft_bytes=b"synthetic reviewed financial draft",
            operation=operation,
        )

    def compose(
        self, *, profile_id: UUID, operation: PinnedAuthorityOperation, write: Callable[[Callable[[], None]], None]
    ) -> ReviewPackageExchangeOperationPorts:
        assert profile_id == PROFILE_ID and operation is self.operation and not self.fence.active
        self.signing.write = self.encryption.write = self.history.write = self.replay.write = self.files.write = write
        return ReviewPackageExchangeOperationPorts(
            profile_id,
            operation,
            self.signing,
            self.encryption,
            RecipientFingerprintRegistryPorts(self.recipients),
            self.replay,
            self.history,
            self.files,
        )

    def context(self, definition_id: str) -> OperationExecutorContext:
        return cast(
            OperationExecutorContext,
            SimpleNamespace(
                identity=SimpleNamespace(
                    definition_id=definition_id, subject_ref=profile_operation_subject(str(PROFILE_ID))
                ),
                authority_operation=self.operation,
                cancellation=self.fence,
                events=self.events,
                operands=self.operands,
            ),
        )
