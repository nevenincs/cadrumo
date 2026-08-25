"""Application-owned active-profile pointer custody witness."""

from __future__ import annotations

import base64
import os
from pathlib import Path

from pydantic import BaseModel, model_validator

from ...core import STRICT_FROZEN_CONFIG, StorageCategory, storage_location
from ...core.hashing import prefixed_digest as _digest
from ...core.paths import effective_storage_root
from ._custody_ports import default_profile_custody_local_record_store


def _corrupt(message: str) -> Exception:
    from ._custody_transactions import ProfileCustodyTransactionCorruptError

    return ProfileCustodyTransactionCorruptError(message)


class ProfileCustodyPointerSnapshot(BaseModel):
    """The exact pointer bytes and digest observed under the root lock."""

    model_config = STRICT_FROZEN_CONFIG

    present: bool
    encoded_bytes: str | None = None
    digest: str | None = None

    @model_validator(mode="after")
    def _validate_presence(self) -> ProfileCustodyPointerSnapshot:
        if self.present != (self.encoded_bytes is not None and self.digest is not None):
            raise ValueError("pointer snapshot presence must match bytes and digest")
        if self.encoded_bytes is not None:
            try:
                raw = base64.b64decode(self.encoded_bytes.encode("ascii"), validate=True)
            except (UnicodeEncodeError, ValueError) as exc:
                raise ValueError("pointer snapshot bytes must be canonical base64") from exc
            if base64.b64encode(raw).decode("ascii") != self.encoded_bytes or self.digest != _digest(raw):
                raise ValueError("pointer snapshot digest does not match captured bytes")
        return self

    @classmethod
    def capture(cls, root: Path) -> ProfileCustodyPointerSnapshot:
        storage_root = effective_storage_root(root)
        store = default_profile_custody_local_record_store()
        with store.root_lock(storage_root):
            target = storage_root / storage_location(StorageCategory.ACTIVE_PROFILE_POINTER).relative_path()
            if not os.path.lexists(target):
                captured = None
            else:
                try:
                    captured = store.read(target, maximum_bytes=1024)
                except Exception as exc:
                    raise _corrupt("active profile pointer cannot be no-follow captured") from exc
        if captured is None:
            return cls(present=False)
        return cls(
            present=True,
            encoded_bytes=base64.b64encode(captured).decode("ascii"),
            digest=_digest(captured),
        )

    def captured_bytes(self) -> bytes | None:
        if self.encoded_bytes is None:
            return None
        return base64.b64decode(self.encoded_bytes.encode("ascii"), validate=True)


__all__ = ["ProfileCustodyPointerSnapshot"]
