"""Tests for packaging smoke evidence manifests."""

from __future__ import annotations

import json

import pytest

from dev.packaging.smoke_core import _manifest_path, _write_smoke_manifest

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_smoke_manifest_records_successful_run_evidence(tmp_path) -> None:
    """Manifest writes durable run evidence with relative artifact paths."""
    wheel = tmp_path / "wheel" / "aeat-0.1.0-py3-none-any.whl"
    wheel.parent.mkdir()
    wheel.write_bytes(b"wheel-smoke")

    manifest = _write_smoke_manifest(
        tmp_path,
        lane="core-wheel",
        artifacts={"wheel": _manifest_path(tmp_path, wheel)},
        checks=("wheel metadata dependency surface", "installed CLI config/profile smoke"),
        details={"python": "3.13"},
    )

    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["ok"] is True
    assert payload["lane"] == "core-wheel"
    assert payload["artifacts"] == {"wheel": "wheel/aeat-0.1.0-py3-none-any.whl"}
    assert payload["checks"] == ["wheel metadata dependency surface", "installed CLI config/profile smoke"]
    assert payload["details"] == {"python": "3.13"}
    assert payload["work_dir"] == str(tmp_path.resolve())
    assert payload["completed_at"].endswith("Z")
