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
    assert server["mcp_config"]["env"] == {
        "CADRUMO_MCP_PERSONA": "${user_config.persona}",
    }
    assert manifest["display_name"] == "Cadrumo tax assistant console"
    assert {tool["name"] for tool in manifest["tools"]} == {
        "cadrumo_harness_load",
        "cadrumo_corpus_search",
        "cadrumo_terminology_search",
        "cadrumo_contract",
        "search",
        "execute",
    }

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
    elif "[signed]" in captured.out:
        assert captured.err == ""
    else:
        assert "[UNSIGNED (signer unavailable or no signing identity configured)]" in captured.out
        assert captured.err.startswith("mcpb sign failed (no identity?); shipping unsigned:")


def test_manifest_version_matches_the_package_release() -> None:
    """The bundle manifest must move in lockstep with the pyproject version.

    A served plugin can otherwise pin a release several minors behind
    source; this gate keeps at least the in-repo manifest honest.
    """
    import tomllib

    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo_root / "packaging" / "mcpb" / "manifest.json").read_text("utf-8"))
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text("utf-8"))
    assert manifest["version"] == pyproject["project"]["version"]
