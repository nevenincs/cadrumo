"""Setup receipts: one non-secret record per installed item, written after it verifies.

A receipt records what was installed (version or revision), a digest manifest
of the installed files, when the item last verified and which hosts it came
from. It is evidence a status probe compares against -- a browser executable
whose digest no longer matches its receipt is damaged -- and never authority:
a receipt whose files are gone describes nothing, so no state is ever derived
from a receipt alone.

Receipts are public facts about public artifacts and live installation-wide in
the ``DEPENDENCY_RECEIPTS`` storage category, beside the components they
describe and outside encrypted custody. Each is written atomically.
"""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, NonNegativeInt, StringConstraints, ValidationError, model_validator

from ..core.atomic_write import atomic_write_bytes
from ..core.config import Settings
from ..core.errors.hierarchy import pydantic_validation_boundary
from ..core.hashing import canonical_json_bytes, hash_file
from ..core.identity.digest import ContentDigest
from ..core.models import STRICT_FROZEN_CONFIG
from ..core.storage_taxonomy import StorageCategory
from ..core.storage_taxonomy_locations import storage_path
from ..core.time.utc import validate_utc_aware
from .dependency_contracts import DependencyHostName, DependencyItemId, dependency_item_kind

__all__ = [
    "DEPENDENCY_RECEIPT_VERSION",
    "DependencyManifestCheck",
    "DependencyReceipt",
    "DependencyReceiptFile",
    "DependencyReceiptReading",
    "DependencyReceiptState",
    "DependencyReceiptStore",
    "build_file_manifest",
    "check_file_manifest",
    "dependency_receipts_root",
]

DEPENDENCY_RECEIPT_VERSION: Final = 1
_MAX_RECEIPT_BYTES: Final = 4 * 1024 * 1024

type _RelativePath = Annotated[str, StringConstraints(min_length=1, max_length=1024)]


class DependencyReceiptFile(BaseModel):
    """One installed file: its path relative to the item's install root, size and digest."""

    model_config = STRICT_FROZEN_CONFIG

    path: _RelativePath
    size_bytes: NonNegativeInt
    sha256: ContentDigest

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_path(self) -> DependencyReceiptFile:
        _require_contained(self.path)
        return self


def _require_contained(relative: str) -> PurePosixPath:
    path = PurePosixPath(relative)
    if path.is_absolute() or "\\" in relative or ":" in relative or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("a receipt path is a plain relative path inside the install root")
    if path.as_posix() != relative:
        raise ValueError("a receipt path is written in its canonical form")
    return path


class DependencyReceipt(BaseModel):
    """The receipt of one verified item."""

    model_config = STRICT_FROZEN_CONFIG

    receipt_version: Literal[1] = DEPENDENCY_RECEIPT_VERSION
    item_id: DependencyItemId
    version: Annotated[str, StringConstraints(min_length=1, max_length=128)] | None
    files: tuple[DependencyReceiptFile, ...]
    verified_at: datetime
    hosts: tuple[DependencyHostName, ...] = Field(default=())

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_receipt(self) -> DependencyReceipt:
        dependency_item_kind(self.item_id)
        validate_utc_aware(self.verified_at)
        paths = [entry.path for entry in self.files]
        if paths != sorted(set(paths)):
            raise ValueError("a receipt lists each file once, in path order")
        return self


class DependencyReceiptState(StrEnum):
    """Whether a receipt could be read: present, never written, or unreadable."""

    PRESENT = "present"
    ABSENT = "absent"
    UNREADABLE = "unreadable"


class DependencyReceiptReading(BaseModel):
    """A read of one item's receipt; ``receipt`` is set exactly when it is present."""

    model_config = STRICT_FROZEN_CONFIG

    state: DependencyReceiptState
    receipt: DependencyReceipt | None = None

    @model_validator(mode="after")
    @pydantic_validation_boundary
    def _validate_reading(self) -> DependencyReceiptReading:
        if (self.state is DependencyReceiptState.PRESENT) != (self.receipt is not None):
            raise ValueError("a receipt reading carries the receipt exactly when it is present")
        return self


def dependency_receipts_root(settings: Settings | None = None) -> Path:
    """Return the installation-wide folder that holds every setup receipt."""
    return storage_path(StorageCategory.DEPENDENCY_RECEIPTS, settings=settings)


class DependencyReceiptStore:
    """Atomic, per-item receipt files under one receipts folder."""

    def __init__(self, root: Path) -> None:
        """Bind the store to its receipts folder, created on first write."""
        self._root = root

    @property
    def root(self) -> Path:
        """The receipts folder."""
        return self._root

    def _path(self, item_id: str) -> Path:
        dependency_item_kind(item_id)
        return self._root / f"{item_id}.json"

    def write(self, receipt: DependencyReceipt) -> None:
        """Replace the item's receipt atomically."""
        atomic_write_bytes(self._path(receipt.item_id), canonical_json_bytes(receipt.model_dump(mode="json")))

    def read(self, item_id: str) -> DependencyReceiptReading:
        """Read the item's receipt; a damaged or foreign file reads as unreadable, never as absent."""
        path = self._path(item_id)
        try:
            with path.open("rb") as handle:
                raw = handle.read(_MAX_RECEIPT_BYTES + 1)
        except FileNotFoundError:
            return DependencyReceiptReading(state=DependencyReceiptState.ABSENT)
        except OSError:
            return DependencyReceiptReading(state=DependencyReceiptState.UNREADABLE)
        if len(raw) > _MAX_RECEIPT_BYTES:
            return DependencyReceiptReading(state=DependencyReceiptState.UNREADABLE)
        try:
            receipt = DependencyReceipt.model_validate_json(raw)
        except (ValidationError, json.JSONDecodeError, UnicodeDecodeError):
            return DependencyReceiptReading(state=DependencyReceiptState.UNREADABLE)
        if receipt.item_id != item_id:
            return DependencyReceiptReading(state=DependencyReceiptState.UNREADABLE)
        return DependencyReceiptReading(state=DependencyReceiptState.PRESENT, receipt=receipt)

    def remove(self, item_id: str) -> None:
        """Remove the item's receipt, if there is one, when its install is removed."""
        self._path(item_id).unlink(missing_ok=True)


def build_file_manifest(install_root: Path, files: Iterable[Path] | None = None) -> tuple[DependencyReceiptFile, ...]:
    """Hash the installed files under ``install_root`` (every regular file by default) into a manifest.

    Symbolic links are not followed or recorded, so a manifest never describes
    bytes outside the install root.
    """
    root = install_root.resolve()
    selected = (path for path in root.rglob("*")) if files is None else (Path(path) for path in files)
    entries: dict[str, DependencyReceiptFile] = {}
    for candidate in selected:
        absolute = candidate if candidate.is_absolute() else root / candidate
        if absolute.is_symlink() or not absolute.is_file():
            continue
        relative = absolute.resolve().relative_to(root).as_posix()
        digest, size = hash_file(absolute)
        entries[relative] = DependencyReceiptFile(path=relative, size_bytes=size, sha256=digest)
    return tuple(entries[path] for path in sorted(entries))


class DependencyManifestCheck(BaseModel):
    """How the files on disk compare with a receipt's manifest."""

    model_config = STRICT_FROZEN_CONFIG

    missing: tuple[str, ...] = ()
    changed: tuple[str, ...] = ()
    checked: NonNegativeInt = 0

    @property
    def intact(self) -> bool:
        """Whether every checked file is present with the recorded size and digest."""
        return not self.missing and not self.changed


def check_file_manifest(
    install_root: Path,
    receipt: DependencyReceipt,
    *,
    only: Iterable[str] | None = None,
) -> DependencyManifestCheck:
    """Compare installed files with ``receipt``; ``only`` limits the check to named paths.

    A quick check passes ``only`` with the executables, so it stays inside its
    time bound; a full check compares every recorded file. A named path the
    receipt does not record counts as missing.
    """
    recorded = {entry.path: entry for entry in receipt.files}
    names = sorted(recorded) if only is None else sorted(set(only))
    missing: list[str] = []
    changed: list[str] = []
    for name in names:
        entry = recorded.get(name)
        path = install_root / _require_contained(name)
        if entry is None or path.is_symlink() or not path.is_file():
            missing.append(name)
            continue
        if path.stat().st_size != entry.size_bytes or hash_file(path)[0] != entry.sha256:
            changed.append(name)
    return DependencyManifestCheck(missing=tuple(missing), changed=tuple(changed), checked=len(names))
