"""Durable persistence and recovery operations for the label head."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID

from pydantic import ValidationError

from .....core import StorageCategory, storage_location
from .....core.paths import effective_storage_root
from ._capsule_records import ProfileCustodyCapsuleLabel
from .errors import ProfileCustodyRecordError
from ._filesystem import (
    clear_profile_custody_local_record,
    ensure_profile_custody_local_directory,
    read_profile_custody_local_record,
    write_profile_custody_local_record,
)
from ._label_head_models import LABEL_HEAD_MAX_BYTES, ProfileLabelHead, ProfileLabelHeadPendingAdvance


def _read_profile_custody_record(path: Path, *, maximum_bytes: int, subject: str) -> bytes:
    """Read one bounded local custody record without following a link."""
    if not os.path.lexists(path):
        raise ProfileCustodyRecordError(f"{subject} is absent")
    try:
        return read_profile_custody_local_record(path, maximum_bytes=maximum_bytes)
    except Exception as exc:
        raise ProfileCustodyRecordError(f"{subject} cannot be opened") from exc


class ProfileLabelHeadRepository:
    """Read, verify, CAS-advance, and deterministically recover label heads."""

    def __init__(self, *, root: Path | None = None) -> None:
        self._root = effective_storage_root(root)
        self._head_root = self._root / storage_location(StorageCategory.PROFILE_CUSTODY_LABEL_HEAD).relative_path()

    def head_path(self, profile_id: UUID) -> Path:
        return self._head_root / f"{profile_id}.json"

    def pending_path(self, profile_id: UUID) -> Path:
        return self._head_root / f".{profile_id}.pending.json"

    def load_current(self, profile_id: UUID) -> ProfileLabelHead:
        """Return the exact durable head for an already-verified current capsule."""
        head = self._load_head(profile_id)
        if head is None:
            raise ProfileCustodyRecordError("profile label head is absent")
        return head

    def verify_or_recover_initial(
        self,
        *,
        label: ProfileCustodyCapsuleLabel,
        source_witness: str,
    ) -> ProfileLabelHead:
        """Return a matching head or publish exactly the journal-bound first head."""
        pending = self._load_pending(label.profile_id)
        if pending is not None:
            self._recover_pending(pending, label)
        current = self._load_head(label.profile_id)
        if current is None:
            head = ProfileLabelHead.create_initial(label=label, source_witness=source_witness)
            self._write_head_exclusive(head)
            return head
        if not current.verifies(label):
            raise ProfileCustodyRecordError("profile label differs from its trusted head")
        return current

    def begin_advance(
        self,
        *,
        current_head: ProfileLabelHead,
        current_label: ProfileCustodyCapsuleLabel,
        replacement_label: ProfileCustodyCapsuleLabel,
    ) -> ProfileLabelHeadPendingAdvance:
        if not current_head.verifies(current_label):
            raise ProfileCustodyRecordError("profile label differs from its trusted head")
        replacement_head = ProfileLabelHead.advance(current=current_head, label=replacement_label)
        pending = ProfileLabelHeadPendingAdvance.create(
            expected_head=current_head,
            expected_label=current_label,
            replacement_label=replacement_label,
            replacement_head=replacement_head,
        )
        self._write_pending_exclusive(pending)
        return pending

    def recover_advance(
        self,
        *,
        profile_id: UUID,
        current_label: ProfileCustodyCapsuleLabel,
    ) -> ProfileLabelHead:
        pending = self._load_pending(profile_id)
        if pending is not None:
            self._recover_pending(pending, current_label)
        head = self._load_head(profile_id)
        if head is None or not head.verifies(current_label):
            raise ProfileCustodyRecordError("profile label differs from its trusted head")
        return head

    def _recover_pending(
        self,
        pending: ProfileLabelHeadPendingAdvance,
        current_label: ProfileCustodyCapsuleLabel,
    ) -> None:
        current_head = self._load_head(pending.profile_id)
        if current_head is None:
            raise ProfileCustodyRecordError("pending label advance lacks its trusted current head")
        if current_label == pending.expected_label and current_head.self_digest == pending.expected_head_digest:
            self._clear_pending(pending.profile_id)
            return
        if current_label == pending.replacement_label and current_head.self_digest == pending.expected_head_digest:
            self._write_head_replace(pending.replacement_head)
            self._clear_pending(pending.profile_id)
            return
        if current_label == pending.replacement_label and current_head == pending.replacement_head:
            self._clear_pending(pending.profile_id)
            return
        raise ProfileCustodyRecordError("pending label advance conflicts with durable label or head state")

    def _load_head(self, profile_id: UUID) -> ProfileLabelHead | None:
        path = self.head_path(profile_id)
        if not os.path.lexists(path):
            return None
        try:
            payload = _read_profile_custody_record(
                path,
                maximum_bytes=LABEL_HEAD_MAX_BYTES,
                subject="profile label head",
            )
            head = ProfileLabelHead.model_validate_json(payload)
        except (ProfileCustodyRecordError, ValidationError, ValueError) as exc:
            raise ProfileCustodyRecordError("profile label head is invalid") from exc
        if head.profile_id != profile_id or head.canonical_json_bytes() != payload:
            raise ProfileCustodyRecordError("profile label head identity or canonical bytes differ")
        return head

    def _load_pending(self, profile_id: UUID) -> ProfileLabelHeadPendingAdvance | None:
        path = self.pending_path(profile_id)
        if not os.path.lexists(path):
            return None
        try:
            payload = _read_profile_custody_record(
                path,
                maximum_bytes=LABEL_HEAD_MAX_BYTES,
                subject="pending profile label head",
            )
            pending = ProfileLabelHeadPendingAdvance.model_validate_json(payload)
        except (ProfileCustodyRecordError, ValidationError, ValueError) as exc:
            raise ProfileCustodyRecordError("pending profile label head is invalid") from exc
        if pending.profile_id != profile_id or pending.canonical_json_bytes() != payload:
            raise ProfileCustodyRecordError("pending profile label head identity or canonical bytes differ")
        return pending

    def _ensure_root(self) -> None:
        try:
            ensure_profile_custody_local_directory(self._head_root)
        except Exception as exc:
            raise ProfileCustodyRecordError("profile label head root cannot be anchored") from exc

    def _write_head_exclusive(self, head: ProfileLabelHead) -> None:
        self._ensure_root()
        try:
            write_profile_custody_local_record(
                self.head_path(head.profile_id), head.canonical_json_bytes(), publish_once=True
            )
        except Exception as exc:
            raise ProfileCustodyRecordError("profile label head cannot be exclusively published") from exc

    def _write_head_replace(self, head: ProfileLabelHead) -> None:
        self._ensure_root()
        try:
            write_profile_custody_local_record(
                self.head_path(head.profile_id), head.canonical_json_bytes(), publish_once=False
            )
        except Exception as exc:
            raise ProfileCustodyRecordError("profile label head cannot be atomically replaced") from exc

    def _write_pending_exclusive(self, pending: ProfileLabelHeadPendingAdvance) -> None:
        self._ensure_root()
        try:
            write_profile_custody_local_record(
                self.pending_path(pending.profile_id), pending.canonical_json_bytes(), publish_once=True
            )
        except Exception as exc:
            raise ProfileCustodyRecordError("profile label advance is already pending") from exc

    def _clear_pending(self, profile_id: UUID) -> None:
        try:
            clear_profile_custody_local_record(self.pending_path(profile_id))
        except Exception as exc:
            raise ProfileCustodyRecordError("pending profile label head cannot be cleared") from exc


__all__ = ["ProfileLabelHeadRepository"]
