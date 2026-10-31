"""Discovery records readable source inputs without private build settings."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ...google_oauth import GOOGLE_OAUTH_RESOURCE
from ..discovered_inputs import _write_discovered_inputs

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_discovery_omits_private_settings_and_build_outputs(tmp_path: Path) -> None:
    root = tmp_path / "checkout"
    source = root / "src" / "product.py"
    private = root / GOOGLE_OAUTH_RESOURCE
    environment = root / "env" / "client.json"
    built = root / "build" / "output.txt"
    for path in (source, private, environment, built):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("fixture", encoding="utf-8")
    receipt = tmp_path / "discovered.json"

    _write_discovered_inputs(receipt, root.resolve(), {str(path) for path in (source, private, environment, built)})

    assert json.loads(receipt.read_text(encoding="utf-8")) == [source.as_posix()]
