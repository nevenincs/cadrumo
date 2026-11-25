"""Derived idempotency-claim lookup entries kept beside the operation journal records.

The index is a lookup aid, never evidence: the journal loads and validates every
record an entry names before it believes a claim. Every method here runs while
the caller holds the journal's exclusive lock.
"""

from __future__ import annotations

import os
import re
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ValidationError, field_validator

from ....application.operations.models import OperationId
from ....core.atomic_write import DurableWriteBatch, atomic_write_hardened_bytes
from ....core.directory_scan import scan_directory
from ....core.external_constants import UTF_8_ENCODING
from ....core.hex import HEX_PATTERN_64
from ....core.identity.digest import ContentDigest
from ....core.link_safety import is_link_like
from ....core.models import STRICT_FROZEN_CONFIG
from ..storage.errors import RepositoryError

_HEX_64: Final = re.compile(HEX_PATTERN_64)
_CLAIM_INDEX_DIRNAME: Final = "idempotency-claims"
_CLAIM_INDEX_COMPLETE_FILENAME: Final = "complete"
_CLAIM_INDEX_DIRECTORY_MODE: Final = 0o700
_CLAIM_INDEX_FILE_MODE: Final = 0o600


class _ClaimIndexEntry(BaseModel):
    """Which journal records were created carrying one idempotency key digest.

    The entry is a derived lookup aid, never evidence: every named record is
    loaded and validated before its claim is believed, so an entry naming an
    absent record, a record whose claim was purged, or a record with another
    claim changes nothing.
    """

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1]
    key_digest: ContentDigest
    operation_ids: tuple[OperationId, ...]

    @field_validator("operation_ids")
    @classmethod
    def _sorted_unique(cls, value: tuple[OperationId, ...]) -> tuple[OperationId, ...]:
        if tuple(sorted(set(value))) != value:
            raise ValueError("claim index operation ids must be sorted and unique")
        return value


class _ClaimIndexCompleteness(BaseModel):
    """Witness that every claim-bearing record in the journal root has an entry."""

    model_config = STRICT_FROZEN_CONFIG

    schema_version: Literal[1]


class OperationClaimIndex:
    """The claim index files under one journal root, read and written under the caller's journal lock."""

    def __init__(self, *, journal_root: Path, write_payload: Callable[[Path, str], None]) -> None:
        """Bind the index to its journal root and the journal's fully synced payload writer."""
        self.root = journal_root / _CLAIM_INDEX_DIRNAME
        self._write_payload = write_payload

    def entry_path(self, key_digest: str) -> Path:
        """Return the entry file for one key digest, refusing a digest that is not canonical hex."""
        if _HEX_64.fullmatch(key_digest) is None:
            raise RepositoryError("operation idempotency key digest must be 64 lowercase hexadecimal characters")
        return self.root / f"{key_digest}.json"

    def _complete_path(self) -> Path:
        return self.root / _CLAIM_INDEX_COMPLETE_FILENAME

    def _read_text_unlocked(self, path: Path) -> str | None:
        """Read one index file, ``None`` when absent; links and unreadable files are refused."""
        if not os.path.lexists(path):
            return None
        if is_link_like(path) or is_link_like(self.root):
            raise RepositoryError("operation idempotency claim index cannot be a link")
        try:
            return path.read_text(encoding=UTF_8_ENCODING)
        except OSError as exc:
            raise RepositoryError("cannot read operation idempotency claim index") from exc

    def is_complete_unlocked(self) -> bool:
        """Report whether a readable, valid completeness witness is published."""
        try:
            raw = self._read_text_unlocked(self._complete_path())
        except RepositoryError:
            return False
        if raw is None:
            return False
        try:
            _ClaimIndexCompleteness.model_validate_json(raw)
        except ValidationError:
            return False
        return True

    def read_entry_unlocked(self, key_digest: str) -> tuple[OperationId, ...]:
        """Return the records one entry names, empty when it is absent, refusing a malformed entry."""
        raw = self._read_text_unlocked(self.entry_path(key_digest))
        if raw is None:
            return ()
        try:
            entry = _ClaimIndexEntry.model_validate_json(raw)
        except ValidationError as exc:
            raise RepositoryError("invalid operation idempotency claim index entry") from exc
        if entry.key_digest != key_digest:
            raise RepositoryError("operation idempotency claim index entry names another key")
        return entry.operation_ids

    def _ensure_root_unlocked(self) -> None:
        index_root = self.root
        if os.path.lexists(index_root) and is_link_like(index_root):
            raise RepositoryError("operation idempotency claim index cannot be a link")
        index_root.mkdir(exist_ok=True)
        if not index_root.is_dir():
            raise RepositoryError("operation idempotency claim index is not a directory")
        try:
            # Private directory mode; Semgrep's generic file-mode rule is inverted here.
            os.chmod(index_root, _CLAIM_INDEX_DIRECTORY_MODE)  # nosemgrep
        except OSError as exc:
            raise RepositoryError("cannot restrict operation idempotency claim index permissions") from exc

    def _write_entry_unlocked(
        self,
        key_digest: str,
        operation_ids: Iterable[OperationId],
        *,
        rebuild_batch: DurableWriteBatch | None = None,
    ) -> None:
        entry = _ClaimIndexEntry(
            schema_version=1,
            key_digest=key_digest,
            operation_ids=tuple(sorted(set(operation_ids))),
        )
        path = self.entry_path(key_digest)
        payload = entry.model_dump_json() + "\n"
        if rebuild_batch is None:
            self._write_payload(path, payload)
            return
        if self._read_text_unlocked(path) == payload:
            return
        # A rebuilt entry is re-derived from the records it names, so its
        # durability sync is batched (see DurableWriteBatch): a torn entry is
        # refused as malformed and rebuilt again. A create's entry is not.
        atomic_write_hardened_bytes(
            path, payload.encode(UTF_8_ENCODING), mode=_CLAIM_INDEX_FILE_MODE, batch=rebuild_batch
        )
        try:
            os.chmod(path, _CLAIM_INDEX_FILE_MODE)
        except OSError as exc:
            raise RepositoryError("cannot restrict operation idempotency claim index permissions") from exc

    def add_entry_unlocked(self, key_digest: str, operation_id: OperationId) -> None:
        """Publish ``operation_id`` under ``key_digest`` before its record is written."""
        self._ensure_root_unlocked()
        existing = self.read_entry_unlocked(key_digest)
        if operation_id not in existing:
            self._write_entry_unlocked(key_digest, (*existing, operation_id))

    def publish_rebuild_unlocked(self, claimed: Mapping[str, set[OperationId]]) -> None:
        """Retract the witness, make the entries exactly ``claimed``, then witness completeness."""
        self._ensure_root_unlocked()
        complete_path = self._complete_path()
        if os.path.lexists(complete_path):
            if is_link_like(complete_path):
                raise RepositoryError("operation idempotency claim index cannot be a link")
            complete_path.unlink()
        rebuild_batch = DurableWriteBatch()
        self._replace_entries_unlocked(claimed, rebuild_batch)
        # Every entry's publication is synced before the witness that relies
        # on it, which is itself written with a full per-file sync.
        rebuild_batch.commit()
        self._write_payload(complete_path, _ClaimIndexCompleteness(schema_version=1).model_dump_json() + "\n")

    def _replace_entries_unlocked(
        self,
        claimed: Mapping[str, set[OperationId]],
        rebuild_batch: DurableWriteBatch,
    ) -> None:
        """Make the entry files exactly the derived mapping, refusing foreign files."""
        for path in scan_directory(self.root, require_root=True):
            if path.name == _CLAIM_INDEX_COMPLETE_FILENAME:
                continue
            key_digest = path.name.removesuffix(".json")
            if path.suffix != ".json" or _HEX_64.fullmatch(key_digest) is None:
                raise RepositoryError("invalid operation idempotency claim index filename")
            if is_link_like(path) or not path.is_file():
                raise RepositoryError("operation idempotency claim index entry is not a regular file")
            if key_digest not in claimed:
                path.unlink()
        for key_digest, operation_ids in claimed.items():
            self._write_entry_unlocked(key_digest, operation_ids, rebuild_batch=rebuild_batch)
