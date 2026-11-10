"""The write that stops storing a personal row's old business figures records what they were.

A personal row stored before such rows were refused business figures is read
without them, so the next write of that row persists their absence. These
tests store such a row in the real encrypted catalogue, edit an unrelated field
through the ledger update service, and read back the stored row, the catalogue
revision and the bucket event history: the figures are gone from the row, and
the edit's event names each dropped figure with its prior value.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import TypeAdapter

from .....application.ledger.manual_update import update_manual_transaction_fields
from .....application.ledger.models import ManualLedgerTransactionPatch
from .....domain.buckets.event import BucketEvent, BucketEventType
from .....domain.transactions.classification_effects import fields_refused_by_classification
from .....domain.transactions.enums import BusinessClassification
from .....domain.transactions.repository import transaction_object_key
from ...storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from ...storage.sql.secure_object_records import SecureObjectRecord
from .classification_origin_support import BUCKET_ID, PERSON, Ledger, add_row, composed_ledger

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter, pytest.mark.usefixtures("operation")]
_JSON_OBJECT = TypeAdapter(dict[str, object])

_PERSONAL = BusinessClassification.PERSONAL


@pytest.fixture
def ledger(tmp_path: Path) -> Iterator[Ledger]:
    with composed_ledger(tmp_path) as composed:
        yield composed


def _stored_envelope(ledger: Ledger, transaction_id: str) -> tuple[dict[str, object], SecureObjectRecord]:
    record = ledger.objects.load(
        TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        transaction_object_key(BUCKET_ID, transaction_id),
        expected_class=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        max_supported_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
    )
    assert record is not None
    envelope = _JSON_OBJECT.validate_json(record.payload)
    return envelope, record


def _stored_row(ledger: Ledger, transaction_id: str) -> dict[str, object]:
    return _JSON_OBJECT.validate_python(_stored_envelope(ledger, transaction_id)[0]["payload"])


def _store_legacy_personal_row(ledger: Ledger) -> str:
    """Write a business row with figures, then re-encrypt it as personal, as rows stored before the refusal were."""
    transaction_id = add_row(ledger, description="Office chair", classification=BusinessClassification.BUSINESS)
    update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate(
            {
                "category_id": "material_oficina",
                "taxable_base": Decimal("100.00"),
                "irpf_category": "actividad_economica",
            }
        ),
        actor=PERSON,
        source_command="aeat app ledger update",
        ports=ledger.ports,
    )
    envelope, record = _stored_envelope(ledger, transaction_id)
    row = _JSON_OBJECT.validate_python(envelope["payload"])
    envelope["payload"] = {**row, "business_classification": _PERSONAL.value}
    ledger.objects.save(
        namespace=TRANSACTION_CATALOGUE_NAMESPACE.namespace,
        object_key=transaction_object_key(BUCKET_ID, transaction_id),
        classification=record.classification,
        schema_version=record.schema_version,
        written_at=record.written_at,
        payload=json.dumps(envelope).encode("utf-8"),
    )
    return transaction_id


def _events_for(ledger: Ledger, transaction_id: str) -> list[BucketEvent]:
    return [event for event in ledger.events.load().events.values() if event.object_id == transaction_id]


def test_editing_an_unrelated_field_drops_the_figures_and_records_their_prior_values(ledger: Ledger) -> None:
    transaction_id = _store_legacy_personal_row(ledger)
    legacy = _stored_row(ledger, transaction_id)
    assert legacy["category_id"] == "material_oficina"
    assert legacy["taxable_base"] is not None
    _, revision_before = ledger.transactions.load_revisioned()
    events_before = {event.event_id for event in _events_for(ledger, transaction_id)}

    result = update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate({"notes": "kept for the household"}),
        actor=PERSON,
        source_command="aeat app ledger update",
        ports=ledger.ports,
    )

    stored = _stored_row(ledger, transaction_id)
    assert stored["business_classification"] == _PERSONAL.value
    assert stored["notes"] == "kept for the household"
    assert all(stored[name] is None for name in fields_refused_by_classification(_PERSONAL))
    _, revision_after = ledger.transactions.load_revisioned()
    assert revision_after != revision_before

    new_events = [event for event in _events_for(ledger, transaction_id) if event.event_id not in events_before]
    assert {event.event_id for event in new_events} == set(result.bucket_event_ids)
    traced = [event for event in new_events if "withheld_figure_count" in event.payload]
    assert len(traced) == 1
    trace = traced[0]
    assert trace.event_type is BucketEventType.LEDGER_TRANSACTION_UPDATED
    assert trace.payload["withheld_figure_count"] == "3"
    assert trace.payload["withheld_category_id"] == "material_oficina"
    assert Decimal(trace.payload["withheld_taxable_base"]) == Decimal("100.00")
    assert trace.payload["withheld_irpf_category"] == "actividad_economica"
    assert ledger.row(result.ref.transaction_id).edit_lineage[-1].bucket_event_id == trace.event_id


def test_a_later_write_of_a_row_without_withheld_figures_records_none(ledger: Ledger) -> None:
    transaction_id = _store_legacy_personal_row(ledger)
    first = update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate({"notes": "first"}),
        actor=PERSON,
        source_command="aeat app ledger update",
        ports=ledger.ports,
    )

    second = update_manual_transaction_fields(
        bucket_id=BUCKET_ID,
        transaction_id=first.ref.transaction_id,
        patch=ManualLedgerTransactionPatch.model_validate({"notes": "second"}),
        actor=PERSON,
        source_command="aeat app ledger update",
        ports=ledger.ports,
    )

    events = ledger.events.load().events
    assert all("withheld_figure_count" not in events[event_id].payload for event_id in second.bucket_event_ids)
