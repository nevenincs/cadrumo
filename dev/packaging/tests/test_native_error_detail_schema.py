"""The native relay reads a stopped operation's detail under the schema identity its Python owner publishes.

The desktop's runtime relay has no definition contract naming the error-detail
schema, so it pins the identity. A pin that drifted from
``operation_error_detail_schema()`` would make every detail read refuse and
every refused feature lose its setup offer, so the pin is read from the Rust
source and compared here.
"""

from __future__ import annotations

import re

import pytest

from cadrumo.application.operations.error_detail import operation_error_detail_schema
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_RELAY = REPO_ROOT / "native" / "application" / "src" / "person_operations.rs"
_PINS = {
    "schema_id": re.compile(r'const ERROR_DETAIL_SCHEMA_ID: &str = "([^"]+)";'),
    "schema_version": re.compile(r"const ERROR_DETAIL_SCHEMA_VERSION: u64 = (\d+);"),
    "schema_fingerprint": re.compile(r'const ERROR_DETAIL_SCHEMA_FINGERPRINT: &str =\s*"([0-9a-f]{64})";'),
}


def _pinned(source: str) -> dict[str, object]:
    found: dict[str, object] = {}
    for key, pattern in _PINS.items():
        matches = pattern.findall(source)
        assert len(matches) == 1, f"the relay pins {key} {len(matches)} times"
        found[key] = int(matches[0]) if key == "schema_version" else matches[0]
    return found


def test_the_relay_pins_the_published_error_detail_schema() -> None:
    assert _pinned(_RELAY.read_text(encoding="utf-8")) == operation_error_detail_schema().model_dump(mode="json")


def test_a_pin_that_drifted_from_the_published_schema_is_told_apart() -> None:
    source = _RELAY.read_text(encoding="utf-8")
    published = operation_error_detail_schema().model_dump(mode="json")
    drifted = source.replace(str(published["schema_fingerprint"]), "0" * 64)
    assert drifted != source
    assert _pinned(drifted) != published
    with pytest.raises(AssertionError, match="pins schema_id 0 times"):
        _pinned(source.replace("ERROR_DETAIL_SCHEMA_ID", "ERROR_DETAIL_ID"))
