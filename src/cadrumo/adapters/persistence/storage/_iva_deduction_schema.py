"""v1-to-v2 secure-payload cutover for IVA deduction authority."""

from __future__ import annotations

import json
from collections.abc import MutableMapping

from pydantic import TypeAdapter, ValidationError

from ....core.external_constants import UTF_8_ENCODING
from .errors import StorageValidationError

_JSON_OBJECT = TypeAdapter(dict[str, object])
_JSON_ARRAY = TypeAdapter(list[object])


def _json_object(payload: bytes, *, surface: str) -> dict[str, object]:
    try:
        decoded: object = json.loads(payload.decode(UTF_8_ENCODING))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise StorageValidationError(f"{surface} v1 payload is not a JSON object") from exc
    try:
        return _JSON_OBJECT.validate_python(decoded)
    except ValidationError as exc:
        raise StorageValidationError(f"{surface} v1 payload is not a JSON object") from exc


def _object_value(value: object, *, surface: str) -> dict[str, object]:
    """Validate one nested JSON object without leaking unknown mapping types."""
    try:
        return _JSON_OBJECT.validate_python(value)
    except ValidationError as exc:
        raise StorageValidationError(f"{surface} is not a JSON object") from exc


def _encode(payload: MutableMapping[str, object]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(UTF_8_ENCODING)


def upgrade_transaction_catalogue_v1_payload(payload: bytes) -> bytes:
    """Upgrade only rows whose persisted evidence already proves v2 facts.

    The membership index has no IVA classification and is safely re-stamped.
    A transaction carrying any IVA substrate but lacking exact classification
    provenance refuses before the secure-object row becomes v2.
    """
    envelope = _json_object(payload, surface="transaction catalogue")
    inner = _object_value(
        envelope.get("payload"),
        surface="transaction catalogue v1 transaction envelope payload",
    )
    if "transaction_ids" in inner:
        envelope["schema_version"] = 2
        return _encode(envelope)
    iva_fields = ("taxable_base", "iva_rate", "iva_amount", "iva_category")
    carries_iva = any(inner.get(name) is not None for name in iva_fields)
    authority_fields = (
        "deduction_fact_kind",
        "deduction_provenance",
        "investment_asset_id",
        "rectifies_ledger_id",
        "prorrata_sector_id",
    )
    if carries_iva and (inner.get("deduction_fact_kind") is None or inner.get("deduction_provenance") is None):
        transaction_id = inner.get("transaction_id", "unknown")
        raise StorageValidationError(
            "transaction catalogue v1 backfill refused; re-import or remediate "
            f"transaction {transaction_id!r}: exact deduction_fact_kind and deduction_provenance are absent",
        )
    absent_fields = [field for field in authority_fields if field not in inner]
    if absent_fields:
        transaction_id = inner.get("transaction_id", "unknown")
        raise StorageValidationError(
            "transaction catalogue v1 cutover refused; authoritative fields are absent for "
            f"transaction {transaction_id!r}: {', '.join(absent_fields)}"
        )
    envelope["schema_version"] = 2
    return _encode(envelope)


def upgrade_bienes_inversion_v1_payload(payload: bytes) -> bytes:
    """Upgrade an empty or already-authoritative register, refusing unlinked assets."""
    document = _json_object(payload, surface="bienes-inversion register")
    records = document.get("records")
    try:
        raw_records = _JSON_ARRAY.validate_python(records)
    except ValidationError:
        raise StorageValidationError("bienes-inversion register v1 payload has no records list") from None
    remediation: list[str] = []
    upgraded_records: list[dict[str, object]] = []
    for raw_record in raw_records:
        try:
            record = _JSON_OBJECT.validate_python(raw_record)
        except ValidationError:
            remediation.append("<malformed-record>")
            continue
        identifier_value = record.get("identifier", "<unknown>")
        identifier = identifier_value if isinstance(identifier_value, str) else "<unknown>"
        if not record.get("acquisition_ledger_id"):
            remediation.append(f"{identifier}: missing acquisition_ledger_id")
            continue
        if "prorrata_sector_id" not in record:
            remediation.append(f"{identifier}: missing explicit prorrata_sector_id")
            continue
        record["schema_version"] = "2"
        upgraded_records.append(record)
    if remediation:
        raise StorageValidationError(
            "bienes-inversion v1 backfill refused; re-import or remediate: " + "; ".join(remediation),
        )
    document["records"] = upgraded_records
    document["schema_version"] = "2"
    return _encode(document)


__all__ = ["upgrade_bienes_inversion_v1_payload", "upgrade_transaction_catalogue_v1_payload"]
