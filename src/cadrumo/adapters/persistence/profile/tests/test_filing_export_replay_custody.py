"""Encrypted custody invariants for filing-export replay receipts.

The coordinate below is deliberately outside the filing registry.  These tests
exercise only the opaque custody record and cannot be mistaken for enrollment
or acceptance evidence for a real modelo revision.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID

import pytest
from sqlalchemy import select

from .....application.filing import (
    FilingExportOfficialProbe,
    FilingExportProofCoordinate,
    FilingExportSecureCustodyRecord,
    FilingExportSourcePinnedProbeExpectation,
)
from .....tests.secure_sql import (
    isolated_runtime_profile,
    mutate_encrypted_secure_object_json,
    read_db_at_rest_bytes,
)
from ...storage import FILING_EXPORT_REPLAY_PROOFS_NAMESPACE, SecureObjectRowIdentityError
from ...storage.sql import SecureObjectRow
from ..filing_export_replay import FilingExportReplayCustodyRepository, _require_source_pinned_probe_bytes

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]

_OPAQUE_COORDINATE = FilingExportProofCoordinate(
    modelo="000",
    revision="custody-boundary",
    layout_ids=("custody-layout",),
)
_ATTESTED_AT = datetime(2026, 8, 25, 10, 0, tzinfo=UTC)
_VALID_UNTIL = _ATTESTED_AT + timedelta(hours=1)
_RECEIPT_A = UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
_RECEIPT_B = UUID("bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb")
_DRAFT_CANARY = "operator-source-owned-draft-canary"


def _record(receipt_id: UUID) -> FilingExportSecureCustodyRecord:
    return FilingExportSecureCustodyRecord(
        receipt_id=receipt_id,
        coordinate=_OPAQUE_COORDINATE,
        source_authority_id="operator.source-authority",
        custody_authority_id=FilingExportReplayCustodyRepository.authority_id,
        evidence_id="operator.evidence",
        calculation_revision_id="1" * 64,
        draft_id=_DRAFT_CANARY,
        payload_sha256="2" * 64,
        emitted_bytes=123,
        attested_at=_ATTESTED_AT,
        valid_until=_VALID_UNTIL,
        encrypted_at_rest=True,
        approved_calculation_revision=True,
        source_owned_draft=True,
        matching_producer_snapshot=True,
        value_arrival=True,
        applicability=True,
        repeated_record_order=True,
        emitted_extent=True,
        source_pinned_probes_passed=True,
    )


def _receipt_row_statement(receipt_id: UUID):
    return select(SecureObjectRow).where(
        SecureObjectRow.namespace == FILING_EXPORT_REPLAY_PROOFS_NAMESPACE.namespace,
        SecureObjectRow.object_key == str(receipt_id),
    )


def test_replay_custody_round_trips_only_through_encrypted_profile_storage(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = FilingExportReplayCustodyRepository(valid_for=timedelta(hours=1))
        record = _record(_RECEIPT_A)

        repository.save(record)

        assert repository.load(str(record.receipt_id)) == record
        database_path = Path(str(profile.repository._engine.url.database))
        at_rest = read_db_at_rest_bytes(database_path)
        assert _DRAFT_CANARY.encode() not in at_rest
        assert record.payload_sha256.encode() not in at_rest


def test_replay_custody_refuses_encrypted_receipt_identity_substitution(tmp_path: Path) -> None:
    with isolated_runtime_profile(tmp_path=tmp_path) as profile:
        repository = FilingExportReplayCustodyRepository(valid_for=timedelta(hours=1))
        repository.save(_record(_RECEIPT_A))

        def substitute_receipt_identity(document: dict[str, object]) -> None:
            payload = document["payload"]
            assert isinstance(payload, dict)
            payload["receipt_id"] = str(_RECEIPT_B)

        mutate_encrypted_secure_object_json(
            profile.repository._engine,
            row_statement=_receipt_row_statement(_RECEIPT_A),
            mutate=substitute_receipt_identity,
        )

        with pytest.raises(SecureObjectRowIdentityError):
            repository.load(str(_RECEIPT_A))


def test_replay_custody_refuses_same_length_wrong_probe_bytes() -> None:
    expectation = FilingExportSourcePinnedProbeExpectation(
        probe=FilingExportOfficialProbe(
            record_id="official-record",
            field_id="official-literal",
            emitted_offset=2,
            length=3,
        ),
        expected_bytes=b"ABC",
    )

    with pytest.raises(ValueError, match="disagrees with source-pinned expected bytes"):
        _require_source_pinned_probe_bytes(
            expectations=(expectation,),
            payload=b"00ABD99",
        )
