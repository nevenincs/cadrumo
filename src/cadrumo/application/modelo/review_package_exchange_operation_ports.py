"""Exact-profile capabilities for the existing human review-package exchange."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import UUID

from ...domain.buckets.protocols import BucketEventHistoryRepositoryProtocol
from ...domain.calculations.registry.authority import PinnedAuthorityOperation
from .recipient_encryption import RecipientEncryptionCapability
from .review_package_recipient_registry_ports import RecipientFingerprintRegistryPorts
from .review_package_signing_ports import ReviewPackageSigningKeypairCapability


class ReviewPackageExchangeFiles(Protocol):
    """Read authorized local inputs and write only the explicit final human artifacts."""

    def require_exists(self, path: Path) -> None:
        """Preserve canonical existence checks without reading unused package bytes."""
        ...

    def read_bytes(self, path: Path) -> bytes:
        """Read one existing input into memory."""
        ...

    def read_text(self, path: Path) -> str:
        """Read one UTF-8 document, retaining canonical decode failures."""
        ...

    def write_bytes(self, path: Path, data: bytes) -> None:
        """Fence the prepared final artifact's mkdir/write only."""
        ...

    def write_text(self, path: Path, text: str) -> None:
        """Fence the prepared UTF-8 final artifact with canonical LF newlines."""
        ...


class ReviewPackageReplayGuard(Protocol):
    """Canonical single-use nonce consumption; no new application replay algorithm."""

    def mark_consumed(self, nonce_hex: str) -> object:
        """Atomically consume or refuse the already-consumed nonce."""
        ...


@dataclass(frozen=True, slots=True)
class ReviewPackageExchangeOperationPorts:
    """One worker's immutable profile, publication pin and canonical capabilities."""

    profile_id: UUID
    operation: PinnedAuthorityOperation
    signing: ReviewPackageSigningKeypairCapability
    encryption: RecipientEncryptionCapability
    recipients: RecipientFingerprintRegistryPorts
    replay: ReviewPackageReplayGuard
    history: BucketEventHistoryRepositoryProtocol
    files: ReviewPackageExchangeFiles


class ReviewPackageExchangeOperationPortsFactory(Protocol):
    """Compose capabilities with actual writer interception for one exact worker."""

    def __call__(
        self, *, profile_id: UUID, operation: PinnedAuthorityOperation, write: Callable[[Callable[[], None]], None]
    ) -> ReviewPackageExchangeOperationPorts:
        """Bind canonical secure writes and explicit artifacts to the operation fence."""
        ...
