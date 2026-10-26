"""Compact recording layout preserves provenance and localizes record diffs."""

from __future__ import annotations

import difflib
import json
from pathlib import Path

import pytest

from dev._paths import REPO_ROOT

from ..json_layout import format_sequence_json

pytestmark = [pytest.mark.unit, pytest.mark.hex_core, pytest.mark.docs]


def test_record_arrays_preserve_values_and_localize_changes() -> None:
    records = [
        {"box": str(index), "value": "0.00", "absent": False, "source": None, "refs": ["ley:á", "x"]}
        for index in range(32)
    ]
    document = {"records": records, "empty_object": {}, "empty_array": [], "escaped": '"\\\n</script>'}
    before = format_sequence_json(document)
    assert json.loads(before) == document
    assert format_sequence_json(json.loads(before)) == before
    assert len(before) < len(json.dumps(document, ensure_ascii=False, indent=2)) * 0.65

    records[9]["value"] = "12.34"
    after = format_sequence_json(document)
    changed = [line for line in difflib.ndiff(before.splitlines(), after.splitlines()) if line[:2] in {"- ", "+ "}]
    assert len(changed) == 2
    assert all('"box":"9"' in line for line in changed)
    assert json.loads(after) == document


def test_large_records_stay_expanded_and_small_documents_keep_standard_layout() -> None:
    document = {"rows": [{"nested": {"detail": "x" * 1100}, "value": index} for index in range(16)]}
    assert format_sequence_json(document) == json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2)
    small = {"z": [False, None, 0, "0", {"a": []}], "a": {"x": "á"}}
    assert format_sequence_json(small) == json.dumps(small, ensure_ascii=False, sort_keys=True, indent=2)


def test_entire_recording_corpus_roundtrips_without_losing_fields() -> None:
    root: Path = REPO_ROOT / "docs" / "_sequences"
    recordings = 0
    pretty_bytes = compact_bytes = 0
    for path in root.rglob("*.json"):
        raw = path.read_text(encoding="utf-8")
        document = json.loads(raw)
        if not isinstance(document, dict) or "golden_schema_version" not in document:
            continue
        recordings += 1
        compact = format_sequence_json(document)
        assert json.dumps(json.loads(compact), sort_keys=True) == json.dumps(document, sort_keys=True), path
        assert raw == compact + "\n", f"refresh the recording layout: {path}"
        pretty_bytes += len(json.dumps(document, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8"))
        compact_bytes += len(compact.encode("utf-8"))
    assert recordings > 0
    assert compact_bytes < pretty_bytes * 0.7
