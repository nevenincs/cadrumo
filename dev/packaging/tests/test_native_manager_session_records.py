"""The native manager's session records follow the runtime's record grammar.

The Rust manager reads the same vectors in ``native/manager/tests/session_records.rs``, and
``native/manager/tests/custody_conformance.rs`` exchanges locks and records with the Python
custody primitives in real processes. The verdicts here come from the canonical-JSON owner,
so a change to either side that breaks the shared verdicts fails one of the suites.
"""

from __future__ import annotations

import json
from pathlib import Path, PurePosixPath
from typing import Any

import pytest

from cadrumo.adapters.local_runtime.boot_record import runtime_boot_record_path
from cadrumo.core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant
from cadrumo.core.storage_taxonomy import (
    FingerprintParticipation,
    StorageCategory,
    StorageLifecycle,
    StorageNodeKind,
    StorageOverridePolicy,
    StorageScope,
)
from cadrumo.core.storage_taxonomy_locations import storage_location
from dev._paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_VECTORS: dict[str, Any] = json.loads(
    (REPO_ROOT / "native/manager/tests/session_record_vectors.json").read_text(encoding="utf-8")
)
_MARKERS: dict[str, Any] = _VECTORS["quit_markers"]
_MAXIMUM_BYTES = int(_VECTORS["quit_marker_maximum_bytes"])


def _grammatical(raw: bytes) -> object | None:
    """Return the one object ``raw`` holds under the runtime's record grammar, else ``None``.

    The grammar bounds the bytes and refuses a repeated member or a non-finite constant.
    """
    if len(raw) > _MAXIMUM_BYTES:
        return None
    try:
        parsed: object = json.loads(
            raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def test_the_records_sit_beside_the_boot_record(tmp_path: Path) -> None:
    runtime_directory = runtime_boot_record_path(tmp_path).parent.relative_to(tmp_path).as_posix()
    for key in ("start_claim_location", "quit_marker_location"):
        assert PurePosixPath(_VECTORS[key]).parent.as_posix() == runtime_directory


def test_native_manager_records_are_enrolled_in_the_canonical_storage_taxonomy() -> None:
    expected = {
        StorageCategory.RUNTIME_BOOT_RECORD: ".runtime/boot.json",
        StorageCategory.MANAGER_START_CLAIM: _VECTORS["start_claim_location"],
        StorageCategory.MANAGER_QUIT_RECORD: _VECTORS["quit_marker_location"],
        StorageCategory.MANAGER_FAILED_VERSIONS: ".runtime/manager-failed-versions.json",
        StorageCategory.MANAGER_PREFERENCES: "manager-preferences.json",
        StorageCategory.MANAGER_LOG_FILE: "logs/cadrumo-manager.log",
    }
    for category, path in expected.items():
        location = storage_location(category)
        assert location.subpath == path
        assert location.scope is StorageScope.ROOT
        assert location.node_kind is StorageNodeKind.FILE
        assert location.override_policy is StorageOverridePolicy.FIXED
        assert location.fingerprint_participation is FingerprintParticipation.EXCLUDED
        assert location.lifecycle is (
            StorageLifecycle.ROTATION
            if category is StorageCategory.MANAGER_LOG_FILE
            else StorageLifecycle.UNBOUNDED_BY_DESIGN
        )


def test_canonical_markers_are_what_canonical_json_writes() -> None:
    assert _MARKERS["canonical"]
    for raw in _MARKERS["canonical"]:
        parsed = _grammatical(raw.encode("utf-8"))
        assert parsed is not None, raw
        assert canonical_json_bytes(parsed) == raw.encode("utf-8")


def test_equivalent_spellings_canonicalise_to_their_marker() -> None:
    assert _MARKERS["equivalent"]
    for vector in _MARKERS["equivalent"]:
        parsed = _grammatical(vector["raw"].encode("utf-8"))
        assert parsed is not None, vector["raw"]
        assert canonical_json_bytes(parsed) == vector["canonical"].encode("utf-8")


def test_grammar_refusals_are_refused_by_the_owner() -> None:
    assert _MARKERS["refused"]
    assert [raw for raw in _MARKERS["refused"] if _grammatical(raw.encode("utf-8")) is not None] == []


def test_schema_refusals_are_grammatical_so_the_manager_schema_owns_them() -> None:
    assert _MARKERS["refused_by_manager"]
    assert [raw for raw in _MARKERS["refused_by_manager"] if _grammatical(raw.encode("utf-8")) is None] == []


def test_only_the_bound_refuses_a_padded_marker() -> None:
    padded = _MARKERS["canonical"][0].encode("utf-8").ljust(_MAXIMUM_BYTES, b" ")
    assert _grammatical(padded) is not None
    assert _grammatical(padded + b" ") is None
    assert isinstance(json.loads(padded + b" "), dict)
