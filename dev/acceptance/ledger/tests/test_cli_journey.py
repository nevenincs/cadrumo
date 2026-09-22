"""Failure receipt checks for the LEDGER-01 installed CLI driver."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..cli_journey import main

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def test_a_nonempty_store_refuses_before_any_installed_command(tmp_path: Path) -> None:
    store = tmp_path / "store"
    store.mkdir()
    (store / "prior-run-marker").write_text("synthetic", encoding="utf-8")
    receipt = tmp_path / "receipt.json"

    exit_code = main(
        (
            "--cli",
            str(tmp_path / "unused-aeat"),
            "--authority-root",
            str(tmp_path / "unused-authority"),
            "--storage-root",
            str(store),
            "--output-root",
            str(tmp_path / "output"),
            "--receipt",
            str(receipt),
            "--year",
            "2025",
            "--package-identity",
            "test-source",
        )
    )

    assert exit_code == 2
    assert json.loads(receipt.read_text(encoding="utf-8")) == {
        "status": "failed",
        "brief_revision": "0.1",
        "pattern_revision": "1.7",
        "scenario": "ledger-cli-lifecycle-v1",
        "package_identity": "test-source",
        "error_type": "LedgerJourneyError",
        "diagnostic": "storage root must be fresh and empty",
    }
    assert (store / "prior-run-marker").read_text(encoding="utf-8") == "synthetic"
    assert not (tmp_path / "output").exists()
