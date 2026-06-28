"""Tests for the :class:`RecoveryRecord` BIP-39 envelope."""

from __future__ import annotations

import base64
import json
import secrets
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from .._recovery_record import RecoveryRecord

pytestmark = [pytest.mark.unit, pytest.mark.hex_persistence_adapter]


def _b64(n: int) -> str:
    return base64.b64encode(secrets.token_bytes(n)).decode("ascii")


def _record(**overrides: object) -> RecoveryRecord:
    defaults: dict[str, Any] = {
        "wrapped_dek_b64": _b64(32),
        "nonce_b64": _b64(12),
        "tag_b64": _b64(16),
        "mnemonic_word_count": 24,
        "hkdf_info": "aeat-recovery-v1",
        "created_at": datetime.now(tz=UTC),
    }
    defaults.update(overrides)
    return RecoveryRecord(**defaults)


def test_round_trip_preserves_fields() -> None:
    record = _record()
    blob = record.model_dump_json()
    revived = RecoveryRecord.model_validate_json(blob)
    assert revived == record


def test_rejects_non_24_word_count() -> None:
    with pytest.raises(ValidationError):
        _record(mnemonic_word_count=12)


def test_rejects_malformed_base64_wrapped_dek() -> None:
    with pytest.raises(ValidationError):
        _record(wrapped_dek_b64="!!!not-base64!!!")


def test_rejects_malformed_base64_nonce() -> None:
    with pytest.raises(ValidationError):
        _record(nonce_b64="@@@")


def test_rejects_malformed_base64_tag() -> None:
    with pytest.raises(ValidationError):
        _record(tag_b64="*&^")


def test_rejects_naive_created_at() -> None:
    with pytest.raises(ValidationError):
        _record(created_at=datetime(2026, 1, 1, 0, 0, 0))


def test_rejects_non_utc_offset_created_at() -> None:
    plus_one = timezone(timedelta(hours=1))
    with pytest.raises(ValidationError):
        _record(created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=plus_one))


def test_rejects_empty_hkdf_info() -> None:
    with pytest.raises(ValidationError):
        _record(hkdf_info="")


def test_dropped_base64_field_in_serialized_blob_surfaces_at_reload() -> None:
    """Anti-tautology proof for the RecoveryRecord serialization boundary.

    ``test_round_trip_preserves_fields`` asserts a populated record
    survives ``model_dump_json`` -> ``model_validate_json``. That
    assertion is only meaningful if a corrupted serialized blob is
    rejected on reload. Drop the required ``wrapped_dek_b64`` field from
    the serialized JSON and assert reload raises ``ValidationError`` —
    if a dropped field reloaded silently (re-defaulted or ignored),
    every RecoveryRecord roundtrip assertion would be tautological.
    """

    record = _record()
    document = json.loads(record.model_dump_json())
    assert "wrapped_dek_b64" in document
    del document["wrapped_dek_b64"]

    with pytest.raises(ValidationError):
        RecoveryRecord.model_validate_json(json.dumps(document))


def test_mutated_base64_field_in_serialized_blob_surfaces_as_inequality() -> None:
    """A wrapped-DEK value that diverges on disk must not reload as an
    equal record. Re-encode a different 32-byte secret into
    ``wrapped_dek_b64`` and assert the reloaded record is strictly
    unequal to the original — the boundary carries the field verbatim,
    it does not normalise divergent ciphertext away."""

    record = _record()
    document = json.loads(record.model_dump_json())
    document["wrapped_dek_b64"] = _b64(32)

    revived = RecoveryRecord.model_validate_json(json.dumps(document))
    assert revived != record


def test_rejects_unknown_keys() -> None:
    with pytest.raises(ValidationError):
        RecoveryRecord.model_validate(
            {
                "wrapped_dek_b64": _b64(32),
                "nonce_b64": _b64(12),
                "tag_b64": _b64(16),
                "mnemonic_word_count": 24,
                "hkdf_info": "aeat-recovery-v1",
                "created_at": datetime.now(tz=UTC),
                "unexpected": "nope",
            },
        )


# ── UTC helper migration: validate_utc_aware semantics ─────────────────────


def test_created_at_naive_raises_validation_error() -> None:
    """Naive created_at must be rejected — validate semantic, not coerce."""
    with pytest.raises(ValidationError):
        _record(created_at=datetime(2026, 6, 1, 8, 0, 0))


def test_created_at_utc_aware_accepted_and_preserved() -> None:
    """A UTC-aware created_at is accepted and preserved as-is."""
    ts = datetime(2026, 6, 1, 8, 0, 0, tzinfo=UTC)
    record = _record(created_at=ts)
    assert record.created_at == ts


def test_created_at_non_utc_offset_raises_validation_error() -> None:
    """A timezone-aware datetime whose offset is not UTC must be rejected."""
    from datetime import timedelta, timezone

    plus_two = timezone(timedelta(hours=2))
    with pytest.raises(ValidationError):
        _record(created_at=datetime(2026, 6, 1, 8, 0, 0, tzinfo=plus_two))
