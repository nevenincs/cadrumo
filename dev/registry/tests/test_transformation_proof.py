from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from cadrumo.core.hashing import canonical_json_bytes

from ..transformation_proof import (
    fingerprint_source_closure,
    fingerprint_source_tree,
    prove_transformation,
    snapshot_definition,
    write_transformation_receipt,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


class _Definition:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.dump_arguments: dict[str, Any] = {}

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:
        self.dump_arguments = kwargs
        return self.payload


def test_source_closure_fingerprint_detects_addition_deletion_and_byte_edit(tmp_path: Path) -> None:
    (tmp_path / "a.toml").write_bytes(b"id = 'a'\n")
    (tmp_path / "b.toml").write_bytes(b"id = 'b'\r\n")

    original = fingerprint_source_closure(tmp_path, ["b.toml", "a.toml"])
    assert [item.relative_path for item in original.files] == ["a.toml", "b.toml"]

    edited_path = tmp_path / "b.toml"
    edited_path.write_bytes(b"id = 'b'\n")
    edited = fingerprint_source_closure(tmp_path, ["a.toml", "b.toml"])
    added = fingerprint_source_closure(tmp_path, ["a.toml", "b.toml", _write(tmp_path, "c.toml", b"id='c'\n")])
    deleted = fingerprint_source_closure(tmp_path, ["b.toml"])

    assert len({original.sha256, edited.sha256, added.sha256, deleted.sha256}) == 4
    assert original.files[1].byte_count != edited.files[1].byte_count


def test_source_closure_refuses_escape_and_duplicate_paths(tmp_path: Path) -> None:
    _write(tmp_path, "a.toml", b"x=1")
    with pytest.raises(ValueError, match="relative file path"):
        fingerprint_source_closure(tmp_path, ["../a.toml"])
    with pytest.raises(ValueError, match="duplicate"):
        fingerprint_source_closure(tmp_path, ["a.toml", "a.toml"])


def test_source_tree_reenumeration_detects_a_new_file(tmp_path: Path) -> None:
    _write(tmp_path, "a.toml", b"x=1")
    before = fingerprint_source_tree(tmp_path)
    _write(tmp_path, "new.toml", b"x=2")
    after = fingerprint_source_tree(tmp_path)
    assert before.sha256 != after.sha256
    assert [item.relative_path for item in after.files] == ["a.toml", "new.toml"]


def test_snapshot_keeps_unknown_defaults_nulls_locales_and_explicit_metadata() -> None:
    definition = _Definition({"known": 1, "future_schema_field": {"defaulted": False, "nullable": None}})
    snapshot = snapshot_definition(
        definition,
        locale_fields={"revisions.2026.casillas.1.localization_keys": ["modelo.1"]},
        representation_metadata={"source_file_count": 2},
    )

    assert definition.dump_arguments == {"mode": "json", "exclude_defaults": False, "exclude_none": False}
    assert snapshot.definition["future_schema_field"] == {"defaulted": False, "nullable": None}
    assert snapshot.representation_metadata == {"source_file_count": 2}


def test_raw_mapping_snapshot_preserves_toml_scalar_type_distinctions() -> None:
    temporal = snapshot_definition({"value": date(2026, 9, 14)}, locale_fields={})
    string = snapshot_definition({"value": "2026-09-14"}, locale_fields={})
    number = snapshot_definition({"value": 1.0}, locale_fields={})
    boolean = snapshot_definition({"value": True}, locale_fields={})

    assert temporal.definition == {"value": {"$toml_type": "date", "value": "2026-09-14"}}
    assert len({temporal.sha256, string.sha256, number.sha256, boolean.sha256}) == 4


def test_proof_reports_the_first_nested_definition_or_locale_mismatch() -> None:
    before = snapshot_definition(
        _Definition({"revisions": {"2026": {"rows": [{"id": "1", "required": True}]}}}),
        locale_fields={"1": ["one"]},
    )
    after = snapshot_definition(
        _Definition({"revisions": {"2026": {"rows": [{"id": "1", "required": False}]}}}),
        locale_fields={"1": ["one"]},
    )

    proof = prove_transformation(before, after)
    assert not proof.is_equivalent
    assert proof.first_mismatch == "$.definition.revisions.2026.rows[0].required"

    locale_after = snapshot_definition(_Definition(before.definition), locale_fields={"1": ["uno"]})
    assert prove_transformation(before, locale_after).first_mismatch == "$.locale_fields.1[0]"


def test_equivalent_receipt_is_canonical_json_and_contains_no_runtime_envelope(tmp_path: Path) -> None:
    snapshot = snapshot_definition(_Definition({"modelo": "303", "revisions": {}}), locale_fields={})
    proof = prove_transformation(snapshot, snapshot)
    receipt = tmp_path / "proof.json"

    write_transformation_receipt(receipt, proof)

    assert proof.is_equivalent and proof.first_mismatch is None
    raw = receipt.read_bytes()
    payload = json.loads(raw)
    assert raw == canonical_json_bytes(payload) + b"\n"
    assert set(payload) == {"after", "before", "first_mismatch", "is_equivalent"}
    assert "taxpayer" not in raw.decode("utf-8")


def _write(root: Path, name: str, contents: bytes) -> str:
    (root / name).write_bytes(contents)
    return name
