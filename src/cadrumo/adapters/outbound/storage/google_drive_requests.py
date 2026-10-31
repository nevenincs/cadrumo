"""Drive response matching and transport error translation."""

from __future__ import annotations

from http import HTTPStatus
from typing import Any

from ....core.google_http_error import google_http_status, google_quota_marker
from ....core.operator_action_enums import NoRecoveryOutcome
from ....core.type_guards import is_object_dict, is_object_list, is_object_mapping, is_str_keyed_dict
from ..google.drive_entries import OWNERSHIP_KEY, OWNERSHIP_VALUE
from ._google_drive_metadata import DriveStoragePreconditionCondition, drive_external_verdict
from .errors import (
    OutboundStorageConflictError,
    OutboundStorageError,
    OutboundStorageNetworkError,
    OutboundStorageNotFoundError,
    OutboundStoragePermissionError,
    OutboundStorageQuotaError,
    OutboundStorageUnavailableError,
)

_STATUS_CODE_END = 600
"""One past the last status code HTTP defines."""

_FILE_EXTENSION = ".bin"


def translate_http_error(error: Exception, *, action: str) -> OutboundStorageError:
    """Translate a Google API HttpError into a typed :class:`OutboundStorageError`.

    The lazy-import guard makes this callable without ``google-api-python-client``
    installed, which is important for unit tests that inject fakes.
    """
    status = google_http_status(error)
    detail = "drive request failed"
    context = {"action": action, "status": str(status) if status is not None else "unknown"}
    if status == HTTPStatus.TOO_MANY_REQUESTS or (
        status == HTTPStatus.FORBIDDEN and google_quota_marker(error) is not None
    ):
        return OutboundStorageQuotaError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_WITHIN_QUOTA,
                facts={"operation": action, "status": context["status"], "quota_available": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    if status in (401, 403):
        return OutboundStoragePermissionError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_AUTHORIZED,
                facts={"operation": action, "status": context["status"], "authorization_sufficient": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    if status == HTTPStatus.NOT_FOUND:
        return OutboundStorageNotFoundError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=drive_external_verdict(
                DriveStoragePreconditionCondition.TARGET_PRESENT,
                facts={"operation": action, "status": context["status"], "target_present": False},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        )
    if status == HTTPStatus.CONFLICT:
        return OutboundStorageConflictError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_CONFLICT_FREE,
                facts={"operation": action, "status": context["status"], "conflict_detected": True},
                outcome=NoRecoveryOutcome.OPERATOR_DECISION,
            ),
        )
    if status is not None and HTTPStatus.INTERNAL_SERVER_ERROR <= status < _STATUS_CODE_END:
        return OutboundStorageUnavailableError(
            detail,
            context=context,
            translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
            precondition_verdict=drive_external_verdict(
                DriveStoragePreconditionCondition.REQUEST_AVAILABLE,
                facts={"operation": action, "status": context["status"], "available": False},
                outcome=NoRecoveryOutcome.SAFETY,
            ),
        )
    return OutboundStorageNetworkError(
        detail,
        context=context,
        translated_message="adapters.outbound.storage.google_drive.errors.request_failed",
        precondition_verdict=drive_external_verdict(
            DriveStoragePreconditionCondition.REQUEST_TRANSPORT_AVAILABLE,
            facts={"operation": action, "status": context["status"], "transport_available": False},
            outcome=NoRecoveryOutcome.SAFETY,
        ),
    )


def listed_drive_files(response: object) -> list[dict[str, object]]:
    """Return the ``files`` rows of a Drive ``list`` response as string-keyed entries.

    The discovery client hands back an untyped JSON mapping. A row that is not
    a string-keyed object cannot carry the ``id``/``name``/``appProperties``
    fields every caller reads, so it is not a Drive file for our purposes.
    """
    if not is_object_dict(response):
        return []
    raw_files = response.get("files")
    if not is_object_list(raw_files):
        return []
    return [entry for entry in raw_files if is_str_keyed_dict(entry)]


def is_owned_drive_match(entry: dict[str, object], *, prefix: str, object_key_hmac: str) -> bool:
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
    if not is_object_mapping(app_properties):
        return False
    ownership = app_properties.get(OWNERSHIP_KEY)
    stored_hmac = app_properties.get("object_key_hmac")
    return (
        isinstance(ownership, str)
        and ownership == OWNERSHIP_VALUE
        and isinstance(stored_hmac, str)
        and stored_hmac == object_key_hmac
    )


def drive_list_kwargs(
    query: str,
    fields: str,
    page_size: int,
    page_token: str | None,
) -> dict[str, Any]:
    """Build one Drive listing request, adding pagination only when present."""
    kwargs: dict[str, Any] = {"q": query, "fields": fields, "pageSize": page_size}
    if page_token is not None:
        kwargs["pageToken"] = page_token
    return kwargs
