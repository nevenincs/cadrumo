"""Real-behavior tests for the ``.mcpb`` Desktop Extension build.

The repo-root ``packaging/`` directory cannot be imported as ``packaging.mcpb``
(the name collides with the installed PyPA ``packaging`` library), so the build
module is loaded by file path — exactly how it is meant to be run
(``python packaging/mcpb/build.py``), never as an importable package.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import zipfile
from pathlib import Path
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_BUILD_PY = Path(__file__).resolve().parents[1] / "build.py"


def _load_build_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_cadrumo_mcpb_build", _BUILD_PY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUILD = _load_build_module()


def test_manifest_validates_and_points_at_the_console_script() -> None:
    """The shipped manifest validates and its server command is ``cadrumo-mcp``."""
    manifest = BUILD.load_manifest()
    assert manifest["name"] == "cadrumo"
    server = manifest["server"]
    assert isinstance(server, dict)
    assert server["mcp_config"]["command"] == "cadrumo-mcp"
    assert server["entry_point"] == "cadrumo-mcp"
    assert manifest["display_name"] == "Cadrumo tax assistant console"
    assert all(
        tool["name"].startswith("cadrumo_") or tool["name"] in {"search", "execute"} for tool in manifest["tools"]
    )

    assert manifest["name"] != "aeat"
    assert server["entry_point"] != "aeat-mcp"
    assert server["mcp_config"]["command"] != "aeat-mcp"


def test_check_mode_writes_nothing_and_passes(capsys: pytest.CaptureFixture[str]) -> None:
    """``--check`` validates the manifest, prints a valid line, and writes no bundle."""
    rc = BUILD.main(["--check"])
    assert rc == 0
    output = capsys.readouterr().out
    assert "manifest.json valid: cadrumo" in output
    assert "aeat" not in output.casefold()


def test_real_check_cli_reports_the_cadrumo_manifest() -> None:
    """The real script entry point validates the committed Cadrumo manifest."""
    completed = subprocess.run(  # noqa: S603 - fixed interpreter, repository-owned script and arguments
        [sys.executable, str(_BUILD_PY), "--check"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr
    assert "manifest.json valid: cadrumo" in completed.stdout
    assert completed.stderr == ""


def test_build_produces_a_wellformed_bundle(tmp_path: Path) -> None:
    """A real build produces a ``.mcpb`` zip carrying the manifest verbatim."""
    bundle = BUILD.build(dist_dir=tmp_path)
    assert bundle.exists() and bundle.name == "cadrumo.mcpb"
    with zipfile.ZipFile(bundle) as archive:
        assert archive.namelist() == ["manifest.json"]
        embedded = json.loads(archive.read("manifest.json"))
    assert embedded["name"] == "cadrumo"
    assert embedded == BUILD.load_manifest()
    assert embedded["server"]["mcp_config"]["command"] == "cadrumo-mcp"


# --- signing mechanism -------------------------------------------------------
def test_build_reports_the_real_signing_outcome_without_overclaiming(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The host's real signer state controls the diagnostic; no signature is fabricated."""
    signing_available = BUILD._signing_available()
    bundle = BUILD.build(dist_dir=tmp_path)
    captured = capsys.readouterr()
    assert bundle.exists()
    assert f"built {bundle}" in captured.out
    assert "aeat.mcpb" not in captured.out.casefold()
    if not signing_available:
        assert "UNSIGNED (signer unavailable or no signing identity configured)" in captured.out
        assert captured.err == ""
    else:
        assert (
            "[signed]" in captured.out
            or "[UNSIGNED (signer unavailable or no signing identity configured)]" in captured.out
        )


def test_sign_invokes_the_mcpb_cli_when_a_signer_is_available(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """With a signer available, the build invokes `mcpb sign <bundle>` — the sign path is wired."""
    # Simulate a present signer + a successful sign, and assert the build invokes
    # `mcpb sign <bundle>` — proving the sign path runs when an identity exists.
    import subprocess

    bundle = tmp_path / "cadrumo.mcpb"
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

    bundle = tmp_path / "cadrumo.mcpb"
    bundle.write_bytes(b"PK\x03\x04")

    def _failing_run(argv: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(argv, returncode=1, stdout="", stderr="no identity configured")

    monkeypatch.setattr(BUILD.shutil, "which", lambda _name: "/usr/bin/mcpb")
    monkeypatch.setattr(BUILD.subprocess, "run", _failing_run)

    assert BUILD._sign(bundle) is False


def test_manifest_version_matches_the_package_release() -> None:
    """The bundle manifest must move in lockstep with the pyproject version.

    The honesty review found the served plugin pinned a release two minors
    behind source; this gate keeps at least the in-repo manifest honest.
    """
    import tomllib

    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo_root / "packaging" / "mcpb" / "manifest.json").read_text("utf-8"))
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text("utf-8"))
    assert manifest["version"] == pyproject["project"]["version"]
