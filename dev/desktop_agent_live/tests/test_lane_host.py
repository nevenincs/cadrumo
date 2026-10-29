"""The lane starts the desktop against the package of the configuration its recorded test host was built in."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from .. import lane_stage
from ..lane_errors import UnavailableError

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _record(build: Path, **fields: object) -> None:
    executable = build / "host" / "cadrumo.exe"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"host image")
    record = build / "desktop" / "testing" / "packaged" / "host.json"
    record.parent.mkdir(parents=True)
    value = {
        "executable": str(executable),
        "features": ["webview2-remote-debugging"],
        "sha256": hashlib.sha256(b"host image").hexdigest(),
        "shell": None,
        **fields,
    }
    record.write_text(json.dumps(value), encoding="utf-8")


@pytest.mark.parametrize("configuration", ["Debug", "Release"])
def test_the_package_follows_the_host_configuration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configuration: str
) -> None:
    monkeypatch.setattr(lane_stage, "_BUILD", tmp_path)
    monkeypatch.setattr(lane_stage, "_TESTING", tmp_path / "desktop" / "testing")
    monkeypatch.setattr(lane_stage, "_STAGE", tmp_path / "stage")
    _record(tmp_path, configuration=configuration)
    host = lane_stage.test_host(served=False)
    assert host.configuration == configuration
    assert host.package == tmp_path / "stage" / configuration / "app"


@pytest.mark.parametrize("configuration", [None, "", "MinSizeRel"])
def test_a_host_record_without_a_known_configuration_is_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, configuration: object
) -> None:
    monkeypatch.setattr(lane_stage, "_BUILD", tmp_path)
    monkeypatch.setattr(lane_stage, "_TESTING", tmp_path / "desktop" / "testing")
    fields = {} if configuration is None else {"configuration": configuration}
    _record(tmp_path, **fields)
    with pytest.raises(UnavailableError, match="build configuration"):
        lane_stage.test_host(served=False)
