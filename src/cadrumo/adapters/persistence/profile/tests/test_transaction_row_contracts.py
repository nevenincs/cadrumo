"""Refusal parity for the stored-transaction D6 timestamp requirement.

A stored row must carry its two lifecycle timestamps, because ``Transaction``
would otherwise default them. The repository once checked that with a separate
witness parse of the stored bytes ahead of the envelope decode; it now reads
the decoded record's set fields after the one decode. The former witness is
inlined below as the oracle, and each table drives the old composed read
(witness, then envelope) and the shipped one (envelope, then
:func:`require_persisted_transaction_timestamps`) over the same bytes, so a
row accepted by one and refused by the other fails here.

Duplicate keys: ``json.loads`` keeps the last occurrence of a repeated key, and
pydantic's JSON parser does the same, so both reads see the same members.

The one input class the parsers disagree on is JSON that pydantic's parser
rejects but ``json.loads`` accepts (a lone UTF-16 surrogate escape). The oracle
witness refuses it for its missing timestamps; the envelope decode refuses it as
invalid JSON, so both composed reads still refuse it.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel, Field, TypeAdapter, ValidationError

from .....core.time.utc import UtcInstant
from .....domain.calculations.registry.authority import bundled_indexed_authority
from .....domain.transactions.enums import BusinessClassification, TransactionDirection
from .....domain.transactions.errors import TransactionValidationError
from .....domain.transactions.models import Transaction
from .....domain.transactions.raw_transaction import RawProvenance, RawTransaction, SourceFormat
from ...storage.envelope.contract import Envelope
from ...storage.secure_object_namespaces import TRANSACTION_CATALOGUE_NAMESPACE
from ..transaction_row_contracts import require_persisted_transaction_timestamps

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_OBJECT = TypeAdapter(dict[str, object])
_VALID = '"2024-04-14T09:30:00Z"'


class _OracleTimestampWitness(BaseModel):
    created_at: UtcInstant = Field()
    modified_at: UtcInstant = Field()


@pytest.fixture
def _authority_operation() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _oracle_witness(payload: bytes) -> None:
    """The removed decode-then-validate witness, verbatim in behaviour."""
    try:
        decoded: object = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    try:
        envelope = _OBJECT.validate_python(decoded)
    except ValidationError:
        return
    transaction_payload = envelope.get("payload")
    if not isinstance(transaction_payload, dict):
        return
    _OracleTimestampWitness.model_validate(_OBJECT.validate_python(transaction_payload))


def _witness_outcome(witness: object, payload: bytes) -> str:
    assert callable(witness)
    try:
        witness(payload)
    except ValidationError:
        return "refuse"
    return "pass"


#: A payload without ``raw`` fails the transaction id's default factory with the
#: domain error itself rather than a ``ValidationError``; both are refusals.
_ROW_REFUSALS = (ValidationError, TransactionValidationError)


def _old_read(payload: bytes) -> str:
    """The removed composition: the witness parse, then the envelope decode."""
    try:
        _oracle_witness(payload)
        Envelope[Transaction].model_validate_json(payload)
    except _ROW_REFUSALS:
        return "refuse"
    return "accept"


def _shipped_read(payload: bytes) -> str:
    """The repository's composition: one envelope decode, then the set-field requirement."""
    try:
        envelope = Envelope[Transaction].model_validate_json(payload)
        require_persisted_transaction_timestamps(envelope.payload)
    except _ROW_REFUSALS:
        return "refuse"
    return "accept"


def _envelope(created: str | None, modified: str | None = _VALID) -> bytes:
    members = [
        f'"{name}":{value}' for name, value in (("created_at", created), ("modified_at", modified)) if value is not None
    ]
    return ('{"schema_version":2,"payload":{"group_label":null,' + ",".join(members) + "}}").encode()


_WITNESS_CASES: tuple[tuple[str, bytes, str], ...] = (
    ("utc Z suffix", _envelope(_VALID), "pass"),
    ("utc +00:00 offset", _envelope('"2024-04-14T09:30:00+00:00"'), "pass"),
    ("utc -00:00 offset", _envelope('"2024-04-14T09:30:00-00:00"'), "pass"),
    ("space separator", _envelope('"2024-04-14 09:30:00Z"'), "pass"),
    ("nanosecond fraction", _envelope('"2024-04-14T09:30:00.123456789Z"'), "pass"),
    ("unix seconds number", _envelope("1713087000"), "pass"),
    ("unix seconds string", _envelope('"1713087000"'), "pass"),
    ("created_at missing", _envelope(None), "refuse"),
    ("modified_at missing", _envelope(_VALID, None), "refuse"),
    ("non-utc offset", _envelope('"2024-04-14T09:30:00+01:00"'), "refuse"),
    ("non-utc modified_at", _envelope(_VALID, '"2024-04-14T09:30:00-05:00"'), "refuse"),
    ("naive timestamp", _envelope('"2024-04-14T09:30:00"'), "refuse"),
    ("date only", _envelope('"2024-04-14"'), "refuse"),
    ("basic iso format", _envelope('"20240414T093000Z"'), "refuse"),
    ("free text", _envelope('"yesterday"'), "refuse"),
    ("null", _envelope("null"), "refuse"),
    ("boolean", _envelope("true"), "refuse"),
    ("array", _envelope("[]"), "refuse"),
    ("object", _envelope("{}"), "refuse"),
    (
        "duplicate created_at, invalid then valid",
        ('{"payload":{"created_at":"bad","created_at":' + _VALID + ',"modified_at":' + _VALID + "}}").encode(),
        "pass",
    ),
    (
        "duplicate created_at, valid then invalid",
        ('{"payload":{"created_at":' + _VALID + ',"created_at":"bad","modified_at":' + _VALID + "}}").encode(),
        "refuse",
    ),
    (
        "duplicate payload, empty then complete",
        ('{"payload":{},"payload":{"created_at":' + _VALID + ',"modified_at":' + _VALID + "}}").encode(),
        "pass",
    ),
    (
        "duplicate payload, complete then empty",
        ('{"payload":{"created_at":' + _VALID + ',"modified_at":' + _VALID + '},"payload":{}}').encode(),
        "refuse",
    ),
    ("NaN elsewhere, timestamps missing", b'{"rate":NaN,"payload":{}}', "refuse"),
    (
        "NaN elsewhere, timestamps present",
        ('{"rate":NaN,"payload":{"created_at":' + _VALID + ',"modified_at":' + _VALID + "}}").encode(),
        "pass",
    ),
    ("not json", b"\x00\x01not json", "pass"),
    ("invalid utf-8", b'{"payload":{"created_at":"\xff"}}', "pass"),
    ("array envelope", b"[1,2]", "pass"),
    ("string payload", b'{"payload":"x"}', "pass"),
    ("payload absent", b'{"schema_version":2}', "pass"),
)


@pytest.mark.parametrize(
    ("payload", "expected"), [case[1:] for case in _WITNESS_CASES], ids=[case[0] for case in _WITNESS_CASES]
)
@pytest.mark.usefixtures("_authority_operation")
def test_partial_rows_read_identically_through_the_old_and_shipped_composition(payload: bytes, expected: str) -> None:
    """The oracle witness still judges each row as recorded, and both reads agree on every one."""
    assert _witness_outcome(_oracle_witness, payload) == expected
    assert _shipped_read(payload) == _old_read(payload)


@pytest.mark.parametrize(
    "payload",
    [b"\x00\x01not json", b'{"payload":{"created_at":"\xff"}}', b"[1,2]", b'{"payload":"x"}', b'{"schema_version":2}'],
    ids=["not json", "invalid utf-8", "array envelope", "string payload", "payload absent"],
)
def test_malformed_rows_are_refused_by_the_envelope_decode(payload: bytes) -> None:
    """A row the old witness could not read was left for the envelope refusal, which still fires."""
    assert _witness_outcome(_oracle_witness, payload) == "pass"
    assert _shipped_read(payload) == "refuse"
    with pytest.raises(ValidationError) as refusal:
        Envelope[Transaction].model_validate_json(payload)
    assert refusal.value.title == "Envelope[Transaction]"


def test_lone_surrogate_row_is_still_refused_by_the_composed_read() -> None:
    """The only parser disagreement still ends in a refusal.

    ``json.loads`` accepts a lone surrogate escape, so the oracle reached the
    witness and refused the missing timestamps. Pydantic's parser rejects the
    bytes, so the shipped witness passes them on and the envelope, parsing with
    the same parser, refuses the row.
    """
    payload = b'{"payload":{"\\ud800":1}}'
    assert _witness_outcome(_oracle_witness, payload) == "refuse"
    assert _shipped_read(payload) == "refuse"
    with pytest.raises(ValidationError) as refusal:
        Envelope[Transaction].model_validate_json(payload)
    assert any(error["type"] == "json_invalid" for error in refusal.value.errors())


def _stored_row() -> dict[str, object]:
    raw = RawTransaction(
        provider_transaction_id="witness-row",
        booked_date=date(2024, 4, 10),
        value_date=date(2024, 4, 10),
        amount=Decimal("77.00"),
        currency="EUR",
        counterparty="Witness Supplier SL",
        description="witness parity row",
        provenance=RawProvenance(
            source_path=Path(__file__),
            source_sha256="c" * 64,
            source_row_index=3,
            source_format=SourceFormat.CSV,
            ingested_at=datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            provider_name="witness provider",
        ),
        raw_fields={"Concepto": "witness"},
    )
    transaction = Transaction.model_validate(
        {
            "raw": raw,
            "direction": TransactionDirection.OUTGOING,
            "group_label": None,
            "business_classification": BusinessClassification.BUSINESS,
            "source_jurisdiction": "ES",
            "created_at": datetime(2024, 4, 14, 9, 30, tzinfo=UTC),
            "modified_at": datetime(2024, 6, 1, 16, 45, tzinfo=UTC),
        },
    )
    envelope = Envelope[Transaction](
        schema_version=TRANSACTION_CATALOGUE_NAMESPACE.schema_version,
        written_at=transaction.modified_at,
        classification=TRANSACTION_CATALOGUE_NAMESPACE.sensitivity,
        payload=transaction,
    )
    return _OBJECT.validate_python(json.loads(envelope.model_dump_json()))


def _composed_read(witness: object, payload: bytes) -> str:
    """Run a witness then the envelope, as the repository's row decode does."""
    assert callable(witness)
    try:
        witness(payload)
        Envelope[Transaction].model_validate_json(payload)
    except ValidationError:
        return "refuse"
    return "accept"


_REMOVED = object()

_ROW_TIMESTAMP_CASES: tuple[tuple[str, dict[str, object], str], ...] = (
    ("stored as written", {}, "accept"),
    ("created_at missing", {"created_at": _REMOVED}, "refuse"),
    ("modified_at missing", {"modified_at": _REMOVED}, "refuse"),
    ("non-utc offset", {"created_at": "2024-04-14T10:30:00+01:00"}, "refuse"),
    ("naive timestamp", {"modified_at": "2024-06-01T16:45:00"}, "refuse"),
    ("number", {"created_at": 1713087000}, "refuse"),
    ("explicit null", {"modified_at": None}, "refuse"),
)


@pytest.mark.usefixtures("_authority_operation")
@pytest.mark.parametrize(
    ("changes", "expected"),
    [case[1:] for case in _ROW_TIMESTAMP_CASES],
    ids=[case[0] for case in _ROW_TIMESTAMP_CASES],
)
def test_real_stored_row_reads_identically_through_the_old_and_shipped_composition(
    changes: dict[str, object],
    expected: str,
) -> None:
    """A complete stored row is accepted or refused identically by both decodes."""
    row = _stored_row()
    transaction_payload = _OBJECT.validate_python(row["payload"])
    for name, value in changes.items():
        if value is _REMOVED:
            del transaction_payload[name]
        else:
            transaction_payload[name] = value
    row["payload"] = transaction_payload
    payload = json.dumps(row).encode()

    assert _composed_read(_oracle_witness, payload) == expected
    assert _shipped_read(payload) == expected
