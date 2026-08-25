"""The notification-document history reports documents, never a balance."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from .._app_live_notifications_payloads import NotificationDocumentHistoryResult

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FORBIDDEN_AMOUNT_AGGREGATES = frozenset({"total", "balance", "payable", "sum", "aggregate"})


def _aggregate_fields(schema: Mapping[str, object]) -> set[str]:
    """Find amount-aggregation field names recursively in a JSON schema."""
    found: set[str] = set()
    properties = schema.get("properties")
    if isinstance(properties, Mapping):
        for raw_name, child in properties.items():
            name = str(raw_name).casefold()
            if any(token in name for token in _FORBIDDEN_AMOUNT_AGGREGATES):
                found.add(str(raw_name))
            if isinstance(child, Mapping):
                found.update(_aggregate_fields(child))
    for key in ("$defs", "items", "anyOf", "oneOf", "allOf"):
        child = schema.get(key)
        if isinstance(child, Mapping):
            found.update(_aggregate_fields(child))
        elif isinstance(child, list):
            for item in child:
                if isinstance(item, Mapping):
                    found.update(_aggregate_fields(item))
    return found


def test_notification_document_history_schema_declares_no_cross_document_total() -> None:
    assert _aggregate_fields(NotificationDocumentHistoryResult.model_json_schema()) == set()


def test_no_total_gate_detects_a_mutated_schema_shape() -> None:
    mutated = {
        "type": "object",
        "properties": {
            "documents": {"type": "array", "items": {"type": "object"}},
            "payable_total": {"type": "string"},
        },
    }
    assert _aggregate_fields(mutated) == {"payable_total"}
