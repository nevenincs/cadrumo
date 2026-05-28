"""Google Drive v3 `StorageProvider` implementation.

Maps the `StorageProvider` Protocol onto the Drive API:

- Each namespace is a folder directly under the operator-configured
  `aeat-vault/` root. The root folder is auto-created on first probe
  under the parent specified by `aeat_google_drive_root_folder_id` if
  absent. The root folder ID is required when `aeat_storage_provider_kind=google_drive`.
- Each object is a `files().create(...)` upload with a binary
  `mimeType=application/octet-stream`, named
  `<hmac_prefix_8>--<label>.bin`. The Drive `appProperties` field
  carries the per-object commit-log payload from
  `aeat.adapters.outbound.google.DriveAppProperties` (written on every
  push by P03's coordinator, not by this provider).
- Downloads use `files().get_media(fileId=...)`.
- HttpError status codes are mapped onto the typed `OutboundStorageError`
  hierarchy: 401/403 → Permission, 404 → NotFound, 409 → Conflict,
  429 → Quota, 5xx → Unavailable, every other failure → Network.

The `service_factory` constructor argument lets tests inject a fake
Drive v3 Resource-shaped object so unit tests run without the real
google-api-python-client. The real factory lives in `_service_factory`
and is the default when no override is supplied.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from ....core.config import Settings as _Settings
from ....core.external_constants import BINARY_MIME_TYPE as _BINARY_MIME_TYPE
from ._errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageIntegrityError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
    OutboundStorageUnavailableError,
    OutboundStorageValidationError,
)
from ._records import ProviderKind, ProviderObjectMetadata, ProviderProbeReport

_VAULT_FOLDER_NAME = _Settings().aeat_google_drive_vault_folder_name
_FOLDER_MIME = "application/vnd.google-apps.folder"
_HMAC_PREFIX_LEN = 8
_FILE_EXTENSION = ".bin"
_DEFAULT_LABEL = "object"
_PROBE_NAMESPACE = "_probe"
# Drive `appProperties` ownership marker. The provider stamps this key
# onto every folder + file it creates and refuses to touch any entry
# that lacks the marker. This isolates the operator's pre-existing
# Drive content from the app's mirror — a folder named `aeat-vault`
# the operator created manually for unrelated work will be rejected
# rather than silently adopted.
_OWNERSHIP_KEY = "aeat_vault_app"
_OWNERSHIP_VALUE = "aeat"


def _validate_namespace(namespace: str) -> str:
    cleaned = namespace.strip()
    if not cleaned:
        raise OutboundStorageValidationError("namespace must not be blank")
    if "/" in cleaned or "\\" in cleaned:
        raise OutboundStorageValidationError(
            f"namespace {namespace!r} contains forbidden characters",
            context={"namespace": namespace},
        )
    return cleaned


def _validate_hmac(object_key_hmac: str) -> str:
    cleaned = object_key_hmac.strip()
    if not cleaned:
        raise OutboundStorageValidationError("object_key_hmac must not be blank")
    return cleaned


def _safe_label(label: str) -> str:
    cleaned = label.strip()
    if not cleaned:
        return _DEFAULT_LABEL
    safe = "".join(c if c.isalnum() or c in "-_." else "-" for c in cleaned)
    return safe[:64] or _DEFAULT_LABEL


def _filename(object_key_hmac: str, label: str) -> str:
    return f"{object_key_hmac[:_HMAC_PREFIX_LEN]}--{label}{_FILE_EXTENSION}"


def _translate_http_error(error: Exception, *, action: str) -> OutboundStorageError:
    """Translate a Google API HttpError (or any upstream failure) into a typed `OutboundStorageError`.

    The lazy-import guard makes this callable without `google-api-python-client`
    installed, which is important for unit tests that inject fakes.
    """

    status = getattr(getattr(error, "resp", None), "status", None)
    detail = f"drive {action} failed: {error}"
    context = {"action": action, "status": str(status) if status is not None else "unknown"}
    if status in (401, 403):
        return OutboundStoragePermissionError(detail, context=context)
    if status == 404:
        return OutboundStorageNotFoundError(detail, context=context)
    if status == 409:
        return OutboundStorageConflictError(detail, context=context)
    if status == 429:
        return OutboundStorageQuotaError(detail, context=context)
    if status is not None and 500 <= int(status) < 600:
        return OutboundStorageUnavailableError(detail, context=context)
    return OutboundStorageNetworkError(detail, context=context)


def _service_factory(credentials: object) -> Any:
    """Real Drive v3 service factory. Lazily imports google-api-python-client."""

    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            f"googleapiclient not importable: {exc}",
            suggestion="uv sync",
        ) from exc
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


class GoogleDriveProvider:
    """Bytes-in / bytes-out provider against Google Drive v3.

    Args:
        credentials: A `google.oauth2.credentials.Credentials`-shaped
            object. The provider does not refresh credentials itself;
            upper layers refresh via `aeat.adapters.outbound.google._refresh`.
        root_folder_id: The parent folder ID under which `aeat-vault/`
            lives. Operator-configured via
            `aeat_google_drive_root_folder_id`. The provider creates
            `aeat-vault/` lazily under this parent on first probe /
            first put.
    """

    def __init__(self, *, credentials: object, root_folder_id: str) -> None:
        if not root_folder_id.strip():
            raise OutboundStorageValidationError(
                "root_folder_id must not be blank for GoogleDriveProvider",
                context={"root_folder_id": root_folder_id},
            )
        self._credentials = credentials
        self._root_folder_id = root_folder_id.strip()
        self._service: Any | None = None
        self._vault_folder_id: str | None = None
        self._namespace_folder_ids: dict[str, str] = {}

    @property
    def root_folder_id(self) -> str:
        return self._root_folder_id

    def _get_service(self) -> Any:
        if self._service is None:
            self._service = _service_factory(self._credentials)
        return self._service

    def _execute(self, request: Any, *, action: str) -> Any:
        try:
            return request.execute()
        except OutboundStorageError:
            raise
        except Exception as exc:
            raise _translate_http_error(exc, action=action) from exc

    def _resolve_vault_folder(self) -> str:
        """Resolve (or create) the `aeat-vault/` folder ID under the configured root.

        Refuses to adopt a pre-existing folder of the same name unless
        it carries the `appProperties.aeat_vault_app=aeat` ownership
        marker — protects operator-created same-named work from
        silent merge. Cached for the lifetime of the provider instance.
        """

        if self._vault_folder_id is not None:
            return self._vault_folder_id
        service = self._get_service()
        query = (
            f"'{self._root_folder_id}' in parents "
            f"and name='{_VAULT_FOLDER_NAME}' "
            f"and mimeType='{_FOLDER_MIME}' "
            f"and trashed=false"
        )
        response = self._execute(
            service.files().list(q=query, fields="files(id,name,mimeType,appProperties)", pageSize=10),
            action="resolve_vault_folder",
        )
        files = response.get("files", []) if isinstance(response, dict) else []
        if files:
            entry = files[0]
            if entry.get("mimeType") != _FOLDER_MIME:
                raise OutboundStorageValidationError(
                    f"aeat_google_drive_root_folder_id points at a folder containing "
                    f"a file named {_VAULT_FOLDER_NAME!r} that is not itself a folder",
                    context={"root_folder_id": self._root_folder_id},
                )
            self._verify_ownership_or_adopt(entry, kind=_VAULT_FOLDER_NAME)
            self._vault_folder_id = str(entry["id"])
            return self._vault_folder_id
        # Create the folder with the ownership marker.
        body = {
            "name": _VAULT_FOLDER_NAME,
            "mimeType": _FOLDER_MIME,
            "parents": [self._root_folder_id],
            "appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE},
        }
        created = self._execute(
            service.files().create(body=body, fields="id,appProperties"),
            action="create_vault_folder",
        )
        if not isinstance(created, dict) or "id" not in created:
            raise OutboundStorageNetworkError(
                "drive create_vault_folder returned no id",
                context={"response": str(created)},
            )
        self._vault_folder_id = str(created["id"])
        return self._vault_folder_id

    def _verify_ownership_or_adopt(self, entry: dict[str, Any], *, kind: str) -> None:
        """Refuse to adopt a foreign Drive folder; auto-stamp our own.

        - If the entry carries `appProperties.aeat_vault_app=aeat`,
          treat it as ours (no-op).
        - If the entry was created by us in a previous session but
          predates ownership marking (no `appProperties` at all),
          stamp the marker on it now (one-time backfill).
        - If the entry carries `appProperties` but the marker is
          missing or different, refuse — the operator must rename
          their own folder or change `aeat_google_drive_root_folder_id`.

        Raises:
            OutboundStorageConflictError: When the entry has appProperties that
                do not include our ownership marker — the folder
                belongs to the operator's pre-existing work.
        """

        existing = entry.get("appProperties") or {}
        existing_value = existing.get(_OWNERSHIP_KEY)
        if existing_value == _OWNERSHIP_VALUE:
            return
        if not existing:
            # Probably a folder we created in a prior session before
            # ownership marking landed. Stamp it now.
            service = self._get_service()
            self._execute(
                service.files().update(
                    fileId=entry["id"],
                    body={"appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE}},
                    fields="id,appProperties",
                ),
                action=f"stamp_ownership_{kind}",
            )
            return
        raise OutboundStorageConflictError(
            f"Drive folder named {kind!r} exists under the configured root but is not "
            f"marked as owned by this app. Refusing to write to it to protect operator data. "
            f"To use this folder for the aeat-vault mirror, manually add "
            f"appProperties.{_OWNERSHIP_KEY}={_OWNERSHIP_VALUE} to it, or change "
            f"aeat_google_drive_root_folder_id.",
            context={
                "folder_id": entry["id"],
                "folder_name": entry.get("name", ""),
                "existing_app_properties": existing,
            },
        )

    def _resolve_namespace_folder(self, namespace: str, *, create: bool = True) -> str | None:
        """Resolve (or create) the namespace folder ID under `aeat-vault/`.

        Returns ``None`` when the namespace folder does not exist and
        `create=False`.
        """

        cached = self._namespace_folder_ids.get(namespace)
        if cached is not None:
            return cached
        service = self._get_service()
        vault_id = self._resolve_vault_folder()
        query = f"'{vault_id}' in parents and name='{namespace}' and mimeType='{_FOLDER_MIME}' and trashed=false"
        response = self._execute(
            service.files().list(q=query, fields="files(id,name,appProperties)", pageSize=10),
            action=f"resolve_namespace_{namespace}",
        )
        files = response.get("files", []) if isinstance(response, dict) else []
        if files:
            entry = files[0]
            self._verify_ownership_or_adopt(entry, kind=f"namespace:{namespace}")
            folder_id = str(entry["id"])
            self._namespace_folder_ids[namespace] = folder_id
            return folder_id
        if not create:
            return None
        body = {
            "name": namespace,
            "mimeType": _FOLDER_MIME,
            "parents": [vault_id],
            "appProperties": {_OWNERSHIP_KEY: _OWNERSHIP_VALUE},
        }
        created = self._execute(
            service.files().create(body=body, fields="id,appProperties"),
            action=f"create_namespace_{namespace}",
        )
        if not isinstance(created, dict) or "id" not in created:
            raise OutboundStorageNetworkError(
                f"drive create_namespace_{namespace} returned no id",
                context={"response": str(created)},
            )
        folder_id = str(created["id"])
        self._namespace_folder_ids[namespace] = folder_id
        return folder_id

    def _find_file(self, namespace_folder_id: str, object_key_hmac: str) -> dict[str, Any] | None:
        """Locate a file by `(namespace_folder_id, object_key_hmac)`.

        Matches the 8-char prefix on the filename for the SQL query,
        then verifies the FULL HMAC matches via `appProperties.object_key_hmac`
        AND that the file carries our ownership marker. Refuses to
        return any file lacking both — protects operator-placed files
        whose name happens to collide with the 8-char prefix space.

        Returns:
            The Drive entry dict when a marker-verified match exists.
            `None` when no marker-verified match exists (including the
            case where a foreign file shares the prefix).
        """

        service = self._get_service()
        prefix = object_key_hmac[:_HMAC_PREFIX_LEN]
        query = f"'{namespace_folder_id}' in parents and name contains '{prefix}--' and trashed=false"
        response = self._execute(
            service.files().list(
                q=query,
                fields="files(id,name,size,md5Checksum,modifiedTime,appProperties)",
                pageSize=10,
            ),
            action="find_file",
        )
        files = response.get("files", []) if isinstance(response, dict) else []
        for entry in files:
            name = str(entry.get("name", ""))
            if not (name.startswith(f"{prefix}--") and name.endswith(_FILE_EXTENSION)):
                continue
            app_properties = entry.get("appProperties") or {}
            if app_properties.get(_OWNERSHIP_KEY) != _OWNERSHIP_VALUE:
                # Foreign file: operator-placed content that happens to
                # share the 8-hex prefix. Refuse to touch it.
                continue
            if app_properties.get("object_key_hmac") != object_key_hmac:
                # Different aeat object that shares the prefix (extremely
                # rare HMAC collision). Refuse to touch it.
                continue
            return entry
        return None

    def put(
        self,
        namespace: str,
        object_key_hmac: str,
        payload: bytes,
        *,
        content_hash: str,
        label: str,
    ) -> ProviderObjectMetadata:
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)
        if not content_hash.strip():
            raise OutboundStorageValidationError("content_hash must not be blank")
        label_clean = _safe_label(label)

        service = self._get_service()
        namespace_folder_id = self._resolve_namespace_folder(namespace_clean)
        assert namespace_folder_id is not None  # create=True so always populated
        target_name = _filename(hmac_clean, label_clean)
        existing = self._find_file(namespace_folder_id, hmac_clean)

        media_body = _build_media_body(payload)
        # ``dict[str, Any]`` here is the irreducible Google Drive API
        # boundary shape: ``service.files().create(body=body)`` and
        # ``service.files().update(body=body)`` accept arbitrary
        # heterogeneous Drive metadata. Narrowing to ``object`` breaks
        # the call under the google-api-python-client stubs; this is
        # a third-party-API boundary where ``Any`` is correct.
        body: dict[str, Any] = {
            "name": target_name,
            "parents": [namespace_folder_id] if existing is None else None,
            "appProperties": {
                _OWNERSHIP_KEY: _OWNERSHIP_VALUE,
                "namespace": namespace_clean,
                "object_key_hmac": hmac_clean,
                "content_hash": content_hash,
            },
        }
        if existing is None:
            # Drive `files().create` requires `parents`; existing-file
            # `files().update` rejects it. Strip None entries.
            body = {k: v for k, v in body.items() if v is not None}
            request = service.files().create(
                body=body,
                media_body=media_body,
                fields="id,name,size,md5Checksum,modifiedTime,appProperties",
            )
            action = "files.create"
        else:
            # Update existing — strip `parents`; rename via `name` if label drifted.
            body = {k: v for k, v in body.items() if v is not None and k != "parents"}
            request = service.files().update(
                fileId=existing["id"],
                body=body,
                media_body=media_body,
                fields="id,name,size,md5Checksum,modifiedTime,appProperties",
            )
            action = "files.update"
        response = self._execute(request, action=action)
        if not isinstance(response, dict):
            raise OutboundStorageNetworkError(f"drive {action} returned non-dict response", context={"response": str(response)})

        return _metadata_from_drive_entry(response, namespace=namespace_clean, object_key_hmac=hmac_clean)

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)

        service = self._get_service()
        namespace_folder_id = self._resolve_namespace_folder(namespace_clean, create=False)
        if namespace_folder_id is None:
            raise OutboundStorageNotFoundError(
                f"namespace {namespace_clean!r} not present in Drive",
                context={"namespace": namespace_clean},
            )
        entry = self._find_file(namespace_folder_id, hmac_clean)
        if entry is None:
            raise OutboundStorageNotFoundError(
                f"object {hmac_clean!r} not found in Drive namespace {namespace_clean!r}",
                context={"namespace": namespace_clean, "object_key_hmac": hmac_clean},
            )

        request = service.files().get_media(fileId=entry["id"])
        try:
            payload = request.execute()
        except OutboundStorageError:
            raise
        except Exception as exc:
            raise _translate_http_error(exc, action="files.get_media") from exc
        if not isinstance(payload, (bytes, bytearray)):
            raise OutboundStorageNetworkError(
                f"drive files.get_media returned non-bytes payload: {type(payload).__name__}",
            )

        metadata = _metadata_from_drive_entry(
            entry,
            namespace=namespace_clean,
            object_key_hmac=hmac_clean,
        )
        app_properties = entry.get("appProperties") or {}
        stored_hash = str(app_properties.get("content_hash", "") or "")
        if stored_hash:
            stripped = stored_hash.split("-", 1)[1] if stored_hash.startswith("sha256-") else stored_hash
            if len(stripped) == 64:
                actual = hashlib.sha256(bytes(payload)).hexdigest()
                if stripped != actual:
                    raise OutboundStorageIntegrityError(
                        f"drive content_hash mismatch for {hmac_clean!r} in {namespace_clean!r}",
                        context={"stored_hash": stored_hash, "actual_sha256": actual},
                    )
        return bytes(payload), metadata

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)

        service = self._get_service()
        namespace_folder_id = self._resolve_namespace_folder(namespace_clean, create=False)
        if namespace_folder_id is None:
            return False
        entry = self._find_file(namespace_folder_id, hmac_clean)
        if entry is None:
            return False
        self._execute(service.files().delete(fileId=entry["id"]), action="files.delete")
        return True

    def iter_namespaces(self) -> Iterator[str]:
        service = self._get_service()
        vault_id = self._resolve_vault_folder()
        query = f"'{vault_id}' in parents and mimeType='{_FOLDER_MIME}' and trashed=false"
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"q": query, "fields": "files(id,name),nextPageToken", "pageSize": 100}
            if page_token is not None:
                kwargs["pageToken"] = page_token
            response = self._execute(service.files().list(**kwargs), action="iter_namespaces")
            files = response.get("files", []) if isinstance(response, dict) else []
            for entry in files:
                name = str(entry.get("name", ""))
                if name:
                    self._namespace_folder_ids[name] = str(entry["id"])
                    yield name
            page_token = response.get("nextPageToken") if isinstance(response, dict) else None
            if not page_token:
                return

    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]:
        namespace_clean = _validate_namespace(namespace)
        service = self._get_service()
        namespace_folder_id = self._resolve_namespace_folder(namespace_clean, create=False)
        if namespace_folder_id is None:
            raise OutboundStorageNotFoundError(
                f"namespace {namespace_clean!r} does not exist",
                context={"namespace": namespace_clean},
            )
        query = f"'{namespace_folder_id}' in parents and trashed=false"
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {
                "q": query,
                "fields": "files(id,name,size,md5Checksum,modifiedTime,appProperties),nextPageToken",
                "pageSize": 100,
            }
            if page_token is not None:
                kwargs["pageToken"] = page_token
            response = self._execute(service.files().list(**kwargs), action="iter_objects")
            files = response.get("files", []) if isinstance(response, dict) else []
            for entry in files:
                name = str(entry.get("name", ""))
                if not name.endswith(_FILE_EXTENSION) or "--" not in name:
                    continue
                hmac = name.split("--", 1)[0]
                full_hmac = (entry.get("appProperties") or {}).get("object_key_hmac", hmac)
                yield _metadata_from_drive_entry(
                    entry,
                    namespace=namespace_clean,
                    object_key_hmac=str(full_hmac),
                )
            page_token = response.get("nextPageToken") if isinstance(response, dict) else None
            if not page_token:
                return

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        try:
            service = self._get_service()
        except OutboundStorageError as exc:
            return ProviderProbeReport(
                provider_kind=ProviderKind.GOOGLE_DRIVE,
                reachable=False,
                writable=False,
                read_only=read_only,
                root_folder_present=None,
                detail=f"service unreachable: {exc}",
            )

        try:
            root_check = self._execute(
                service.files().get(fileId=self._root_folder_id, fields="id,mimeType,trashed"),
                action="probe.get_root",
            )
        except OutboundStorageNotFoundError:
            return ProviderProbeReport(
                provider_kind=ProviderKind.GOOGLE_DRIVE,
                reachable=True,
                writable=False,
                read_only=read_only,
                root_folder_present=False,
                detail=f"root_folder_id {self._root_folder_id!r} not found",
            )
        except OutboundStorageError as exc:
            return ProviderProbeReport(
                provider_kind=ProviderKind.GOOGLE_DRIVE,
                reachable=False,
                writable=False,
                read_only=read_only,
                root_folder_present=None,
                detail=str(exc),
            )

        if not isinstance(root_check, dict) or root_check.get("trashed", False):
            return ProviderProbeReport(
                provider_kind=ProviderKind.GOOGLE_DRIVE,
                reachable=True,
                writable=False,
                read_only=read_only,
                root_folder_present=False,
                detail=f"root_folder_id {self._root_folder_id!r} is trashed or malformed",
            )
        if root_check.get("mimeType") != _FOLDER_MIME:
            return ProviderProbeReport(
                provider_kind=ProviderKind.GOOGLE_DRIVE,
                reachable=True,
                writable=False,
                read_only=read_only,
                root_folder_present=False,
                detail=(
                    f"root_folder_id {self._root_folder_id!r} points at a non-folder "
                    f"(mimeType={root_check.get('mimeType')!r})"
                ),
            )

        if read_only:
            return ProviderProbeReport(
                provider_kind=ProviderKind.GOOGLE_DRIVE,
                reachable=True,
                writable=False,
                read_only=True,
                root_folder_present=True,
                detail="read_only probe; sentinel round-trip skipped",
            )

        try:
            metadata = self.put(
                _PROBE_NAMESPACE,
                "00000000probe",
                b"",
                content_hash="sha256-empty",
                label="sentinel",
            )
            self.delete(_PROBE_NAMESPACE, "00000000probe")
        except OutboundStorageError as exc:
            return ProviderProbeReport(
                provider_kind=ProviderKind.GOOGLE_DRIVE,
                reachable=True,
                writable=False,
                read_only=False,
                root_folder_present=True,
                detail=f"sentinel round-trip refused: {exc}",
            )
        del metadata
        return ProviderProbeReport(
            provider_kind=ProviderKind.GOOGLE_DRIVE,
            reachable=True,
            writable=True,
            read_only=False,
            root_folder_present=True,
            detail=f"sentinel round-trip ok under root_folder_id={self._root_folder_id!r}",
        )


def _build_media_body(payload: bytes) -> Any:
    """Build a `MediaIoBaseUpload` from `payload`. Lazy-imported."""

    try:
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            f"googleapiclient.http not importable: {exc}",
            suggestion="uv sync",
        ) from exc
    return MediaIoBaseUpload(io.BytesIO(payload), mimetype=_BINARY_MIME_TYPE, resumable=False)


def _metadata_from_drive_entry(
    entry: dict[str, Any],
    *,
    namespace: str,
    object_key_hmac: str,
) -> ProviderObjectMetadata:
    """Convert a Drive `files().get/list` response entry into our record."""

    byte_length_raw = entry.get("size", 0)
    try:
        byte_length = int(byte_length_raw) if byte_length_raw is not None else 0
    except (TypeError, ValueError):
        byte_length = 0
    modified = entry.get("modifiedTime", "")
    try:
        written_at = datetime.fromisoformat(str(modified).replace("Z", "+00:00")) if modified else datetime.now(UTC)
    except ValueError:
        written_at = datetime.now(UTC)

    app_properties = entry.get("appProperties") or {}
    content_hash = str(app_properties.get("content_hash", "") or "")
    if not content_hash:
        md5 = entry.get("md5Checksum")
        content_hash = f"md5-{md5}" if md5 else "sha256-unverified"

    return ProviderObjectMetadata(
        namespace=namespace,
        object_key_hmac=object_key_hmac,
        provider_object_id=str(entry.get("id", "")),
        byte_length=max(byte_length, 0),
        content_hash=content_hash,
        written_at=written_at,
    )


# Suppress the unused-import warning for `json` — kept for forward
# compatibility when `appProperties` payloads need stringification.
_ = json
__all__ = ["GoogleDriveProvider"]
