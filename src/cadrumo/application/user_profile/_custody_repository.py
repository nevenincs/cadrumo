"""Application repository and lock ports for profile custody transactions."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal
from uuid import UUID

from pydantic import ValidationError

from ...core import StorageCategory, storage_location
from ...core.paths import effective_storage_root
from ._custody_ports import ProfileCustodyLocalRecordStore, default_profile_custody_local_record_store
from ._custody_transactions import (
    CUSTODY_RECEIPT_MAX_BYTES,
    CUSTODY_TRANSACTION_MAX_BYTES,
    ProfileCustodyOwnerReceipt,
    ProfileCustodyTransactionConflictError,
    ProfileCustodyTransactionCorruptError,
    ProfileCustodyTransactionJournal,
    ProfileCustodyTransactionReceipt,
    read_profile_custody_record,
)


class ProfileCustodyTransactionRepository:
    """Persist strict current-format transaction journals and owner receipts."""

    def __init__(self, *, root: Path | None = None, adapters: ProfileCustodyLocalRecordStore | None = None) -> None:
        self._storage_root = effective_storage_root(root)
        self._adapters = adapters if adapters is not None else default_profile_custody_local_record_store()
        self._journal_root = (
            self._storage_root / storage_location(StorageCategory.PROFILE_CUSTODY_TRANSACTION_JOURNAL).relative_path()
        )
        self._receipt_root = (
            self._storage_root / storage_location(StorageCategory.PROFILE_CUSTODY_RECEIPT).relative_path()
        )

    def journal_path(self, transaction_id: UUID) -> Path:
        return self._journal_root / f"{transaction_id}.json"

    def receipt_path(self, transaction_id: UUID) -> Path:
        return self._receipt_root / f"{transaction_id}.application-local-custody.json"

    def owner_receipt_path(
        self,
        transaction_id: UUID,
        owner: Literal["process-secret-revocation", "local-session-acceleration"],
    ) -> Path:
        return self._receipt_root / f"{transaction_id}.{owner}.json"

    def create_journal(self, journal: ProfileCustodyTransactionJournal) -> None:
        self._ensure_root(self._journal_root, "custody transaction journal")
        path = self.journal_path(journal.transaction_id)
        with self._adapters.lock(self._journal_root / ".repository.lock"):
            self._write_exclusive(path, journal.canonical_json_bytes(), "custody transaction journal")

    def load_journal(self, transaction_id: UUID) -> ProfileCustodyTransactionJournal:
        path = self.journal_path(transaction_id)
        payload = self._read_bounded(path, CUSTODY_TRANSACTION_MAX_BYTES, "custody transaction journal")
        try:
            journal = ProfileCustodyTransactionJournal.model_validate_json(payload)
        except (ValidationError, ValueError) as exc:
            raise ProfileCustodyTransactionCorruptError("custody transaction journal is invalid") from exc
        if journal.transaction_id != transaction_id or journal.canonical_json_bytes() != payload:
            raise ProfileCustodyTransactionCorruptError(
                "custody transaction journal identity or canonical bytes differ"
            )
        return journal

    def save_journal(self, journal: ProfileCustodyTransactionJournal) -> None:
        self._ensure_root(self._journal_root, "custody transaction journal")
        path = self.journal_path(journal.transaction_id)
        with self._adapters.lock(self._journal_root / f".{path.name}.lock"):
            try:
                self._read_bounded(path, CUSTODY_TRANSACTION_MAX_BYTES, "custody transaction journal")
            except ProfileCustodyTransactionConflictError:
                raise ProfileCustodyTransactionConflictError("custody transaction journal is absent") from None
            self._write_replace(path, journal.canonical_json_bytes(), "custody transaction journal")

    def write_receipt(self, receipt: ProfileCustodyTransactionReceipt) -> ProfileCustodyTransactionReceipt:
        self._ensure_root(self._receipt_root, "custody receipt")
        path = self.receipt_path(receipt.transaction_id)
        payload = receipt.canonical_json_bytes()
        with self._adapters.lock(self._receipt_root / f".{path.name}.lock"):
            try:
                existing = self._read_bounded(path, CUSTODY_RECEIPT_MAX_BYTES, "custody receipt")
            except ProfileCustodyTransactionConflictError:
                self._write_exclusive(path, payload, "custody receipt")
            else:
                if existing != payload:
                    raise ProfileCustodyTransactionConflictError("custody receipt identity has different durable bytes")
            return receipt
        return receipt

    def load_receipt(self, transaction_id: UUID) -> ProfileCustodyTransactionReceipt | None:
        path = self.receipt_path(transaction_id)
        try:
            payload = self._read_bounded(path, CUSTODY_RECEIPT_MAX_BYTES, "custody receipt")
        except ProfileCustodyTransactionConflictError:
            return None
        try:
            receipt = ProfileCustodyTransactionReceipt.model_validate_json(payload)
        except (ValidationError, ValueError) as exc:
            raise ProfileCustodyTransactionCorruptError("custody receipt is invalid") from exc
        if receipt.transaction_id != transaction_id or receipt.canonical_json_bytes() != payload:
            raise ProfileCustodyTransactionCorruptError("custody receipt identity or canonical bytes differ")
        return receipt

    def write_owner_receipt(self, receipt: ProfileCustodyOwnerReceipt) -> ProfileCustodyOwnerReceipt:
        self._ensure_root(self._receipt_root, "custody owner receipt")
        path = self.owner_receipt_path(receipt.transaction_id, receipt.owner)
        payload = receipt.canonical_json_bytes()
        with self._adapters.lock(self._receipt_root / f".{path.name}.lock"):
            try:
                existing = self._read_bounded(path, CUSTODY_RECEIPT_MAX_BYTES, "custody owner receipt")
            except ProfileCustodyTransactionConflictError:
                self._write_exclusive(path, payload, "custody owner receipt")
            else:
                if existing != payload:
                    raise ProfileCustodyTransactionConflictError(
                        "custody owner receipt identity has different durable bytes"
                    )
            return receipt
        return receipt

    def load_owner_receipt(
        self,
        transaction_id: UUID,
        owner: Literal["process-secret-revocation", "local-session-acceleration"],
    ) -> ProfileCustodyOwnerReceipt | None:
        path = self.owner_receipt_path(transaction_id, owner)
        try:
            receipt = ProfileCustodyOwnerReceipt.model_validate_json(
                self._read_bounded(path, CUSTODY_RECEIPT_MAX_BYTES, "custody owner receipt")
            )
        except ProfileCustodyTransactionConflictError:
            return None
        except ValidationError as exc:
            raise ProfileCustodyTransactionCorruptError("custody owner receipt is invalid") from exc
        if receipt.transaction_id != transaction_id or receipt.owner != owner:
            raise ProfileCustodyTransactionCorruptError("custody owner receipt identity differs from its path")
        return receipt

    def _ensure_root(self, root: Path, subject: str) -> None:
        try:
            self._adapters.ensure_directory(root)
        except Exception as exc:
            raise ProfileCustodyTransactionCorruptError(f"{subject} root cannot be anchored") from exc

    @staticmethod
    def _read_bounded(path: Path, maximum_bytes: int, subject: str) -> bytes:
        return read_profile_custody_record(path, maximum_bytes=maximum_bytes, subject=subject)

    def _write_exclusive(self, path: Path, payload: bytes, subject: str) -> None:
        try:
            self._adapters.write(path, payload, publish_once=True)
        except Exception as exc:
            raise ProfileCustodyTransactionCorruptError(f"{subject} cannot be exclusively created") from exc

    def _write_replace(self, path: Path, payload: bytes, subject: str) -> None:
        try:
            self._adapters.write(path, payload, publish_once=False)
        except Exception as exc:
            raise ProfileCustodyTransactionCorruptError(f"{subject} cannot be atomically replaced") from exc


@contextmanager
def profile_custody_transaction_lock(root: Path, profile_id: UUID) -> Generator[None]:
    """Acquire root then profile lock, the only accepted custody lock order.

    Custody transactions are GLOBALLY serialised, not per profile. The root
    lock is taken first and held for the whole span, so two transactions for
    DIFFERENT profiles exclude each other exactly as two for the same profile
    do; a long transaction on one profile blocks every other.

    The profile lock therefore never contends under the current call graph --
    it is only ever acquired inside this function, with the root lock already
    held. Removing it fails the lock-order gate and nothing else, which is
    stated here because "there is a per-profile lock" otherwise reads as a
    promise of per-profile concurrency that the root lock does not deliver.
    It stays because the ORDER is the deadlock-safety rule: a future path that
    takes both must take them this way round.
    """
    from ._profile_pointer_transaction import active_profile_pointer_transaction

    adapters = default_profile_custody_local_record_store()
    storage_root = effective_storage_root(root)
    capsules_root = storage_root / storage_location(StorageCategory.BUCKETS).relative_path()
    # Use the application pointer transaction rather than reacquiring the raw
    # non-reentrant sidecar. A caller may already hold the canonical root lock
    # to bind an inactive-target decision across the complete custody delete.
    with active_profile_pointer_transaction(storage_root):
        try:
            adapters.ensure_directory(capsules_root)
        except Exception as exc:
            raise ProfileCustodyTransactionCorruptError("profile custody lock root cannot be anchored") from exc
        profile_target = capsules_root / f".profile-custody-{profile_id}.lock"
        with adapters.lock(profile_target):
            yield


__all__ = [
    "ProfileCustodyTransactionRepository",
    "profile_custody_transaction_lock",
]
