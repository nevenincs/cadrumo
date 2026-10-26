"""Remove legacy manual edit operands before any operation journal hydration.

This changes custody only. Superseded snapshot versions remain superseded;
no old invocation is adopted as a current request or resumed from its values.
"""

from __future__ import annotations

import json

from pydantic import JsonValue, TypeAdapter, ValidationError

from ....application.operations.models import OperationTerminalReceipt
from ....application.operations.persistence.events import (
    OperationDiagnosticEvent,
    OperationEffectEvent,
    OperationInteractionEvent,
    OperationLogRecord,
    OperationNoticeEvent,
    OperationPhaseEvent,
    OperationProgressEvent,
    OperationReconciliationEvent,
    OperationTerminalEvent,
)
from ....application.operations.persistence.journal import OperationPersistedSnapshot
from ....core.hashing import reject_duplicate_json_members, reject_json_constant, sha256_hex
from ..storage.errors import RepositoryError
from ._journal_validation import OperationJournalRecord

_JSON_OBJECT = TypeAdapter(dict[str, JsonValue])
_PURGED_REQUEST = '{"manual_edit_values_purged":true}'
_PURGED_REFERENCE = sha256_hex(_PURGED_REQUEST.encode("utf-8"))
_FINANCIAL_DEFINITIONS = frozenset({"modelo.edit.apply", "modelo.edit.preflight"})
_EVENT_MODELS = {
    str(model.model_fields["kind"].default): model
    for model in (
        OperationPhaseEvent,
        OperationProgressEvent,
        OperationLogRecord,
        OperationEffectEvent,
        OperationNoticeEvent,
        OperationReconciliationEvent,
        OperationDiagnosticEvent,
        OperationInteractionEvent,
        OperationTerminalEvent,
    )
}


class FinancialEditJournalPurgeRefusedError(RepositoryError):
    """A legacy edit journal cannot be safely purged and must remain unavailable."""

    def __init__(self) -> None:
        """Carry a bounded refusal with no journal content or exception details."""
        super().__init__("financial edit journal purge refused")


def _decode_object(raw: str) -> dict[str, JsonValue]:
    decoded = json.loads(raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
    return _JSON_OBJECT.validate_python(decoded, strict=True)


def _object(value: JsonValue) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        raise FinancialEditJournalPurgeRefusedError
    return value


def _events(value: JsonValue) -> list[JsonValue]:
    if not isinstance(value, list):
        raise FinancialEditJournalPurgeRefusedError
    cleaned: list[JsonValue] = []
    for item in value:
        event = _object(item)
        kind = event.get("kind")
        if not isinstance(kind, str) or kind not in _EVENT_MODELS:
            raise FinancialEditJournalPurgeRefusedError
        model = _EVENT_MODELS[kind]
        event = {key: val for key, val in event.items() if key in model.model_fields}
        if "receipt" in event:
            receipt = _object(event["receipt"])
            event["receipt"] = {
                key: val for key, val in receipt.items() if key in OperationTerminalReceipt.model_fields
            }
        cleaned.append(event)
    return cleaned


def purge_legacy_financial_edit_journal(raw: str, *, operation_id: str) -> str | None:
    """Return safe replacement bytes, or None when no financial purge is needed.

    The filename is proved before replacement. A temporary current-schema
    validation checks the preserved lifecycle and history without changing the
    stored version, so an old version still fails normal hydration afterwards.
    No input value or content digest survives the replacement.
    """
    try:
        document = _decode_object(raw)
    except (ValidationError, ValueError):
        raise RepositoryError("invalid operation journal") from None
    candidate = document.get("snapshot")
    if not isinstance(candidate, dict):
        return None
    identity_candidate = candidate.get("identity")
    if not isinstance(identity_candidate, dict):
        return None
    definition_id = identity_candidate.get("definition_id")
    if not isinstance(definition_id, str) or definition_id not in _FINANCIAL_DEFINITIONS:
        return None
    try:
        snapshot = candidate
        identity = identity_candidate
        if identity.get("operation_id") != operation_id:
            raise FinancialEditJournalPurgeRefusedError
        inline = snapshot.get("credential_free_request_json")
        request = _decode_object(inline) if isinstance(inline, str) else None
        legacy = (request is not None and "submission" in request) or snapshot.get(
            "request_storage"
        ) == "secure_reference"
        if not legacy:
            return None
        snapshot = {key: val for key, val in snapshot.items() if key in OperationPersistedSnapshot.model_fields}
        snapshot["credential_free_request_json"] = _PURGED_REQUEST
        snapshot["request_storage"] = "credential_free_journal"
        snapshot["request_reference"] = _PURGED_REFERENCE
        snapshot["manual_edit_values_purged"] = True
        snapshot["idempotency_claim"] = None
        snapshot["admission_provenance_reference"] = None
        snapshot["events"] = _events(snapshot.get("events", []))
        if snapshot.get("terminal_receipt") is not None:
            receipt = _object(snapshot["terminal_receipt"])
            snapshot["terminal_receipt"] = {
                key: val for key, val in receipt.items() if key in OperationTerminalReceipt.model_fields
            }
        document = {"snapshot": snapshot, "history": _events(document["history"])}
        validation_snapshot = dict(snapshot)
        validation_snapshot["schema_version"] = OperationPersistedSnapshot.model_fields["schema_version"].default
        OperationJournalRecord.model_validate_json(json.dumps({**document, "snapshot": validation_snapshot}))
        return json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    except (ValidationError, KeyError, TypeError, ValueError):
        raise FinancialEditJournalPurgeRefusedError from None
