"""Real-behavior tests for the ``.mcpb`` Desktop Extension build.

The repo-root ``packaging/`` directory cannot be imported as ``packaging.mcpb``
(the name collides with the installed PyPA ``packaging`` library), so the build
module is loaded by file path — exactly how it is meant to be run
(``python packaging/mcpb/build.py``), never as an importable package.
"""

from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUILD_PY = Path(__file__).resolve().parents[1] / "build.py"


def _load_build_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_aeat_mcpb_build", _BUILD_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = _load_build_module()


def test_manifest_validates_and_points_at_the_console_script() -> None:
    """The shipped manifest validates and its server command is ``aeat-mcp``."""
    manifest = BUILD.load_manifest()
    assert manifest["name"] == "aeat"
    server = manifest["server"]
    assert isinstance(server, dict)
    assert server["mcp_config"]["command"] == "aeat-mcp"


def test_check_mode_writes_nothing_and_passes(capsys: pytest.CaptureFixture[str]) -> None:
    """``--check`` validates the manifest, prints a valid line, and writes no bundle."""
    rc = BUILD.main(["--check"])
    assert rc == 0
    assert "valid" in capsys.readouterr().out


def test_build_produces_a_wellformed_bundle(tmp_path: Path) -> None:
    """A real build produces a ``.mcpb`` zip carrying the manifest verbatim."""
    bundle = BUILD.build(dist_dir=tmp_path)
    assert bundle.exists() and bundle.suffix == ".mcpb"
    with zipfile.ZipFile(bundle) as archive:
        assert "manifest.json" in archive.namelist()
        embedded = json.loads(archive.read("manifest.json"))
    assert embedded["name"] == "aeat"
    assert embedded["server"]["mcp_config"]["command"] == "aeat-mcp"


def test_a_manifest_without_a_command_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A manifest whose ``mcp_config`` carries no command fails validation."""
    broken = tmp_path / "manifest.json"
    broken.write_text(
        json.dumps(
            {
                "manifest_version": "0.2",
                "name": "aeat",
                "version": "0.1.0",
                "description": "x",
                "server": {"type": "binary", "mcp_config": {}},
            },
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(BUILD, "_MANIFEST", broken)
    with pytest.raises(BUILD.ManifestError):
        BUILD.load_manifest()
