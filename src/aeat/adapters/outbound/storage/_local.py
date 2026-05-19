"""Local-filesystem `StorageProvider` implementation.

Stores objects under a configurable root directory. Each namespace is
a subdirectory; each object is a single file named
`<hmac_prefix_8>--<label>.<ext>`. Metadata
(content_hash, byte_length, written_at, full HMAC, label) lives in a
sibling JSON sidecar so the listing API can return
`ProviderObjectMetadata` without re-hashing the payload.

Bytes-in / bytes-out: encryption + classification stay above this
layer. The provider treats every payload as opaque bytes.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

from ._errors import (
    OutboundStorageConflictError,
    OutboundStorageIntegrityError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageValidationError,
)
from ._records import ProviderKind, ProviderObjectMetadata, ProviderProbeReport

_HMAC_PREFIX_LEN = 8
_FILE_EXTENSION = ".bin"
_SIDECAR_EXTENSION = ".meta.json"
_PROBE_NAMESPACE = "_probe"
_DEFAULT_LABEL = "object"


def _validate_namespace(namespace: str) -> str:
    cleaned = namespace.strip()
    if not cleaned:
        raise OutboundStorageValidationError("namespace must not be blank")
    if "/" in cleaned or "\\" in cleaned or cleaned.startswith("."):
        raise OutboundStorageValidationError(
            f"namespace {namespace!r} contains forbidden characters",
            context={"namespace": namespace},
        )
    return cleaned


def _validate_hmac(object_key_hmac: str) -> str:
    cleaned = object_key_hmac.strip()
    if not cleaned:
        raise OutboundStorageValidationError("object_key_hmac must not be blank")
    if not all(c.isalnum() or c == "-" or c == "_" for c in cleaned):
        raise OutboundStorageValidationError(
            f"object_key_hmac {object_key_hmac!r} contains forbidden characters",
            context={"object_key_hmac": object_key_hmac},
        )
    return cleaned


def _validate_label(label: str) -> str:
    cleaned = label.strip()
    if not cleaned:
        return _DEFAULT_LABEL
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in cleaned)
    return safe[:64] or _DEFAULT_LABEL


def _filename(object_key_hmac: str, label: str, *, extension: str = _FILE_EXTENSION) -> str:
    """Build the canonical filename `<hmac_prefix_8>--<label><extension>`."""

    prefix = object_key_hmac[:_HMAC_PREFIX_LEN]
    return f"{prefix}--{label}{extension}"


def _sidecar_filename(object_key_hmac: str, label: str) -> str:
    return _filename(object_key_hmac, label, extension=_SIDECAR_EXTENSION)


class LocalFileSystemProvider:
    """Bytes-in / bytes-out provider backed by a `pathlib` directory tree."""

    def __init__(self, root: Path) -> None:
        """Bind the provider to ``root``.

        The root directory is created on first write if absent. The
        constructor itself never touches the filesystem so test
        fixtures and settings-driven instantiation stay cheap.
        """

        self._root = Path(root)

    @property
    def root(self) -> Path:
        return self._root

    def _ensure_namespace_dir(self, namespace: str) -> Path:
        target = self._root / namespace
        try:
            target.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            raise OutboundStoragePermissionError(
                f"cannot create namespace directory {target}: {exc}",
                context={"namespace": namespace, "path": str(target)},
            ) from exc
        return target

    def _resolve_object_path(self, namespace: str, object_key_hmac: str) -> Path | None:
        """Find the on-disk file for ``object_key_hmac`` if present.

        Searches the namespace directory for a file matching the HMAC
        prefix; the label suffix is operator-mutable so we resolve by
        prefix to keep rename detection cheap.
        """

        namespace_dir = self._root / namespace
        if not namespace_dir.is_dir():
            return None
        prefix = object_key_hmac[:_HMAC_PREFIX_LEN]
        for entry in namespace_dir.iterdir():
            if entry.is_file() and entry.name.startswith(f"{prefix}--") and entry.suffix == _FILE_EXTENSION:
                return entry
        return None

    def _load_sidecar(self, sidecar_path: Path) -> dict[str, object]:
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OutboundStorageIntegrityError(
                f"sidecar {sidecar_path} is unreadable or malformed: {exc}",
                context={"sidecar_path": str(sidecar_path)},
            ) from exc
        if not isinstance(payload, dict):
            raise OutboundStorageIntegrityError(
                f"sidecar {sidecar_path} is not a JSON object",
                context={"sidecar_path": str(sidecar_path)},
            )
        return payload

    def put(
        self,
        namespace: str,
        object_key_hmac: str,
        payload: bytes,
        *,
        content_hash: str,
        label: str,
    ) -> ProviderObjectMetadata:
        """Atomically write the object and its sidecar.

        Atomicity guarantee: the payload file is written to a `.tmp`
        sibling and renamed into place. The sidecar is written
        afterwards; on sidecar-write failure the payload is removed so
        no orphaned object lingers without metadata.
        """

        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)
        label_clean = _validate_label(label)
        if not content_hash.strip():
            raise OutboundStorageValidationError("content_hash must not be blank")

        namespace_dir = self._ensure_namespace_dir(namespace_clean)
        existing_path = self._resolve_object_path(namespace_clean, hmac_clean)
        if existing_path is not None and existing_path.name != _filename(hmac_clean, label_clean):
            # Label drifted; the rename is part of put() semantics. The
            # coordinator's diff classifier handles "did label change"
            # via the rename-detection path on push.
            existing_sidecar = existing_path.with_name(
                existing_path.stem + _SIDECAR_EXTENSION,
            )
            existing_path.unlink(missing_ok=True)
            existing_sidecar.unlink(missing_ok=True)

        target_path = namespace_dir / _filename(hmac_clean, label_clean)
        sidecar_path = namespace_dir / _sidecar_filename(hmac_clean, label_clean)
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")

        try:
            tmp_path.write_bytes(payload)
            os.replace(tmp_path, target_path)
        except PermissionError as exc:
            tmp_path.unlink(missing_ok=True)
            raise OutboundStoragePermissionError(
                f"cannot write object payload to {target_path}: {exc}",
                context={"path": str(target_path)},
            ) from exc
        except OSError as exc:
            tmp_path.unlink(missing_ok=True)
            raise OutboundStorageConflictError(
                f"failed to commit object payload to {target_path}: {exc}",
                context={"path": str(target_path)},
            ) from exc

        written_at = datetime.now(UTC)
        sidecar_payload = {
            "namespace": namespace_clean,
            "object_key_hmac": hmac_clean,
            "label": label_clean,
            "byte_length": len(payload),
            "content_hash": content_hash,
            "written_at": written_at.isoformat(),
        }
        try:
            sidecar_path.write_text(json.dumps(sidecar_payload, sort_keys=True), encoding="utf-8")
        except OSError as exc:
            target_path.unlink(missing_ok=True)
            raise OutboundStoragePermissionError(
                f"failed to write sidecar {sidecar_path}: {exc}",
                context={"path": str(sidecar_path)},
            ) from exc

        return ProviderObjectMetadata(
            namespace=namespace_clean,
            object_key_hmac=hmac_clean,
            provider_object_id=str(target_path),
            byte_length=len(payload),
            content_hash=content_hash,
            written_at=written_at,
        )

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)

        target_path = self._resolve_object_path(namespace_clean, hmac_clean)
        if target_path is None:
            raise OutboundStorageNotFoundError(
                f"object {hmac_clean!r} not found in namespace {namespace_clean!r}",
                context={"namespace": namespace_clean, "object_key_hmac": hmac_clean},
            )
        sidecar_path = target_path.with_name(target_path.stem + _SIDECAR_EXTENSION)
        if not sidecar_path.is_file():
            raise OutboundStorageIntegrityError(
                f"object {target_path.name} has no sidecar; storage corrupt",
                context={"path": str(target_path)},
            )
        sidecar = self._load_sidecar(sidecar_path)

        try:
            payload = target_path.read_bytes()
        except PermissionError as exc:
            raise OutboundStoragePermissionError(
                f"cannot read object payload from {target_path}: {exc}",
                context={"path": str(target_path)},
            ) from exc

        actual_hash = hashlib.sha256(payload).hexdigest()
        stored_hash = str(sidecar.get("content_hash", ""))
        # The stored hash may be a vendor-prefixed string ("sha256-XXX")
        # or a bare hex digest; we accept either as long as the digest
        # portion matches.
        stripped_stored = stored_hash.split("-", 1)[1] if stored_hash.startswith("sha256-") else stored_hash
        if stripped_stored and stripped_stored != actual_hash:
            raise OutboundStorageIntegrityError(
                f"content_hash mismatch for {target_path.name}: stored={stored_hash!r} actual_sha256={actual_hash!r}",
                context={"path": str(target_path), "stored_hash": stored_hash, "actual_sha256": actual_hash},
            )

        written_at_raw = str(sidecar.get("written_at", ""))
        try:
            written_at = datetime.fromisoformat(written_at_raw) if written_at_raw else datetime.now(UTC)
        except ValueError:
            written_at = datetime.now(UTC)

        _byte_length_raw = sidecar.get("byte_length", len(payload))
        if not isinstance(_byte_length_raw, (int, str)):
            raise TypeError(f"sidecar byte_length has unexpected type: {type(_byte_length_raw)!r}")
        metadata = ProviderObjectMetadata(
            namespace=namespace_clean,
            object_key_hmac=hmac_clean,
            provider_object_id=str(target_path),
            byte_length=int(_byte_length_raw),
            content_hash=stored_hash or f"sha256-{actual_hash}",
            written_at=written_at,
        )
        return payload, metadata

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)

        target_path = self._resolve_object_path(namespace_clean, hmac_clean)
        if target_path is None:
            return False
        sidecar_path = target_path.with_name(target_path.stem + _SIDECAR_EXTENSION)
        try:
            target_path.unlink()
            sidecar_path.unlink(missing_ok=True)
        except PermissionError as exc:
            raise OutboundStoragePermissionError(
                f"cannot delete object {target_path}: {exc}",
                context={"path": str(target_path)},
            ) from exc
        return True

    def iter_namespaces(self) -> Iterator[str]:
        if not self._root.is_dir():
            return
        for entry in self._root.iterdir():
            if entry.is_dir():
                yield entry.name

    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]:
        namespace_clean = _validate_namespace(namespace)
        namespace_dir = self._root / namespace_clean
        if not namespace_dir.is_dir():
            raise OutboundStorageNotFoundError(
                f"namespace {namespace_clean!r} does not exist",
                context={"namespace": namespace_clean},
            )
        for entry in sorted(namespace_dir.iterdir()):
            if not entry.is_file() or entry.suffix != _FILE_EXTENSION:
                continue
            sidecar_path = entry.with_name(entry.stem + _SIDECAR_EXTENSION)
            if not sidecar_path.is_file():
                # Skip orphan-without-sidecar; the coordinator's diff
                # classifier surfaces it as an integrity issue elsewhere.
                continue
            sidecar = self._load_sidecar(sidecar_path)
            written_at_raw = str(sidecar.get("written_at", ""))
            try:
                written_at = datetime.fromisoformat(written_at_raw) if written_at_raw else datetime.now(UTC)
            except ValueError:
                written_at = datetime.now(UTC)
            _byte_length_raw = sidecar.get("byte_length", 0)
            if not isinstance(_byte_length_raw, (int, str)):
                raise TypeError(f"sidecar byte_length has unexpected type: {type(_byte_length_raw)!r}")
            yield ProviderObjectMetadata(
                namespace=namespace_clean,
                object_key_hmac=str(sidecar.get("object_key_hmac", "")),
                provider_object_id=str(entry),
                byte_length=int(_byte_length_raw),
                content_hash=str(sidecar.get("content_hash", "")),
                written_at=written_at,
            )

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        if not self._root.exists():
            try:
                self._root.mkdir(parents=True, exist_ok=True)
            except (PermissionError, OSError) as exc:
                return ProviderProbeReport(
                    provider_kind=ProviderKind.LOCAL_FILESYSTEM,
                    read_only=read_only,
                    reachable=False,
                    writable=False,
                    detail=f"root {self._root} unreachable: {exc}",
                )

        if read_only:
            return ProviderProbeReport(
                provider_kind=ProviderKind.LOCAL_FILESYSTEM,
                read_only=read_only,
                reachable=True,
                writable=False,
                detail=f"read_only probe; root {self._root} is reachable",
            )

        # Sentinel-file round-trip in `_probe/`.
        try:
            metadata = self.put(
                _PROBE_NAMESPACE,
                "00000000probe",
                b"",
                content_hash="sha256-empty",
                label="sentinel",
            )
        except (PermissionError, OSError, OutboundStoragePermissionError, OutboundStorageConflictError) as exc:
            return ProviderProbeReport(
                provider_kind=ProviderKind.LOCAL_FILESYSTEM,
                read_only=read_only,
                reachable=True,
                writable=False,
                detail=f"sentinel write refused: {exc}",
            )
        with contextlib.suppress(PermissionError, OSError, OutboundStoragePermissionError):
            self.delete(_PROBE_NAMESPACE, "00000000probe")
        del metadata
        return ProviderProbeReport(
            provider_kind=ProviderKind.LOCAL_FILESYSTEM,
            read_only=read_only,
            reachable=True,
            writable=True,
            detail=f"sentinel round-trip ok in {self._root}",
        )


__all__ = ["LocalFileSystemProvider"]
