"""Tests for the :class:`RecoveryRecord` BIP-39 envelope."""

from __future__ import annotations

import base64
import secrets
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

import pytest
from pydantic import ValidationError

from ._recovery_record import RecoveryRecord

pytestmark = [pytest.mark.unit, pytest.mark.domain_persistence]


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
            }
        )
