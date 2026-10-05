"""The native manager's protocol and boot-record vectors agree with their Python owners.

The Rust manager reads the same vectors in ``native/manager/tests/protocol_conformance.rs``.
Each verdict here comes from the runtime's own grammar, so a change to either side that
breaks the shared verdicts fails one of the two suites.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from cadrumo.adapters.local_runtime.boot_record import (
    decode_runtime_boot_record,
    encode_runtime_boot_record,
    runtime_boot_record_path,
)
from cadrumo.application.runtime.contracts import RuntimeExitReason
from cadrumo.core.hashing import reject_duplicate_json_members, reject_json_constant
from cadrumo.entrypoints.runtime.supervised_protocol import (
    MAX_LINE_BYTES,
    RuntimeAnnouncement,
    RuntimeStopping,
    decode_supervisor_command,
    encode_runtime_announcement,
)
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_VECTORS: dict[str, Any] = json.loads(
    (REPO_ROOT / "native/manager/tests/protocol_vectors.json").read_text(encoding="utf-8")
)
_ANNOUNCEMENTS: TypeAdapter[RuntimeAnnouncement] = TypeAdapter(RuntimeAnnouncement)


def _runtime_accepts(line: str) -> bool:
    """Apply the runtime's line grammar: ASCII, bounded, unique members, strict models."""
    raw = line.encode("utf-8")
    if len(raw) >= MAX_LINE_BYTES:
        return False
    try:
        text = raw.decode("ascii")
        json.loads(text, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant)
        _ANNOUNCEMENTS.validate_json(text, strict=True)
    except (UnicodeDecodeError, ValueError, ValidationError):
        return False
    return True


def _record_accepted(raw: str) -> bool:
    try:
        decode_runtime_boot_record(raw.encode("utf-8"))
    except (ValueError, ValidationError, TypeError, RecursionError):
        return False
    return True


def test_line_bound_and_record_location_match_the_owners(tmp_path: Path) -> None:
    assert _VECTORS["max_line_bytes"] == MAX_LINE_BYTES
    location = runtime_boot_record_path(tmp_path).relative_to(tmp_path)
    assert location.as_posix() == _VECTORS["boot_record_location"]


def test_manager_commands_decode_to_the_named_command() -> None:
    for vector in _VECTORS["commands"]:
        expected = {key: value for key, value in vector.items() if key != "line"}
        assert decode_supervisor_command(vector["line"].encode("ascii")).model_dump() == expected


def test_canonical_announcements_are_exactly_what_the_runtime_writes() -> None:
    for line in _VECTORS["announcements"]["canonical"]:
        announcement = _ANNOUNCEMENTS.validate_json(line, strict=True)
        assert encode_runtime_announcement(announcement) == line.encode("ascii") + b"\n"


def test_every_stop_reason_has_a_canonical_vector() -> None:
    reasons = [
        announcement.reason
        for line in _VECTORS["announcements"]["canonical"]
        if isinstance(announcement := _ANNOUNCEMENTS.validate_json(line, strict=True), RuntimeStopping)
    ]
    assert reasons == list(RuntimeExitReason)


@pytest.mark.parametrize(
    ("kind", "accepted"),
    [("canonical", True), ("accepted", True), ("refused", False), ("refused_by_manager_only", True)],
)
def test_announcement_verdicts_follow_the_runtime_grammar(kind: str, accepted: bool) -> None:
    lines = _VECTORS["announcements"][kind]
    assert lines
    assert [line for line in lines if _runtime_accepts(line) != accepted] == []


def test_the_canonical_boot_record_is_what_the_runtime_publishes() -> None:
    for raw in _VECTORS["boot_records"]["canonical"]:
        assert encode_runtime_boot_record(decode_runtime_boot_record(raw.encode("utf-8"))) == raw.encode("utf-8")


@pytest.mark.parametrize(
    ("kind", "accepted"),
    [("canonical", True), ("accepted", True), ("refused", False), ("refused_by_manager_only", True)],
)
def test_boot_record_verdicts_follow_the_runtime_owner(kind: str, accepted: bool) -> None:
    records = _VECTORS["boot_records"][kind]
    assert records
    assert [raw for raw in records if _record_accepted(raw) != accepted] == []
