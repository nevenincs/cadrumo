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


def test_manifest_validates_and_self_installs_via_uvx() -> None:
    """The shipped manifest validates and self-installs cadrumo[agent] via uvx.

    The bundle no longer requires a prior ``pip install cadrumo[agent]``: its
    ``server.mcp_config`` launches ``uvx --from cadrumo[agent]==<version>
    cadrumo-mcp`` — the same bootstrap the Claude plugin uses — so opening it in
    Claude Desktop installs the package from PyPI on first run. The persona AND
    surface user_config options are wired through the env passthrough.
    """
    manifest = BUILD.load_manifest()
    assert manifest["name"] == "cadrumo"
    server = manifest["server"]
    assert isinstance(server, dict)
    mcp_config = server["mcp_config"]
    assert mcp_config["command"] == "uvx"
    assert mcp_config["args"] == ["--from", f"cadrumo[agent]=={manifest['version']}", "cadrumo-mcp"]
    assert server["entry_point"] == "cadrumo-mcp"
    assert mcp_config["env"] == {
        "CADRUMO_MCP_PERSONA": "${user_config.persona}",
        "CADRUMO_MCP_SURFACE": "${user_config.surface}",
    }
    # Both user_config options the env interpolates are declared.
    assert set(manifest["user_config"]) == {"persona", "surface"}
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
    assert "aeat" not in " ".join(mcp_config["args"])


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


def test_build_produces_a_wellformed_bundle_stamped_to_the_package_version(tmp_path: Path) -> None:
    """A real build produces a ``.mcpb`` zip carrying the version-stamped manifest."""
    bundle = BUILD.build(dist_dir=tmp_path)
    assert bundle.exists() and bundle.name == "cadrumo.mcpb"
    with zipfile.ZipFile(bundle) as archive:
        assert archive.namelist() == ["manifest.json"]
        embedded = json.loads(archive.read("manifest.json"))
    assert embedded["name"] == "cadrumo"
    # The shipped bundle is stamped from pyproject at build time (single-sourced),
    # so it can never carry a stale version or a stale uvx pin.
    assert embedded == BUILD.stamped_manifest()
    version = BUILD._package_version()
    assert embedded["version"] == version
    mcp_config = embedded["server"]["mcp_config"]
    assert mcp_config["command"] == "uvx"
    assert mcp_config["args"] == ["--from", f"cadrumo[agent]=={version}", "cadrumo-mcp"]


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


def test_mcpb_version_and_uvx_pin_agree_with_package_and_plugin() -> None:
    """Parity gate: mcpb manifest version == uvx pin == package version == plugin identity.

    A release bump cannot leave a stale pin: the committed manifest version, the
    committed ``uvx --from cadrumo[agent]==<version>`` pin, the root pyproject
    version, and the in-package ``__version__`` must all agree. The distribution
    and console-script strings the manifest and builder hardcode must equal the
    plugin generator's canonical ``PRODUCT_IDENTITY`` values, so the mcpb and
    plugin launch the identical server.
    """
    import tomllib

    from cadrumo import __version__
    from cadrumo.core.product_identity import PRODUCT_IDENTITY

    repo_root = Path(__file__).resolve().parents[3]
    manifest = json.loads((repo_root / "packaging" / "mcpb" / "manifest.json").read_text("utf-8"))
    pyproject = tomllib.loads((repo_root / "pyproject.toml").read_text("utf-8"))
    package_version = pyproject["project"]["version"]

    # Every version surface agrees.
    assert manifest["version"] == package_version
    assert __version__ == package_version

    # The committed uvx pin agrees with the manifest version and uses the plugin's
    # canonical distribution + console script (so mcpb and plugin boot the same
    # server the same way).
    args = manifest["server"]["mcp_config"]["args"]
    assert args == [
        "--from",
        f"{PRODUCT_IDENTITY.distribution}[agent]=={package_version}",
        PRODUCT_IDENTITY.mcp_executable,
    ]
    # The builder's own hardcoded identity strings match PRODUCT_IDENTITY.
    assert PRODUCT_IDENTITY.distribution == BUILD._DISTRIBUTION
    assert PRODUCT_IDENTITY.mcp_executable == BUILD._CONSOLE_SCRIPT
