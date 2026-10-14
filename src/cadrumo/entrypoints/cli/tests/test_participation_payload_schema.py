"""The tax CLI participation payload schemas preserve their published fields."""

import pytest

from .._ledger_payloads import LedgerTrackResult, LedgerTransactionParticipationPayload

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_ledger_track_result_schema_carries_participated_in() -> None:
    assert "participated_in" in LedgerTrackResult.model_fields
    # The field is optional (omitted for transactions with no finalized participations).
    assert LedgerTrackResult.model_fields["participated_in"].is_required() is False


def test_participation_payload_schema_shape() -> None:
    fields = LedgerTransactionParticipationPayload.model_fields
    assert "transaction_id" in fields
    assert "participations" in fields
