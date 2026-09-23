"""Focused checks for the installed Ledger import provenance driver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..installed_provenance import (
    _parse_child_receipt,
    assert_detail_provenance,
    assert_json_provenance,
    assert_track_text_provenance,
    main,
)
from ..installed_tui_journey import LedgerInstalledTuiError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_FILE = "ledger-provenance-statement.csv"


def test_track_text_requires_exact_source_and_row_lines() -> None:
    assert_track_text_provenance(f"id\tabc\nimport_source\t{_FILE}\nimport_source_row\t2\n", filename=_FILE, row=2)

    with pytest.raises(LedgerInstalledTuiError, match="track text"):
        assert_track_text_provenance(f"id\tabc\nimport_source\t{_FILE}\n", filename=_FILE, row=2)
    with pytest.raises(LedgerInstalledTuiError, match="track text"):
        assert_track_text_provenance(
            f"import_source\t{_FILE}.bak\nimport_source_row\t2\n",
            filename=_FILE,
            row=2,
        )
    with pytest.raises(LedgerInstalledTuiError, match="track text"):
        assert_track_text_provenance(f"import_source\t{_FILE}\nimport_source_row\t21\n", filename=_FILE, row=2)


def test_json_provenance_refuses_the_older_envelope_without_filename_or_row() -> None:
    assert_json_provenance({"source_filename": _FILE, "source_row_index": 2}, filename=_FILE, row=2, stage="track")

    with pytest.raises(LedgerInstalledTuiError, match="track did not expose"):
        assert_json_provenance({"transaction": {}}, filename=_FILE, row=2, stage="track")
    with pytest.raises(LedgerInstalledTuiError, match="track did not expose"):
        assert_json_provenance({"source_filename": _FILE, "source_row_index": 3}, filename=_FILE, row=2, stage="track")


def test_detail_provenance_requires_the_row_beside_the_filename() -> None:
    assert_detail_provenance(f"Source  {_FILE}:2", filename=_FILE, row=2, stage="detail")

    with pytest.raises(LedgerInstalledTuiError, match="detail did not display"):
        assert_detail_provenance(f"Source  {_FILE}", filename=_FILE, row=2, stage="detail")


def test_child_receipt_requires_both_detail_observations(tmp_path: Path) -> None:
    receipt = tmp_path / "child.json"
    document = {
        "schema_version": "ledger-01-installed-provenance-v1",
        "status": "proven",
        "product_origin": "site-packages",
        "product_init_path": "site-packages/cadrumo/__init__.py",
        "product_init_sha256": "a" * 64,
        "observations": ["installed_tui_invoice_source_filename_and_row"],
    }
    receipt.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(LedgerInstalledTuiError, match="did not prove both details"):
        _parse_child_receipt(receipt)


def test_outer_run_refuses_a_used_output_root_with_a_value_free_failed_receipt(tmp_path: Path) -> None:
    environment = tmp_path / "venv" / "Scripts"
    environment.mkdir(parents=True)
    (environment / "aeat.exe").write_bytes(b"synthetic")
    (environment / "python.exe").write_bytes(b"synthetic")
    wheel = tmp_path / "cadrumo-0.0.0-py3-none-any.whl"
    wheel.write_bytes(b"synthetic wheel")
    authority = tmp_path / "authority"
    authority.mkdir()
    output_root = tmp_path / "prior-run"
    output_root.mkdir()
    marker = output_root / "prior-receipt.json"
    marker.write_text("synthetic", encoding="utf-8")
    receipt = tmp_path / "receipt.json"

    exit_code = main(
        [
            "--cli",
            str(environment / "aeat.exe"),
            "--python",
            str(environment / "python.exe"),
            "--wheel",
            str(wheel),
            "--workspace-root",
            str(tmp_path),
            "--authority-root",
            str(authority),
            "--output-root",
            str(output_root),
            "--source-commit",
            "0" * 40,
            "--receipt",
            str(receipt),
        ]
    )

    document = json.loads(receipt.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert document == {
        "diagnostic": "Ledger provenance output root must be fresh and empty",
        "error_type": "LedgerInstalledTuiError",
        "schema_version": "ledger-01-installed-provenance-v1",
        "status": "failed",
    }
    assert marker.read_text(encoding="utf-8") == "synthetic"


def test_outer_run_without_wheel_identity_fails_closed(tmp_path: Path) -> None:
    receipt = tmp_path / "receipt.json"

    exit_code = main(["--workspace-root", str(tmp_path), "--receipt", str(receipt)])

    document = json.loads(receipt.read_text(encoding="utf-8"))
    assert exit_code == 2
    assert document["status"] == "failed"
    assert document["diagnostic"] == "installed provenance outer run lacks its wheel and source inputs"
