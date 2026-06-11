"""Tests for bucket-history CLI filter parsing."""

from __future__ import annotations

import pytest
import typer

from .....domain.buckets import BucketEventType
from .. import _parse_bucket_event_types

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


def test_parse_bucket_event_types_returns_typed_filters() -> None:
    parsed = _parse_bucket_event_types(
        [
            BucketEventType.LEDGER_TRANSACTION_CREATED.value,
            BucketEventType.MODELO_FILED.value,
        ],
    )

    assert parsed == (
        BucketEventType.LEDGER_TRANSACTION_CREATED,
        BucketEventType.MODELO_FILED,
    )


def test_parse_bucket_event_types_rejects_unknown_value_with_localized_message() -> None:
    with pytest.raises(typer.BadParameter) as exc_info:
        _parse_bucket_event_types(["not-a-bucket-event"])

    message = str(exc_info.value)
    assert "not-a-bucket-event" in message
    assert BucketEventType.LEDGER_TRANSACTION_CREATED.value in message
    assert "BucketEventType" not in message
