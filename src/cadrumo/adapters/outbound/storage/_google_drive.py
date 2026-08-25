"""Google Drive v3 :class:`adapters.outbound.storage.StorageProvider` implementation.

Maps the :class:`adapters.outbound.storage.StorageProvider` Protocol onto
the Drive API:

- Each namespace is a folder directly under the operator-configured
  ``cadrumo-vault/`` root. The root folder ID is required when
  ``cadrumo_storage_provider_kind=google_drive`` and the vault folder is created
  lazily under ``cadrumo_google_drive_root_folder_id``.
- Each object is a ``files().create(...)`` upload with
  ``mimeType=application/octet-stream``, named
  ``<hmac_prefix_8>--<label>.bin``. The Drive ``appProperties`` field carries
  the ownership marker, namespace, full object-key HMAC, and stored
  ``content_hash`` used to construct
  :class:`adapters.outbound.storage.ProviderObjectMetadata`.
- Downloads use ``files().get_media(fileId=...)`` and validate full SHA-256
  payload hashes through
  :func:`adapters.outbound.storage._integrity.verify_content_hash`.
- HttpError status codes are mapped onto the typed
  :class:`adapters.outbound.storage.OutboundStorageError` hierarchy:
  401/403 -> :class:`adapters.outbound.storage.OutboundStoragePermissionError`,
  404 -> :class:`adapters.outbound.storage.OutboundStorageNotFoundError`,
  409 -> :class:`adapters.outbound.storage.OutboundStorageConflictError`,
  429 -> :class:`adapters.outbound.storage.OutboundStorageQuotaError`,
  5xx -> :class:`adapters.outbound.storage.OutboundStorageUnavailableError`,
  every other failure ->
  :class:`adapters.outbound.storage.OutboundStorageNetworkError`.

The :func:`_service_factory` helper constructs the real Drive v3 resource
lazily so importing this module does not require google-api-python-client or
settings initialization.
"""

from __future__ import annotations

import io
from collections.abc import Iterator, Mapping
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from ....application.operator_actions import no_action_precondition_verdict
from ....core import ActionEvidenceProvenance, NoRecoveryOutcome
from ....core.config import FORMER_PRODUCT_GOOGLE_DRIVE_VAULT_FOLDER_NAME, load_settings
from ....core.errors import CoreValidationError
from ....core.external_constants import BINARY_MIME_TYPE as _BINARY_MIME_TYPE
from ....core.hashing import sha256_hex
from ....core.logging import get_logger
from ....core.time import parse_iso_datetime, validate_utc_aware
from ._drive_pagination import next_drive_page_token
from .errors import (
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
from ._integrity import require_full_sha256_content_hash, verify_content_hash, verify_payload_byte_length
from ._key_validation import assert_admissible_object_key_hmac
from ._object_name import build_provider_object_name, provider_object_hmac_prefix, sanitize_provider_object_label
from ._records import ProviderKind, ProviderObjectMetadata, ProviderProbeReport

if TYPE_CHECKING:
    from ..google import DriveAppProperties

_FOLDER_MIME = "application/vnd.google-apps.folder"
_FILE_EXTENSION = ".bin"
_PROBE_NAMESPACE = "_probe"
# Drive `appProperties` ownership marker. The provider stamps this key
# onto every folder + file it creates and refuses to touch any entry
# that lacks the marker. This isolates the operator's pre-existing
# Drive content from the app's mirror — a folder named `cadrumo-vault`
# the operator created manually for unrelated work will be rejected
# rather than silently adopted.
_OWNERSHIP_KEY = "cadrumo_vault_app"
_OWNERSHIP_VALUE = "cadrumo"
_LOG = get_logger(__name__)


class DriveStoragePreconditionCondition(StrEnum):
    """Closed terminal conditions for observed Google Drive provider failures."""

    API_CLIENT_AVAILABLE = "storage.google_drive.api_client.available"
    REQUEST_AUTHORIZED = "storage.google_drive.request.authorized"
    TARGET_PRESENT = "storage.google_drive.target.present"
    REQUEST_CONFLICT_FREE = "storage.google_drive.request.conflict_free"
    REQUEST_WITHIN_QUOTA = "storage.google_drive.request.within_quota"
    REQUEST_AVAILABLE = "storage.google_drive.request.available"
    REQUEST_TRANSPORT_AVAILABLE = "storage.google_drive.request.transport_available"
    RESPONSE_IDENTIFIER_PRESENT = "storage.google_drive.response.identifier_present"
    OWNERSHIP_ALIGNED = "storage.google_drive.ownership.aligned"
    RESPONSE_MAPPING = "storage.google_drive.response.mapping"
    NAMESPACE_PRESENT = "storage.google_drive.namespace.present"
    OBJECT_PRESENT = "storage.google_drive.object.present"
    MEDIA_PAYLOAD_BYTES = "storage.google_drive.media.payload_bytes"
    METADATA_SIZE_VALID = "storage.google_drive.metadata.size_valid"
    METADATA_MODIFIED_TIME_VALID = "storage.google_drive.metadata.modified_time_valid"
    METADATA_APP_PROPERTIES_VALID = "storage.google_drive.metadata.app_properties_valid"


def _drive_external_verdict(
    condition: DriveStoragePreconditionCondition,
    *,
    facts: Mapping[str, str | bool],
    outcome: NoRecoveryOutcome,
):
    """Project an observed Drive-provider refusal through the public no-action authority."""
    return no_action_precondition_verdict(
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=outcome,
    )


def _drive_validation_verdict(
    condition_id: str,
    *,
    field: str,
    provenance: ActionEvidenceProvenance,
):
    return no_action_precondition_verdict(
        condition_id=condition_id,
        facts={"backend": "google_drive", "field": field, "valid": False},
        provenance=provenance,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def _validate_namespace(namespace: str) -> str:
    cleaned = namespace.strip()
    if not cleaned:
        raise OutboundStorageValidationError(
            "namespace must not be blank",
            translated_message="adapters.outbound.storage.google_drive.errors.namespace_blank",
            precondition_verdict=_drive_validation_verdict(
                "storage.google_drive.namespace.valid",
                field="namespace",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        )
    if "/" in cleaned or "\\" in cleaned:
        raise OutboundStorageValidationError(
            "namespace contains forbidden characters",
            context={"namespace": namespace},
            translated_message="adapters.outbound.storage.google_drive.errors.namespace_forbidden_characters",
            precondition_verdict=_drive_validation_verdict(
                "storage.google_drive.namespace.valid",
                field="namespace",
                provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
            ),
        )
    return cleaned


def _validate_hmac(object_key_hmac: str) -> str:
    """Delegate to the one admissibility rule both backends share.

    This backend previously accepted any non-blank value, so the delegation
    NARROWS what it admits. Deliberate: the key is a contract-level digest and
    nothing legitimate produces a character outside the admissible set.
    """
    return assert_admissible_object_key_hmac(object_key_hmac, backend="google_drive")


def _translate_http_error(error: Exception, *, action: str) -> OutboundStorageError:
    """Translate a Google API HttpError into a typed :class:`OutboundStorageError`.

    The lazy-import guard makes this callable without ``google-api-python-client``
    installed, which is important for unit tests that inject fakes.
    """
    status = getattr(getattr(error, "resp", None), "status", None)
    detail = "drive request failed"
    context = {"action": action, "status": str(status) if status is not None else "unknown"}
    if status in (401, 403):
        return OutboundStoragePermissionError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_AUTHORIZED,
                facts={"operation": action, "status": context["status"], "authorization_sufficient": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    if status == 404:
        return OutboundStorageNotFoundError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.TARGET_PRESENT,
                facts={"operation": action, "status": context["status"], "target_present": False},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        )
    if status == 409:
        return OutboundStorageConflictError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_CONFLICT_FREE,
                facts={"operation": action, "status": context["status"], "conflict_detected": True},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        )
    if status == 429:
        return OutboundStorageQuotaError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_WITHIN_QUOTA,
                facts={"operation": action, "status": context["status"], "quota_available": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    if status is not None and 500 <= int(status) < 600:
        return OutboundStorageUnavailableError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_AVAILABLE,
                facts={"operation": action, "status": context["status"], "available": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return OutboundStorageNetworkError(
        detail,
        context=context,
        translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
        precondition_verdict=_drive_external_verdict(
            DriveStoragePreconditionCondition.REQUEST_TRANSPORT_AVAILABLE,
            facts={"operation": action, "status": context["status"], "transport_available": False},
            outcome=NoRecoveryOutcome.SAFETY,
        ),
    )


# ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY:
# googleapiclient.discovery.build() returns an untyped Resource object; no stub
# narrows the concrete type.
def _service_factory(credentials: object) -> Any:  # ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY
    """Real Drive v3 service factory. Lazily imports google-api-python-client."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            "googleapiclient is not importable",
            context={"dependency": "google-api-python-client"},
            translated_message="adapters.outbound.storage.google_drive.errors.googleapiclient_import_failed",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.API_CLIENT_AVAILABLE,
                facts={"component": "discovery", "client_available": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc
    return build("drive", "v3", credentials=credentials, cache_discovery=False)


def _is_owned_drive_match(entry: dict[str, Any], *, prefix: str, object_key_hmac: str) -> bool:
    """Confirm a listed Drive entry is THIS object and is Cadrumo-owned.

    The 8-hex filename prefix is only a search key, so a listing can return
    entries this provider must not touch: a foreign file (operator-placed
    content that happens to share the prefix) and a different Cadrumo object
    that collides on the prefix (an extremely rare HMAC collision) are both
    refused here rather than matched.
    """
    name = str(entry.get("name", ""))
    if not (name.startswith(f"{prefix}--") and name.endswith(_FILE_EXTENSION)):
        return False
    app_properties = entry.get("appProperties")
    if not isinstance(app_properties, Mapping):
        return False
    ownership = app_properties.get(_OWNERSHIP_KEY)
    stored_hmac = app_properties.get("object_key_hmac")
    return (
        isinstance(ownership, str)
        and ownership == _OWNERSHIP_VALUE
        and isinstance(stored_hmac, str)
        and stored_hmac == object_key_hmac
    )


class GoogleDriveProvider:
    """Bytes-in / bytes-out :class:`StorageProvider` backed by Google Drive v3."""

    def __init__(self, *, credentials: object, root_folder_id: str, vault_folder_name: str | None = None) -> None:
        """Initialise the provider with credentials and the root Drive folder.

        Args:
            credentials: A ``google.oauth2.credentials.Credentials``-shaped object.
            root_folder_id: Parent folder ID under which the vault folder lives.
            vault_folder_name: Optional configured vault folder name. Defaults
                to the centralized settings value.

        Raises:
            :class:`OutboundStorageValidationError`: When ``root_folder_id`` or
                ``vault_folder_name`` is blank.
        """
        if not root_folder_id.strip():
            raise OutboundStorageValidationError(
                "root_folder_id must not be blank for GoogleDriveProvider",
                context={"root_folder_id": root_folder_id},
                translated_message="adapters.outbound.storage.google_drive.errors.root_folder_id_blank",
                precondition_verdict=_drive_validation_verdict(
                    "storage.google_drive.root_folder_id.present",
                    field="root_folder_id",
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                ),
            )
        vault_folder_name_resolved = (
            vault_folder_name
            if vault_folder_name is not None
            else load_settings().cadrumo_google_drive_vault_folder_name
        ).strip()
        if not vault_folder_name_resolved:
            raise OutboundStorageValidationError(
                "vault_folder_name must not be blank for GoogleDriveProvider",
                translated_message="adapters.outbound.storage.google_drive.errors.vault_folder_name_blank",
                precondition_verdict=_drive_validation_verdict(
                    "storage.google_drive.vault_folder_name.valid",
                    field="vault_folder_name",
                    provenance=(
                        ActionEvidenceProvenance.RUNTIME_OBSERVATION
                        if vault_folder_name is not None
                        else ActionEvidenceProvenance.APPLICATION_STATE
                    ),
                ),
            )
        if vault_folder_name_resolved.casefold() == FORMER_PRODUCT_GOOGLE_DRIVE_VAULT_FOLDER_NAME:
            raise OutboundStorageValidationError(
                "the former product Google Drive vault folder is not supported",
                context={"vault_folder_name": vault_folder_name_resolved},
                translated_message="adapters.outbound.storage.google_drive.errors.former_vault_folder",
                precondition_verdict=_drive_validation_verdict(
                    "storage.google_drive.vault_folder_name.valid",
                    field="vault_folder_name",
                    provenance=(
                        ActionEvidenceProvenance.RUNTIME_OBSERVATION
                        if vault_folder_name is not None
                        else ActionEvidenceProvenance.APPLICATION_STATE
                    ),
                ),
            )
        self._credentials = credentials
        self._root_folder_id = root_folder_id.strip()
        self._vault_folder_name = vault_folder_name_resolved
        self._service: Any | None = None
        self._vault_folder_id: str | None = None
        self._namespace_folder_ids: dict[str, str] = {}

    @property
    def root_folder_id(self) -> str:
        """Drive folder ID used as the parent of the configured vault folder."""
        return self._root_folder_id

    # ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY:
    # googleapiclient.discovery.build() returns an untyped Resource object; no
    # stub narrows the concrete type.
    def _get_service(self) -> Any:  # ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY
        if self._service is None:
            self._service = _service_factory(self._credentials)
        return self._service

    # ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY:
    # googleapiclient.discovery.build() returns an untyped Resource object; no
    # stub narrows the concrete type.
    def _execute(self, request: Any, *, action: str) -> Any:  # ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY
        translated_error: OutboundStorageError | None = None
        try:
            return request.execute()
        except OutboundStorageError:
            raise
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            _LOG.debug(
                "Google Drive request failed during %s with status=%s error_type=%s",
                action,
                str(status) if status is not None else "unknown",
                type(exc).__name__,
            )
            translated_error = _translate_http_error(exc, action=action)
        if translated_error is not None:
            raise translated_error
        raise OutboundStorageNetworkError(
            "drive request failed without translated error",
            context={"action": action, "status": "unknown"},
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_TRANSPORT_AVAILABLE,
                facts={"operation": action, "status": "unknown", "transport_available": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )

    def _resolve_vault_folder(self) -> str:
        """Resolve or create the configured vault folder under ``root_folder_id``.

        Refuses to adopt a pre-existing folder of the same name unless
        it carries the ``appProperties.cadrumo_vault_app=cadrumo`` ownership
        marker — protects operator-created same-named work from
        silent merge. Cached for the lifetime of the provider instance.
        """
        if self._vault_folder_id is not None:
            return self._vault_folder_id
        service = self._get_service()
        query = (
            f"'{self._root_folder_id}' in parents "
            f"and name='{self._vault_folder_name}' "
            f"and mimeType='{_FOLDER_MIME}' "
            f"and trashed=false"
        )
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            kwargs: dict[str, Any] = {
                "q": query,
                "fields": "files(id,name,mimeType,appProperties),nextPageToken",
                "pageSize": 10,
            }
            if page_token is not None:
                kwargs["pageToken"] = page_token
            response = self._execute(service.files().list(**kwargs), action="resolve_vault_folder")
            files = response.get("files", []) if isinstance(response, dict) else []
            for entry in files:
                if entry.get("mimeType") != _FOLDER_MIME:
                    raise OutboundStorageValidationError(
                        "configured Drive root contains a vault-name entry that is not a folder",
                        context={"root_folder_id": self._root_folder_id, "vault_folder_name": self._vault_folder_name},
                        translated_message="adapters.outbound.storage.google_drive.errors.vault_entry_not_folder",
                        precondition_verdict=_drive_validation_verdict(
                            "storage.google_drive.vault_entry.folder",
                            field="vault_folder_entry",
                            provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                        ),
                    )
                self.verify_ownership_or_adopt(entry, kind=self._vault_folder_name)
                self._vault_folder_id = str(entry["id"])
                return self._vault_folder_id
            page_token = next_drive_page_token(
                response.get("nextPageToken") if isinstance(response, dict) else None,
                seen_tokens=seen_tokens,
                action="resolve_vault_folder",
            )
            if page_token is None:
                break
        # Create the folder with the ownership marker.
        body = {
            "name": self._vault_folder_name,
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
                translated_message="adapters.outbound.storage.google_drive.errors.create_vault_folder_no_id",
                precondition_verdict=_drive_external_verdict(
                    DriveStoragePreconditionCondition.RESPONSE_IDENTIFIER_PRESENT,
                    facts={
                        "operation": "create_vault_folder",
                        "response_mapping": isinstance(created, dict),
                        "identifier_present": isinstance(created, dict) and "id" in created,
                    },
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )
        self._vault_folder_id = str(created["id"])
        return self._vault_folder_id

    # ADAPTER-INTERNAL-ALIAS-RATIONALE-DRIVE-ENTRY: raw Google Drive API file
    # resource (untyped googleapiclient dict); narrowed via explicit key access.
    def _verify_ownership_or_adopt(self, entry: dict[str, Any], *, kind: str) -> None:
        """Refuse to adopt a foreign Drive folder; auto-stamp our own.

        - If the entry carries ``appProperties.cadrumo_vault_app=cadrumo``, treat it as ours (no-op).
        - If predates ownership marking (no ``appProperties``), stamp the marker now.
        - If the marker is missing or different, refuse.

        Args:
            entry: Drive Files API resource dict for the candidate folder.
            kind: Human-readable label for the folder kind used in error messages.

        Raises:
            OutboundStorageConflictError: When the entry has appProperties that
                do not include our ownership marker.
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
            "Drive folder exists under the configured root but is not marked as owned by this app",
            context={
                "folder_id": entry["id"],
                "folder_name": entry.get("name", ""),
                "ownership_key": _OWNERSHIP_KEY,
                "ownership_value": _OWNERSHIP_VALUE,
            },
            translated_message="adapters.outbound.storage.google_drive.errors.folder_not_owned",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.OWNERSHIP_ALIGNED,
                facts={"ownership_aligned": False},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        )

    def _resolve_namespace_folder(self, namespace: str, *, create: bool = True) -> str | None:
        """Resolve or create the namespace folder ID under the vault folder.

        Returns ``None`` when the namespace folder does not exist and
        ``create=False``.
        """
        cached = self._namespace_folder_ids.get(namespace)
        if cached is not None:
            return cached
        service = self._get_service()
        vault_id = self._resolve_vault_folder()
        query = f"'{vault_id}' in parents and name='{namespace}' and mimeType='{_FOLDER_MIME}' and trashed=false"
        action = f"resolve_namespace_{namespace}"
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            kwargs: dict[str, Any] = {
                "q": query,
                "fields": "files(id,name,appProperties),nextPageToken",
                "pageSize": 10,
            }
            if page_token is not None:
                kwargs["pageToken"] = page_token
            response = self._execute(service.files().list(**kwargs), action=action)
            files = response.get("files", []) if isinstance(response, dict) else []
            for entry in files:
                self.verify_ownership_or_adopt(entry, kind=f"namespace:{namespace}")
                folder_id = str(entry["id"])
                self._namespace_folder_ids[namespace] = folder_id
                return folder_id
            page_token = next_drive_page_token(
                response.get("nextPageToken") if isinstance(response, dict) else None,
                seen_tokens=seen_tokens,
                action=action,
            )
            if page_token is None:
                break
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
                translated_message="adapters.outbound.storage.google_drive.errors.create_namespace_no_id",
                precondition_verdict=_drive_external_verdict(
                    DriveStoragePreconditionCondition.RESPONSE_IDENTIFIER_PRESENT,
                    facts={
                        "operation": "create_namespace",
                        "response_mapping": isinstance(created, dict),
                        "identifier_present": isinstance(created, dict) and "id" in created,
                    },
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )
        folder_id = str(created["id"])
        self._namespace_folder_ids[namespace] = folder_id
        return folder_id

    def _find_file(self, namespace_folder_id: str, object_key_hmac: str) -> dict[str, Any] | None:
        """Locate a file by ``(namespace_folder_id, object_key_hmac)``.

        Matches the 8-char prefix on the filename, then verifies the FULL HMAC
        via ``appProperties.object_key_hmac`` and the ownership marker.

        Args:
            namespace_folder_id: Drive folder ID for the target namespace.
            object_key_hmac: Full HMAC string used to locate the specific file.

        Returns:
            The Drive entry dict when a marker-verified match exists,
            or ``None`` when no marker-verified match exists.
        """
        service = self._get_service()
        prefix = provider_object_hmac_prefix(object_key_hmac)
        query = f"'{namespace_folder_id}' in parents and name contains '{prefix}--' and trashed=false"
        page_token: str | None = None
        seen_tokens: set[str] = set()
        while True:
            kwargs: dict[str, Any] = {
                "q": query,
                "fields": "files(id,name,size,md5Checksum,modifiedTime,appProperties),nextPageToken",
                "pageSize": 10,
            }
            if page_token is not None:
                kwargs["pageToken"] = page_token
            response = self._execute(service.files().list(**kwargs), action="find_file")
            files = response.get("files", []) if isinstance(response, dict) else []
            for entry in files:
                if _is_owned_drive_match(entry, prefix=prefix, object_key_hmac=object_key_hmac):
                    return entry
            page_token = next_drive_page_token(
                response.get("nextPageToken") if isinstance(response, dict) else None,
                seen_tokens=seen_tokens,
                action="find_file",
            )
            if page_token is None:
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
        r"""Upload ``payload`` to Drive and return :class:`ProviderObjectMetadata`.

        If a file for ``object_key_hmac`` already exists the existing Drive
        file is updated in-place (``files().update``); otherwise a new file
        is created (``files().create``) inside the namespace folder.  The
        ``appProperties`` field on the Drive entry records the HMAC,
        ``content_hash``, namespace, and ownership marker so subsequent
        ``get`` and ``iter_objects`` calls can resolve the entry without
        re-downloading the payload.

        Args:
            namespace: Logical bucket name; becomes a Drive sub-folder of
                ``cadrumo-vault/``.
            object_key_hmac: Full HMAC string that uniquely identifies the
                object.  Only the first 8 characters are used in the Drive
                filename; the full value is stored in ``appProperties``.
            payload: Raw bytes to upload.  The provider is opaque to the
                content; encryption lives at a higher layer.
            content_hash: Vendor-prefixed digest string (e.g.
                ``sha256-<hex>``).  Stored in ``appProperties`` and
                verified on ``get``.
            label: Human-readable filename component, sanitised to
                ``[A-Za-z0-9\\-_.]{1,64}``.

        Returns:
            :class:`ProviderObjectMetadata` populated from the Drive API response.

        Raises:
            :class:`OutboundStorageValidationError`: When ``namespace``,
                ``object_key_hmac``, or ``content_hash`` are blank.
            :class:`OutboundStoragePermissionError`: On HTTP 401 or 403 from
                Drive.
            :class:`OutboundStorageQuotaError`: On HTTP 429 from Drive.
            :class:`OutboundStorageUnavailableError`: On HTTP 5xx from Drive.
            :class:`OutboundStorageNetworkError`: On any other Drive API
                failure.
        """
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)
        if not content_hash.strip():
            raise OutboundStorageValidationError(
                "content_hash must not be blank",
                translated_message="adapters.outbound.storage.google_drive.errors.content_hash_blank",
                precondition_verdict=_drive_validation_verdict(
                    "storage.google_drive.content_hash.present",
                    field="content_hash",
                    provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
                ),
            )
        label_clean = sanitize_provider_object_label(label)

        service = self._get_service()
        namespace_folder_id = self._resolve_namespace_folder(namespace_clean)
        assert namespace_folder_id is not None  # create=True so always populated
        target_name = build_provider_object_name(hmac_clean, label_clean, extension=_FILE_EXTENSION)
        existing = self._find_file(namespace_folder_id, hmac_clean)

        media_body = _build_media_body(payload)
        from ..google import DriveAppProperties

        app_properties = DriveAppProperties(
            cadrumo_vault_app=_OWNERSHIP_VALUE,
            namespace=namespace_clean,
            object_key_hmac=hmac_clean,
            content_hash=content_hash,
        ).model_dump(by_alias=True)
        # ``dict[str, Any]`` here is the irreducible Google Drive API
        # boundary shape: ``service.files().create(body=body)`` and
        # ``service.files().update(body=body)`` accept arbitrary
        # heterogeneous Drive metadata. Narrowing to ``object`` breaks
        # the call under the google-api-python-client stubs; this is
        # a third-party-API boundary where ``Any`` is correct.
        body: dict[str, Any] = {
            "name": target_name,
            "parents": [namespace_folder_id] if existing is None else None,
            "appProperties": app_properties,
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
            raise OutboundStorageNetworkError(
                "drive write returned non-dict response",
                context={"action": action, "response": str(response)},
                translated_message="adapters.outbound.storage.google_drive.errors.write_non_dict_response",
                precondition_verdict=_drive_external_verdict(
                    DriveStoragePreconditionCondition.RESPONSE_MAPPING,
                    facts={"operation": action, "response_mapping": False},
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )

        return _metadata_from_drive_entry(response, namespace=namespace_clean, object_key_hmac=hmac_clean)

    def get(self, namespace: str, object_key_hmac: str) -> tuple[bytes, ProviderObjectMetadata]:
        """Download the object, verify the stored hash, and return payload metadata.

        Uses ``files().get_media`` to stream bytes.  If the stored
        ``content_hash`` is a ``sha256-<hex>`` string, the payload digest is
        recomputed after download and compared through
        :func:`verify_content_hash`; a mismatch raises
        :class:`adapters.outbound.storage.OutboundStorageIntegrityError`
        before the payload is returned.

        Args:
            namespace: Logical bucket name.
            object_key_hmac: Full HMAC string identifying the object.

        Returns:
            A two-tuple containing payload bytes and
            :class:`ProviderObjectMetadata`.

        Raises:
            :class:`OutboundStorageNotFoundError`: When the namespace folder or
                object file is absent from Drive.
            :class:`adapters.outbound.storage.OutboundStorageIntegrityError`:
                When the downloaded payload does not match the stored SHA-256
                digest.
            :class:`OutboundStorageValidationError`: When ``namespace`` or
                ``object_key_hmac`` are blank.
            :class:`OutboundStoragePermissionError`: On HTTP 401 or 403 from
                Drive.
            :class:`OutboundStorageNetworkError`: On any other Drive API
                failure or when ``get_media`` returns a non-bytes value.
        """
        namespace_clean = _validate_namespace(namespace)
        hmac_clean = _validate_hmac(object_key_hmac)

        service = self._get_service()
        namespace_folder_id = self._resolve_namespace_folder(namespace_clean, create=False)
        if namespace_folder_id is None:
            raise OutboundStorageNotFoundError(
                "namespace is not present in Drive",
                context={"namespace": namespace_clean},
                translated_message="adapters.outbound.storage.google_drive.errors.namespace_not_found",
                precondition_verdict=_drive_external_verdict(
                    DriveStoragePreconditionCondition.NAMESPACE_PRESENT,
                    facts={"operation": "get", "namespace_present": False},
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )
        entry = self._find_file(namespace_folder_id, hmac_clean)
        if entry is None:
            raise OutboundStorageNotFoundError(
                "object is not present in Drive namespace",
                context={"namespace": namespace_clean, "object_key_hmac": hmac_clean},
                translated_message="adapters.outbound.storage.google_drive.errors.object_not_found",
                precondition_verdict=_drive_external_verdict(
                    DriveStoragePreconditionCondition.OBJECT_PRESENT,
                    facts={"operation": "get", "object_present": False},
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )

        request = service.files().get_media(fileId=entry["id"])
        translated_error: OutboundStorageError | None = None
        payload: Any = None
        try:
            payload = request.execute()
        except OutboundStorageError:
            raise
        except Exception as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            _LOG.debug(
                "Google Drive media request failed with status=%s error_type=%s",
                str(status) if status is not None else "unknown",
                type(exc).__name__,
            )
            translated_error = _translate_http_error(exc, action="files.get_media")
        if translated_error is not None:
            raise translated_error
        if not isinstance(payload, (bytes, bytearray)):
            raise OutboundStorageNetworkError(
                "drive files.get_media returned non-bytes payload",
                context={"payload_type": type(payload).__name__},
                translated_message="adapters.outbound.storage.google_drive.errors.media_non_bytes",
                precondition_verdict=_drive_external_verdict(
                    DriveStoragePreconditionCondition.MEDIA_PAYLOAD_BYTES,
                    facts={
                        "operation": "files.get_media",
                        "payload_bytes": False,
                        "payload_type": type(payload).__name__,
                    },
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )

        stored_hash = _drive_storage_content_hash(entry)
        require_full_sha256_content_hash(
            stored_hash,
            message="drive object metadata does not carry a full SHA-256 content hash",
            context={"provider_object_id": str(entry.get("id", ""))},
            translated_message="adapters.outbound.storage.google_drive.errors.content_hash_mismatch",
        )
        metadata = _metadata_from_drive_entry(
            entry,
            namespace=namespace_clean,
            object_key_hmac=hmac_clean,
        )
        payload_bytes = bytes(payload)
        verify_payload_byte_length(
            payload_bytes,
            metadata.byte_length,
            message="drive byte_length mismatch",
            context={"provider_object_id": metadata.provider_object_id},
            translated_message="adapters.outbound.storage.google_drive.errors.content_hash_mismatch",
        )
        actual = sha256_hex(payload_bytes)
        verify_content_hash(
            actual,
            stored_hash,
            message="drive content_hash mismatch",
            context={"stored_hash": stored_hash, "actual_sha256": actual},
            translated_message="adapters.outbound.storage.google_drive.errors.content_hash_mismatch",
            require_full_digest=True,
        )
        return payload_bytes, metadata

    def delete(self, namespace: str, object_key_hmac: str) -> bool:
        """Permanently delete the Drive file for ``object_key_hmac``.

        Returns ``False`` immediately (without error) when the namespace
        folder or the object file does not exist; deleting a non-existent
        object is idempotent at the provider boundary.

        Args:
            namespace: Logical bucket name.
            object_key_hmac: Full HMAC string identifying the object.

        Returns:
            ``True`` when the file was found and deleted; ``False`` when the
            namespace or object was already absent.

        Raises:
            :class:`OutboundStorageValidationError`: When ``namespace`` or
                ``object_key_hmac`` are blank.
            :class:`OutboundStoragePermissionError`: On HTTP 401 or 403 from
                Drive.
            :class:`OutboundStorageNetworkError`: On any other Drive API
                failure.
        """
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
        """Yield the name of every namespace folder directly under ``cadrumo-vault/``.

        Paginates through Drive's ``files().list`` using ``nextPageToken``.
        The namespace folder IDs are cached as a side effect so subsequent
        ``_resolve_namespace_folder`` calls for yielded names skip the Drive
        lookup.

        Yields:
            Namespace name strings in Drive-returned order.

        Raises:
            :class:`OutboundStoragePermissionError`: On HTTP 401 or 403 from
                Drive.
            :class:`OutboundStorageNetworkError`: On any other Drive API
                failure.
        """
        service = self._get_service()
        vault_id = self._resolve_vault_folder()
        query = f"'{vault_id}' in parents and mimeType='{_FOLDER_MIME}' and trashed=false"
        page_token: str | None = None
        seen_tokens: set[str] = set()
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
            page_token = next_drive_page_token(
                response.get("nextPageToken") if isinstance(response, dict) else None,
                seen_tokens=seen_tokens,
                action="iter_namespaces",
            )
            if not page_token:
                return

    def iter_objects(self, namespace: str) -> Iterator[ProviderObjectMetadata]:
        """Yield metadata for every object in ``namespace``.

        Only files whose names end with ``.bin`` and contain ``--`` are
        yielded; Drive folders and unrelated files inside the namespace
        folder are silently skipped. Each yielded object must carry the
        provider-owned full HMAC in its ``appProperties`` metadata; the
        filename prefix is presentation only and never an identity fallback.

        Args:
            namespace: Logical bucket name.

        Yields:
            :class:`ProviderObjectMetadata` records in Drive-returned order.

        Raises:
            :class:`OutboundStorageNotFoundError`: When the namespace folder is
                absent from Drive.
            :class:`OutboundStorageValidationError`: When ``namespace`` is
                blank.
            :class:`OutboundStoragePermissionError`: On HTTP 401 or 403 from
                Drive.
            :class:`OutboundStorageNetworkError`: On any other Drive API
                failure.
        """
        namespace_clean = _validate_namespace(namespace)
        service = self._get_service()
        namespace_folder_id = self._resolve_namespace_folder(namespace_clean, create=False)
        if namespace_folder_id is None:
            raise OutboundStorageNotFoundError(
                "namespace is not present in Drive",
                context={"namespace": namespace_clean},
                translated_message="adapters.outbound.storage.google_drive.errors.namespace_not_found",
                precondition_verdict=_drive_external_verdict(
                    DriveStoragePreconditionCondition.NAMESPACE_PRESENT,
                    facts={"operation": "iter_objects", "namespace_present": False},
                    outcome=NoRecoveryOutcome.OPERATOR_DECISION,
                ),
            )
        query = f"'{namespace_folder_id}' in parents and trashed=false"
        page_token: str | None = None
        seen_tokens: set[str] = set()
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
                app_properties = _drive_storage_app_properties(entry)
                yield _metadata_from_drive_entry(
                    entry,
                    namespace=namespace_clean,
                    object_key_hmac=app_properties.object_key_hmac,
                )
            page_token = next_drive_page_token(
                response.get("nextPageToken") if isinstance(response, dict) else None,
                seen_tokens=seen_tokens,
                action="iter_objects",
            )
            if not page_token:
                return

    def probe(self, *, read_only: bool = False) -> ProviderProbeReport:
        """Assess Drive connectivity and write access, returning a :class:`ProviderProbeReport`.

        Checks, in order:

        1. Service construction — verifies ``google-api-python-client``
           can be imported and credentials can build a Drive resource.
        2. Root folder existence — confirms ``root_folder_id`` names a
           non-trashed Drive folder.
        3. Sentinel round-trip (skipped when ``read_only=True``) — calls
           ``put`` then ``delete`` against a ``_probe`` namespace to confirm
           write access end-to-end.

        The method never raises; every failure mode is encoded in the returned
        :class:`ProviderProbeReport`.

        Args:
            read_only: When ``True``, skip the sentinel write round-trip and
                report ``writable=False`` regardless of actual permissions.

        Returns:
            A :class:`ProviderProbeReport` with ``reachable``, ``writable``,
            ``root_folder_present``, and a human-readable ``detail`` string.
        """
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


# ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY:
# googleapiclient.discovery.build() returns an untyped Resource object; no stub
# narrows the concrete type.
def _build_media_body(payload: bytes) -> Any:  # ANY-RETURN-RATIONALE-GOOGLE-DRIVE-BUILD-FACTORY
    """Build a ``MediaIoBaseUpload`` from ``payload``. Lazy-imported."""
    try:
        from googleapiclient.http import MediaIoBaseUpload
    except ImportError as exc:
        raise OutboundStorageNetworkError(
            "googleapiclient.http is not importable",
            context={"dependency": "google-api-python-client"},
            translated_message="adapters.outbound.storage.google_drive.errors.googleapiclient_import_failed",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.API_CLIENT_AVAILABLE,
                facts={"component": "media_upload", "client_available": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc
    return MediaIoBaseUpload(io.BytesIO(payload), mimetype=_BINARY_MIME_TYPE, resumable=False)


# ADAPTER-INTERNAL-ALIAS-RATIONALE-DRIVE-ENTRY: raw Google Drive API file
# resource (untyped googleapiclient dict); narrowed via explicit key access.
def _parse_drive_size(value: object, *, provider_object_id: str) -> int:
    """Return the byte length Drive reported, or refuse the response.

    The coercion here used to catch every ``TypeError``/``ValueError`` and
    substitute ``0``, so a malformed remote ``size`` asserted a zero-byte
    contract that nothing downstream re-tested. ``get`` compares the
    DOWNLOADED payload's length against this value, so the two agreed
    trivially for an empty object and the malformed response passed clean;
    ``iter_objects`` downloads nothing at all and so had no second opinion to
    offer. An operator reading either surface saw a confident ``0``.

    Drive sends ``size`` as a decimal string for binary content, which is the
    only shape this adapter's own objects take: every object it writes is an
    uploaded blob, never a native Google document (the file kind whose size
    Drive genuinely omits). A value that is absent, non-numeric, or negative
    is therefore a broken response rather than a variation to absorb.

    Raises:
        :class:`adapters.outbound.storage.OutboundStorageIntegrityError`: When
            the field is absent, is not an integer or a decimal string, or is
            negative.
    """
    if isinstance(value, bool) or not isinstance(value, (int, str)):
        raise OutboundStorageIntegrityError(
            "drive object metadata carries no usable size",
            context={"provider_object_id": provider_object_id, "actual_value": repr(value)},
            translated_message="adapters.outbound.storage.google_drive.errors.size_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
                facts={"field": "size", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    try:
        byte_length = int(value)
    except ValueError:
        raise OutboundStorageIntegrityError(
            "drive object size is not an integer",
            context={"provider_object_id": provider_object_id, "actual_value": str(value)},
            translated_message="adapters.outbound.storage.google_drive.errors.size_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
                facts={"field": "size", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    if byte_length < 0:
        raise OutboundStorageIntegrityError(
            "drive object size is negative",
            context={"provider_object_id": provider_object_id, "actual_value": str(value)},
            translated_message="adapters.outbound.storage.google_drive.errors.size_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_SIZE_VALID,
                facts={"field": "size", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return byte_length


def _parse_drive_modified_time(value: object, *, provider_object_id: str) -> datetime:
    """Return the write instant Drive reported, or refuse the response.

    A missing or unparseable ``modifiedTime`` used to fall back to ``now()``,
    so an upstream metadata corruption was reported as a freshly written
    object. ``get`` and ``iter_objects`` are two separate Drive calls made at
    two different instants, so the same object then exposed two different
    ``written_at`` values depending on which surface an operator read it
    through — the remote analogue of the local sidecar-timestamp failure, and
    just as invisible while the payload itself stayed intact.

    Drive is asked for ``modifiedTime`` on every read that builds metadata and
    always returns it as an RFC 3339 instant for a real file, so an absent or
    malformed one is not a variation this adapter should absorb: it is a
    response that does not meet the storage metadata contract, and the caller
    is better served by being told than by a plausible wrong answer. A
    tz-naive value is refused for the same reason rather than assumed UTC.

    Raises:
        :class:`adapters.outbound.storage.OutboundStorageIntegrityError`: When
            the field is absent, is not a string, does not parse, or carries
            no timezone.
    """
    if not isinstance(value, str) or not value.strip():
        raise OutboundStorageIntegrityError(
            "drive object metadata carries no modifiedTime",
            context={"provider_object_id": provider_object_id, "actual_value": repr(value)},
            translated_message="adapters.outbound.storage.google_drive.errors.modified_time_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
                facts={"field": "modifiedTime", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    try:
        written_at = parse_iso_datetime(value)
    except ValueError:
        raise OutboundStorageIntegrityError(
            "drive object modifiedTime is not an RFC 3339 instant",
            context={"provider_object_id": provider_object_id, "actual_value": value},
            translated_message="adapters.outbound.storage.google_drive.errors.modified_time_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
                facts={"field": "modifiedTime", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    try:
        validate_utc_aware(written_at)
    except CoreValidationError:
        raise OutboundStorageIntegrityError(
            "drive object modifiedTime carries no timezone",
            context={"provider_object_id": provider_object_id, "actual_value": value},
            translated_message="adapters.outbound.storage.google_drive.errors.modified_time_invalid",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_MODIFIED_TIME_VALID,
                facts={"field": "modifiedTime", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from None
    return written_at


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: dict[str, Any] is the
# irreducible Drive API boundary shape; google-api-python-client stubs
# surface entry metadata as Any, so narrowing breaks string-key lookups.
def _metadata_from_drive_entry(
    entry: dict[str, Any],
    *,
    namespace: str,
    object_key_hmac: str,
) -> ProviderObjectMetadata:
    """Convert a Drive ``files().get/list`` response into :class:`ProviderObjectMetadata`."""
    provider_object_id = str(entry.get("id", ""))
    byte_length = _parse_drive_size(entry.get("size"), provider_object_id=provider_object_id)
    written_at = _parse_drive_modified_time(entry.get("modifiedTime"), provider_object_id=provider_object_id)

    app_properties = entry.get("appProperties") or {}
    content_hash = str(app_properties.get("content_hash", "") or "")
    if not content_hash:
        md5 = entry.get("md5Checksum")
        content_hash = f"md5-{md5}" if md5 else "sha256-unverified"

    return ProviderObjectMetadata(
        namespace=namespace,
        object_key_hmac=object_key_hmac,
        provider_object_id=str(entry.get("id", "")),
        byte_length=byte_length,
        content_hash=content_hash,
        written_at=written_at,
    )


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: see
# _metadata_from_drive_entry above.
def _drive_storage_app_properties(entry: dict[str, Any]) -> DriveAppProperties:
    """Return the validated app-owned metadata for a Drive storage object."""
    from pydantic import ValidationError

    from ..google import DriveAppProperties

    try:
        return DriveAppProperties.model_validate(entry.get("appProperties"))
    except ValidationError as exc:
        raise OutboundStorageIntegrityError(
            "drive object appProperties do not match the storage metadata contract",
            context={"provider_object_id": str(entry.get("id", ""))},
            translated_message="adapters.outbound.storage.google_drive.errors.content_hash_mismatch",
            precondition_verdict=_drive_external_verdict(
                DriveStoragePreconditionCondition.METADATA_APP_PROPERTIES_VALID,
                facts={"field": "appProperties", "valid": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        ) from exc


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: see
# _metadata_from_drive_entry above.
def _drive_storage_content_hash(entry: dict[str, Any]) -> str:
    """Return the validated storage content hash for a Drive read."""
    return _drive_storage_app_properties(entry).content_hash


__all__ = ["GoogleDriveProvider"]
