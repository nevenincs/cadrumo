"""Shared Drive owned-entry query, lookup, and identity validation.

Every adapter that resolves an app-owned Drive entry by name runs the same
policy: build a parent/name/MIME query literal, accept an entry carrying the
``appProperties.cadrumo_vault_app=cadrumo`` ownership marker, backfill that
marker onto an unmarked entry a previous run created, and refuse a
foreign-owned entry rather than adopt operator content.

That policy previously existed twice inside
:mod:`adapters.outbound.google._calc_sheets_apply` (once for folders, once
for spreadsheets), differing only in MIME type and in the action and error
text. Two copies of one ownership decision can drift independently, and a
drift here means adopting or overwriting Drive content the operator owns, so
the policy lives here once and is parameterised by the parts that genuinely
differ.

The module also owns two invariants the duplicated copies did not enforce:

- **Query-name escaping.** A Drive v3 query embeds the name as a
  single-quoted literal, so an apostrophe in the configured name closes the
  literal early and the server parses a different (or invalid) predicate.
  Escaping belongs to whoever builds the query, so it cannot be applied on
  one call path and forgotten on another.
- **Entry identity.** A Drive response is untyped JSON, so an owned entry
  with an absent or blank ``id`` is representable. Callers immediately index
  ``entry["id"]``, which surfaced as a raw :exc:`KeyError` from the provider
  instead of a typed storage failure. Validating identity before an entry is
  returned means no caller can index one that has none.

See Also:
    :func:`adapters.outbound.google._api.execute_request`
        Executor that maps Drive transport failures onto the typed
        :class:`adapters.outbound.storage.OutboundStorageError` hierarchy.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Final

from ....core import ActionEvidenceProvenance, NoRecoveryOutcome
from ..storage import OutboundStorageConflictError, OutboundStorageError, OutboundStorageValidationError
from ._api import execute_request
from ._preconditions import google_terminal_refusal

OWNERSHIP_KEY: Final[str] = "cadrumo_vault_app"
OWNERSHIP_VALUE: Final[str] = "cadrumo"


class DriveEntryPreconditionCondition(StrEnum):
    """Closed terminal conditions owned by the Drive entry adapter."""

    IDENTIFIER_VALID = "google.drive_entry.identifier_valid"
    LIST_RESPONSE_VALID = "google.drive_entry.list_response_valid"
    ENTRY_MAPPING_VALID = "google.drive_entry.entry_mapping_valid"
    OWNERSHIP_METADATA_VALID = "google.drive_entry.ownership_metadata_valid"
    OWNERSHIP_ALIGNED = "google.drive_entry.ownership_aligned"


def _drive_entry_terminal_refusal(
    error: OutboundStorageError,
    condition: DriveEntryPreconditionCondition,
    *,
    facts: Mapping[str, str | int | bool],
) -> OutboundStorageError:
    """Return ``error``'s operator-review equivalent without making up an action."""
    return google_terminal_refusal(
        error,
        condition_id=condition.value,
        facts=facts,
        provenance=ActionEvidenceProvenance.RUNTIME_OBSERVATION,
        outcome=NoRecoveryOutcome.OPERATOR_DECISION,
    )


def escape_drive_query_name(name: str) -> str:
    """Return ``name`` escaped for use inside a single-quoted Drive query literal.

    Drive v3 query literals escape a backslash and a single quote with a
    preceding backslash. The backslash is replaced first so an escape
    introduced for an apostrophe is not itself re-escaped.

    Args:
        name: Raw entry name, which may contain apostrophes or backslashes.

    Returns:
        The escaped name, safe to interpolate between single quotes.
    """
    return name.replace("\\", "\\\\").replace("'", "\\'")


def build_owned_entry_query(*, parent_id: str, name: str, mime_type: str) -> str:
    """Return the Drive query selecting a non-trashed child of ``parent_id``.

    Args:
        parent_id: Drive folder ID the entry must be parented by.
        name: Entry name, escaped through :func:`escape_drive_query_name`.
        mime_type: Drive MIME type constraining the entry kind.

    Returns:
        A Drive v3 ``q`` predicate string.
    """
    safe_name = escape_drive_query_name(name)
    return f"'{parent_id}' in parents and name = '{safe_name}' and mimeType = '{mime_type}' and trashed = false"


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: dict[str, Any] is the
# irreducible Drive API boundary shape; google-api-python-client stubs
# surface entry metadata as Any, so narrowing breaks string-key lookups.
def require_drive_entry_id(
    entry: dict[str, Any],
    *,
    name: str,
    parent_id: str,
) -> str:
    """Return the entry's non-empty Drive ID, or refuse with a typed error.

    Args:
        entry: Drive entry mapping as returned by ``files().list()``.
        name: Entry name, for the refusal context.
        parent_id: Parent folder ID, for the refusal context.

    Returns:
        The validated Drive object ID.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStorageValidationError`:
            When the entry carries no ``id``, a non-string ``id``, or a blank
            one. Without this the caller's ``entry["id"]`` raised a raw
            :exc:`KeyError` out of the provider boundary.
    """
    raw_id = entry.get("id")
    if not isinstance(raw_id, str) or not raw_id.strip():
        raise _drive_entry_terminal_refusal(
            OutboundStorageValidationError(
                f"Drive returned an app-owned entry named {name!r} without a usable id",
                context={"parent_id": parent_id, "name": name, "entry_id": repr(raw_id)},
            ),
            DriveEntryPreconditionCondition.IDENTIFIER_VALID,
            facts={
                "parent_id": parent_id,
                "entry_name": name,
                "identifier_present": isinstance(raw_id, str) and bool(raw_id.strip()),
                "identifier_type": type(raw_id).__name__,
            },
        )
    return raw_id


# ADAPTER-INTERNAL-ALIAS-RATIONALE-GOOGLE-RESOURCE: drive is a
# googleapiclient Resource; no stub type ships with google-api-python-client.
def find_owned_drive_entry(
    drive: Any,
    *,
    parent_id: str,
    name: str,
    mime_type: str,
    list_action: str,
    backfill_action: str,
    conflict_message: str,
) -> dict[str, Any] | None:
    """Return the app-owned Drive entry of ``name`` under ``parent_id``, if any.

    Applies the one ownership policy shared by every Drive lookup: an entry
    already carrying the ownership marker is adopted; an entry carrying no
    ``appProperties`` at all is a pre-marker artefact of this app and is
    backfilled then adopted; an entry carrying foreign properties is refused.
    Every returned entry has been checked to carry a usable ID.

    Args:
        drive: Drive v3 service resource.
        parent_id: Folder ID to search within.
        name: Entry name to match.
        mime_type: Drive MIME type constraining the entry kind.
        list_action: Action label for the list call's error context.
        backfill_action: Action label for the marker-backfill call.
        conflict_message: Message raised when a foreign-owned entry is found.

    Returns:
        The owned entry mapping, or ``None`` when no such entry exists.

    Raises:
        :exc:`~adapters.outbound.storage.OutboundStorageConflictError`: When a
            same-named entry exists but is not app-owned.
        :exc:`~adapters.outbound.storage.OutboundStorageValidationError`: When
            an owned entry carries no usable ID.
    """
    query = build_owned_entry_query(parent_id=parent_id, name=name, mime_type=mime_type)
    response = execute_request(
        drive.files().list(q=query, fields="files(id,name,appProperties)", pageSize=10),
        action=list_action,
    )
    entries = response.get("files", [])
    if not isinstance(entries, list):
        raise _drive_entry_terminal_refusal(
            OutboundStorageValidationError(
                "Drive owned-entry lookup returned a non-list files field",
                context={"parent_id": parent_id, "name": name},
            ),
            DriveEntryPreconditionCondition.LIST_RESPONSE_VALID,
            facts={"parent_id": parent_id, "entry_name": name, "entries_list_valid": False},
        )
    for entry_index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise _drive_entry_terminal_refusal(
                OutboundStorageValidationError(
                    "Drive owned-entry lookup returned a non-mapping entry",
                    context={"parent_id": parent_id, "name": name, "entry_index": entry_index},
                ),
                DriveEntryPreconditionCondition.ENTRY_MAPPING_VALID,
                facts={"parent_id": parent_id, "entry_name": name, "entry_index": entry_index, "entry_mapping": False},
            )
        raw_properties = entry.get("appProperties")
        if raw_properties is None:
            existing: Mapping[str, Any] = {}
        elif isinstance(raw_properties, Mapping):
            existing = raw_properties
        else:
            raise _drive_entry_terminal_refusal(
                OutboundStorageValidationError(
                    "Drive owned-entry lookup returned non-mapping ownership metadata",
                    context={"parent_id": parent_id, "name": name, "entry_index": entry_index},
                ),
                DriveEntryPreconditionCondition.OWNERSHIP_METADATA_VALID,
                facts={
                    "parent_id": parent_id,
                    "entry_name": name,
                    "entry_index": entry_index,
                    "ownership_metadata_mapping": False,
                },
            )
        if existing.get(OWNERSHIP_KEY) == OWNERSHIP_VALUE:
            require_drive_entry_id(entry, name=name, parent_id=parent_id)
            return entry
        if not existing:
            # Backfill the marker on an entry this app created on a previous
            # run that predated marker stamping. The ID is validated first so
            # the update call cannot be issued against a malformed entry.
            entry_id = require_drive_entry_id(entry, name=name, parent_id=parent_id)
            execute_request(
                drive.files().update(
                    fileId=entry_id,
                    body={"appProperties": {OWNERSHIP_KEY: OWNERSHIP_VALUE}},
                    fields="id,appProperties",
                ),
                action=backfill_action,
            )
            return entry
        raise _drive_entry_terminal_refusal(
            OutboundStorageConflictError(
                conflict_message,
                context={"parent_id": parent_id, "name": name},
            ),
            DriveEntryPreconditionCondition.OWNERSHIP_ALIGNED,
            facts={"parent_id": parent_id, "entry_name": name, "ownership_aligned": False},
        )
    return None


__all__ = [
    "OWNERSHIP_KEY",
    "OWNERSHIP_VALUE",
    "build_owned_entry_query",
    "escape_drive_query_name",
    "find_owned_drive_entry",
    "require_drive_entry_id",
]
