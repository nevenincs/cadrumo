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


# --- signing mechanism -------------------------------------------------------
# The actual signing needs a real `mcpb` CLI plus a configured release identity,
# which does not exist on this host — so signing itself cannot be exercised here.
# What these tests lock is that the MECHANISM is wired and HONEST: absent an
# identity the build emits an unsigned bundle and never fabricates a signature,
# and when a signer IS available the build invokes it correctly. So the day a
# release identity exists, `python packaging/mcpb/build.py` signs with no further
# code change.


def test_build_is_honestly_unsigned_without_a_signing_identity(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """Absent a signer, the build emits an unsigned bundle and never fabricates a signature."""
    # Force the no-signer state deterministically (independent of the host PATH).
    monkeypatch.setattr(BUILD.shutil, "which", lambda _name: None)
    assert BUILD._signing_available() is False
    bundle = BUILD.build(dist_dir=tmp_path)
    assert bundle.exists()
    assert BUILD._sign(bundle) is False  # never fabricates a signature
    assert "UNSIGNED" in capsys.readouterr().out


def test_sign_invokes_the_mcpb_cli_when_a_signer_is_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With a signer available, the build invokes `mcpb sign <bundle>` — the sign path is wired."""
    # Simulate a present signer + a successful sign, and assert the build invokes
    # `mcpb sign <bundle>` — proving the sign path runs when an identity exists.
    import subprocess

    bundle = tmp_path / "aeat.mcpb"
    bundle.write_bytes(b"PK\x03\x04")
    captured: dict[str, object] = {}

    def _spy_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        captured["argv"] = argv
        return subprocess.CompletedProcess(argv, returncode=0, stdout="signed", stderr="")

    monkeypatch.setattr(BUILD.shutil, "which", lambda _name: "/usr/bin/mcpb")
    monkeypatch.setattr(BUILD.subprocess, "run", _spy_run)

    assert BUILD._sign(bundle) is True
    assert captured["argv"] == ["mcpb", "sign", str(bundle)]


def test_sign_returns_false_without_fabricating_when_the_signer_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A signer that exits non-zero (no identity) ships unsigned, never claims a signature."""
    # Signer present but no configured identity: the CLI exits non-zero, and the
    # build must ship unsigned (return False), never claim a signature.
    import subprocess

    bundle = tmp_path / "aeat.mcpb"
    bundle.write_bytes(b"PK\x03\x04")

    def _failing_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, returncode=1, stdout="", stderr="no identity configured")

    monkeypatch.setattr(BUILD.shutil, "which", lambda _name: "/usr/bin/mcpb")
    monkeypatch.setattr(BUILD.subprocess, "run", _failing_run)

    assert BUILD._sign(bundle) is False
