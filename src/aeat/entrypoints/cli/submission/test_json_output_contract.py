"""Lock the public JSON contract for every ``--json`` CLI emitter.

The submission CLI ships four commands with machine-readable
``--json`` output: ``verify``, ``diff``, ``schemas``, ``check-nif``.
Downstream consumers (the future deadline engine, review dashboard,
external audit scripts) depend on these shapes, so any accidental
key rename or removal breaks their parsers silently.

This test pins the exact top-level keys each command's happy-path
and error-path responses must contain. Adding NEW keys is
permitted (forward-compatible); removing or renaming existing
keys fails the assertion and forces a conscious review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from . import app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]

_runner = CliRunner()


# ---- Expected key sets ---------------------------------------------------

_VERIFY_OK_RECORD: frozenset[str] = frozenset(
    {"status", "kind", "modelo", "ejercicio", "file", "raw_length", "fields", "casillas"}
)
_VERIFY_OK_ENVELOPE: frozenset[str] = frozenset(
    {"status", "kind", "modelo", "ejercicio", "file", "segments", "fields", "casillas"}
)
_VERIFY_ERROR: frozenset[str] = frozenset({"status", "modelo", "ejercicio", "file", "error_type", "error_message"})

_DIFF_IDENTICAL: frozenset[str] = frozenset(
    {"status", "modelo", "ejercicio", "file_a", "file_b", "bytes", "casilla_deltas", "field_deltas"}
)
_DIFF_MISMATCH: frozenset[str] = frozenset(
    {"status", "modelo", "ejercicio", "file_a", "file_b", "casilla_deltas", "field_deltas"}
)
_DIFF_UNSUPPORTED: frozenset[str] = frozenset({"status", "modelo", "ejercicio", "available"})

_SCHEMAS_ROW: frozenset[str] = frozenset({"modelo", "ejercicio", "kind", "encoding", "bytes", "required_header_fields"})

_CHECK_NIF_VALID: frozenset[str] = frozenset({"status", "input", "canonical", "kind"})
_ERROR_ENVELOPE: frozenset[str] = frozenset(
    {"schema_version", "code", "category", "message", "suggestion", "retryable", "runbook_id", "context", "trace_id"}
)


# ---- Helpers -------------------------------------------------------------


def _write_draft(tmp_path: Path, *, modelo: str, period: str) -> Path:
    payload = {
        "draft_id": f"JSON-{modelo}-{period}",
        "modelo": modelo,
        "period": period,
        "profile_tax_id": "X1234567L",
        "status": "DRAFT",
        "values": {"01": "10000.00"},
        "findings": [],
    }
    path = tmp_path / "draft.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _export(tmp_path: Path, *, modelo: str, period: str) -> Path:
    draft = _write_draft(tmp_path, modelo=modelo, period=period)
    out = tmp_path / "out"
    result = _runner.invoke(
        app,
        [
            "export",
            str(draft),
            "--output-dir",
            str(out),
            "--nombre",
            "KENT",
            "--apellidos",
            "DOE",
            "--tipo",
            "I",
        ],
    )
    assert result.exit_code == 0, result.stdout
    ejercicio = period[:4]
    quarter = period[-2:].replace("Q", "") + "T"
    return out / f"X1234567L{ejercicio}{quarter}.{modelo}"


def _assert_keys_superset(doc: dict[str, Any], expected: frozenset[str], *, where: str) -> None:
    """Assert doc contains every expected key (extra keys OK for forward-compat)."""
    missing = expected - doc.keys()
    assert not missing, f"{where} missing keys {sorted(missing)}; got {sorted(doc.keys())}"


def _unwrap_success(output: str) -> dict[str, Any]:
    doc = cast(dict[str, Any], json.loads(output))
    assert doc["schema_version"] == "1"
    assert "command" in doc
    assert "warnings" in doc
    return doc["result"]


def _unwrap_error(output: str) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(output)["error"])


# ---- verify --json -------------------------------------------------------


class TestVerifyJsonContract:
    def test_record_ok_shape(self, tmp_path: Path) -> None:
        path = _export(tmp_path, modelo="130", period="2024Q1")
        result = _runner.invoke(app, ["verify", str(path), "--json"])
        assert result.exit_code == 0, result.stdout
        doc = _unwrap_success(result.stdout)
        _assert_keys_superset(doc, _VERIFY_OK_RECORD, where="verify --json (130 OK)")
        assert doc["status"] == "ok"
        assert doc["kind"] == "record"

    def test_envelope_ok_shape(self, tmp_path: Path) -> None:
        path = _export(tmp_path, modelo="303", period="2024Q1")
        result = _runner.invoke(app, ["verify", str(path), "--json"])
        assert result.exit_code == 0, result.stdout
        doc = _unwrap_success(result.stdout)
        _assert_keys_superset(doc, _VERIFY_OK_ENVELOPE, where="verify --json (303 OK)")
        assert doc["status"] == "ok"
        assert doc["kind"] == "envelope"
        assert isinstance(doc["segments"], list)

    def test_error_shape_on_corrupt_payload(self, tmp_path: Path) -> None:
        bad = tmp_path / "bad.130"
        bad.write_bytes(b"NOT-A-VALID-PAYLOAD\r\n")
        result = _runner.invoke(app, ["verify", str(bad), "--modelo", "130", "--ejercicio", "2024", "--json"])
        assert result.exit_code == 2
        assert result.stdout == ""
        doc = _unwrap_error(result.stderr)
        _assert_keys_superset(doc, _ERROR_ENVELOPE, where="verify --json (error)")
        assert doc["category"] == "REFUSED"


# ---- diff --json ---------------------------------------------------------


class TestDiffJsonContract:
    def test_identical_shape(self, tmp_path: Path) -> None:
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        a = _export(tmp_path / "a", modelo="130", period="2024Q1")
        b = _export(tmp_path / "b", modelo="130", period="2024Q1")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--json"])
        assert result.exit_code == 0, result.stdout
        doc = _unwrap_success(result.stdout)
        _assert_keys_superset(doc, _DIFF_IDENTICAL, where="diff --json (identical)")
        assert doc["status"] == "identical"
        assert doc["casilla_deltas"] == []

    def test_mismatch_shape(self, tmp_path: Path) -> None:
        # A with casilla 01 = 10000; B with casilla 01 = 99999
        (tmp_path / "a").mkdir()
        (tmp_path / "b").mkdir()
        draft_a = _write_draft(tmp_path / "a", modelo="130", period="2024Q1")
        draft_b_payload = json.loads(draft_a.read_text(encoding="utf-8"))
        draft_b_payload["values"]["01"] = "99999.00"
        draft_b = tmp_path / "b" / "draft.json"
        draft_b.write_text(json.dumps(draft_b_payload), encoding="utf-8")
        out_a = tmp_path / "a" / "out"
        out_b = tmp_path / "b" / "out"
        for draft, out in ((draft_a, out_a), (draft_b, out_b)):
            _runner.invoke(
                app,
                [
                    "export",
                    str(draft),
                    "--output-dir",
                    str(out),
                    "--nombre",
                    "KENT",
                    "--apellidos",
                    "DOE",
                ],
            )
        file_a = out_a / "X1234567L20241T.130"
        file_b = out_b / "X1234567L20241T.130"
        result = _runner.invoke(app, ["diff", str(file_a), str(file_b), "--json"])
        assert result.exit_code == 1
        doc = _unwrap_success(result.stdout)
        _assert_keys_superset(doc, _DIFF_MISMATCH, where="diff --json (mismatch)")
        assert doc["status"] == "mismatch"
        casilla_deltas = cast(list[dict[str, Any]], doc["casilla_deltas"])
        assert any(d["casilla"] == "01" for d in casilla_deltas)

    def test_unsupported_shape(self, tmp_path: Path) -> None:
        a = tmp_path / "placeholder.390"
        b = tmp_path / "placeholder2.390"
        a.write_bytes(b"  ")
        b.write_bytes(b"  ")
        result = _runner.invoke(app, ["diff", str(a), str(b), "--modelo", "390", "--ejercicio", "2024", "--json"])
        assert result.exit_code == 2
        assert result.stdout == ""
        doc = _unwrap_error(result.stderr)
        _assert_keys_superset(doc, _ERROR_ENVELOPE, where="diff --json (unsupported)")
        assert doc["category"] == "REFUSED"


# ---- schemas --json ------------------------------------------------------


class TestSchemasJsonContract:
    def test_each_row_shape(self) -> None:
        result = _runner.invoke(app, ["schemas", "--json"])
        assert result.exit_code == 0, result.stdout
        rows = _unwrap_success(result.stdout)
        assert isinstance(rows, list) and rows
        for row in rows:
            _assert_keys_superset(row, _SCHEMAS_ROW, where=f"schemas --json row {row}")


# ---- check-nif --json ----------------------------------------------------


class TestCheckNifJsonContract:
    def test_valid_shape(self) -> None:
        result = _runner.invoke(app, ["check-nif", "X1234567L", "--json"])
        assert result.exit_code == 0, result.stdout
        doc = _unwrap_success(result.stdout)
        _assert_keys_superset(doc, _CHECK_NIF_VALID, where="check-nif --json (valid)")
        assert doc["status"] == "valid"

    def test_invalid_shape(self) -> None:
        result = _runner.invoke(app, ["check-nif", "X1234567Z", "--json"])
        assert result.exit_code == 2
        assert result.stdout == ""
        doc = _unwrap_error(result.stderr)
        _assert_keys_superset(doc, _ERROR_ENVELOPE, where="check-nif --json (invalid)")
        assert doc["category"] == "REFUSED"
