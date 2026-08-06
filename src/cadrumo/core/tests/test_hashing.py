"""Behavioral contracts for canonical JSON content hashing."""

from __future__ import annotations

import pytest

from ..hashing import canonical_json_bytes, content_hash_hex

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_content_hash_hex_uses_ascii_compact_sorted_json_bytes() -> None:
    """A known canonical byte sequence fixes the content-addressing contract."""
    payload = {"answer": 42, "accent": "niño"}

    assert canonical_json_bytes(payload) == b'{"accent":"ni\\u00f1o","answer":42}'
    assert content_hash_hex(payload) == "3014db16127d55af495fa84bec59ba920dfe882865170c915556b8ce082f76c3"


def test_content_hash_hex_changes_for_content_but_not_mapping_order() -> None:
    """Equivalent mappings share an id while a changed value receives a new one."""
    first = {"axis_label": "renta-2025", "captured_at": "2026-04-03T10:00:00+00:00", "payload_text": "alpha"}
    reordered = {"payload_text": "alpha", "captured_at": "2026-04-03T10:00:00+00:00", "axis_label": "renta-2025"}

    assert content_hash_hex(first) == content_hash_hex(reordered)
    assert content_hash_hex(first) != content_hash_hex({**first, "payload_text": "alpha "})
