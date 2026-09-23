"""Receipt publication by the installed assets TUI child."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from dev.acceptance.assets.installed_tui_child import InstalledAssetTuiReceipt, write_receipt_atomically

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _receipt(stage: str) -> InstalledAssetTuiReceipt:
    return InstalledAssetTuiReceipt(
        schema_version="test",
        status="running",
        stage=stage,
        product_origin="site-packages",
        product_init_sha256="0" * 64,
        completed_stages=("probe",),
    )


def test_a_receipt_held_open_by_a_polling_reader_is_replaced_once_released(tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"
    write_receipt_atomically(path=path, receipt=_receipt("probe"))
    reader = path.open("rb")
    release = threading.Timer(0.2, reader.close)
    release.start()
    try:
        # On Windows the open reader makes the first replacements fail with a sharing violation.
        write_receipt_atomically(path=path, receipt=_receipt("home"))
    finally:
        release.cancel()
        reader.close()

    assert json.loads(path.read_text(encoding="utf-8"))["stage"] == "home"
    assert not path.with_suffix(".json.tmp").exists()
