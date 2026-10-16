"""Verify the bundled Node/ACP closure and its staged runtime receipt."""

from __future__ import annotations

import hashlib
import io
import json
import os
import stat
import tarfile
import zipfile
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import httpx
import pytest

from .. import agent_runtime

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_NODE_VERSION = "26.10.0"
_ACP_PACKAGE = "@agentclientprotocol/claude-agent-acp"


def test_runtime_declaration_pins_all_supported_official_archives() -> None:
    """The four supported package targets use reviewed Node archive identities."""
    declaration = json.loads(agent_runtime._RUNTIME_CONFIG.read_text(encoding="utf-8"))
    assert declaration["schema_version"] == 1
    assert declaration["node_version"] == _NODE_VERSION
    assert declaration["targets"] == {
        "windows-x86-64": {
            "archive": "node-v26.10.0-win-x64.zip",
            "sha256": "9fef7eca6743a6b910989cd8e78712376b394fcb9b6e1e9c44a0799a287f90c5",
        },
        "linux-x86-64": {
            "archive": "node-v26.10.0-linux-x64.tar.xz",
            "sha256": "ca70e9e349de048b9522abb3adc05b3bd6f43c5ffd3ec57916c7da292f59f022",
        },
        "linux-aarch64": {
            "archive": "node-v26.10.0-linux-arm64.tar.xz",
            "sha256": "7a6353f63eb3d04765004b4adf172616243e4522434635cb1d26288658b04ab5",
        },
        "macos-arm64": {
            "archive": "node-v26.10.0-darwin-arm64.tar.gz",
            "sha256": "751fdf7439f115d87ee2a8f3f18c065b6151852068e3e666ac60ac2996f75ac9",
        },
    }


@pytest.mark.parametrize("target", ["windows-x86-64", "linux-x86-64"])
def test_build_uses_locked_production_closure_and_stage_preserves_package_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str
) -> None:
    """npm runs against copied inputs with scripts/dev/optional/bin links disabled."""
    source = _agent_source(tmp_path / "agent-source")
    node, npm_cli = _build_tools(tmp_path)
    archive = _node_archive(target)
    _point_config_at_archive(tmp_path, monkeypatch, target, archive)
    _mock_download(monkeypatch, archive)
    monkeypatch.setenv("NPM_TOKEN", "fixture-only-token")
    monkeypatch.setenv("NODE_AUTH_TOKEN", "fixture-only-token")
    calls = _mock_npm(monkeypatch, node)

    output = tmp_path / "build" / "agent" / "runtime"
    agent_runtime.build_agent_runtime(output, source, target, node=node, npm_cli=npm_cli)

    assert len(calls) == 2
    install_argv, install_cwd, install_environment = calls[1]
    assert install_argv[:3] == [str(node), str(npm_cli), "ci"]
    assert set(install_argv[3:]) == {
        "--omit=dev",
        "--omit=optional",
        "--ignore-scripts",
        "--bin-links=false",
        "--no-audit",
        "--no-fund",
    }
    assert install_cwd.name == "runtime"
    assert not install_cwd.exists()
    assert "NPM_TOKEN" not in install_environment
    assert "NODE_AUTH_TOKEN" not in install_environment
    assert install_environment["npm_config_userconfig"].endswith("user.npmrc")
    assert (source / "package-lock.json").read_bytes() == _package_lock_bytes()
    assert (source / "node_modules/dev-only-fixture/index.js").read_text(encoding="utf-8") == "source-only\n"

    expected_node = output / "node" / ("node.exe" if target == "windows-x86-64" else "bin/node")
    assert expected_node.read_bytes() == b"pinned-node-binary"
    assert (output / "node/LICENSE").read_bytes() == b"Node runtime license\n"
    assert not (output / "node-archive-extracted").exists()
    assert not (output / "node/node_modules").exists()
    assert not (output / "node_modules/.bin").exists()
    assert not (output / "node_modules/dev-only-fixture").exists()
    assert not any(path.name.startswith("claude-agent-sdk-") for path in (output / "node_modules").rglob("*"))
    assert (output / "node_modules/@agentclientprotocol/claude-agent-acp/LICENSE").is_file()
    assert (output / "node_modules/@agentclientprotocol/claude-agent-acp/NOTICE").is_file()

    receipt = agent_runtime.verify_agent_runtime(output)
    assert receipt["target"] == target
    assert receipt["node_version"] == _NODE_VERSION
    assert receipt["package_lock_sha256"] == hashlib.sha256(_package_lock_bytes()).hexdigest()
    assert "node/LICENSE" in receipt["files"]
    assert _ACP_ENTRY_NAME in receipt["files"]

    package_root = tmp_path / "app" / "cadrumo"
    package_root.mkdir(parents=True)
    (package_root / "existing-package.py").write_text("preserve\n", encoding="utf-8")
    agent_runtime.stage_agent_runtime(output, package_root)
    assert (package_root / "existing-package.py").read_text(encoding="utf-8") == "preserve\n"
    assert (package_root / expected_node.relative_to(output)).read_bytes() == b"pinned-node-binary"
    assert (package_root / "node_modules" / _ACP_ENTRY_NAME.removeprefix("node_modules/")).is_file()
    assert (package_root / "agent-runtime.json").read_bytes() == (output / "runtime-receipt.json").read_bytes()
    assert not (package_root / "runtime-receipt.json").exists()


def test_posix_archive_copies_only_regular_node_and_license_not_distribution_links(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The POSIX path never extracts the distribution's npm symlink or other members."""
    source = _agent_source(tmp_path / "agent-source")
    node, npm_cli = _build_tools(tmp_path)
    archive = _node_archive("linux-x86-64", include_distribution_symlink=True)
    _point_config_at_archive(tmp_path, monkeypatch, "linux-x86-64", archive)
    _mock_download(monkeypatch, archive)
    _mock_npm(monkeypatch, node)

    output = tmp_path / "build" / "agent" / "runtime"
    agent_runtime.build_agent_runtime(output, source, "linux-x86-64", node=node, npm_cli=npm_cli)

    assert (output / "node/bin/node").read_bytes() == b"pinned-node-binary"
    assert (output / "node/LICENSE").read_bytes() == b"Node runtime license\n"
    assert not (output / "node/bin/npm").exists()
    if os.name == "posix":
        assert stat.S_IMODE((output / "node/bin/node").stat().st_mode) == 0o755


def test_runtime_reuses_locked_node_closure_across_python_edits(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _agent_source(tmp_path / "agent-source")
    node, npm_cli = _build_tools(tmp_path)
    archive = _node_archive("windows-x86-64")
    _point_config_at_archive(tmp_path, monkeypatch, "windows-x86-64", archive)
    _mock_download(monkeypatch, archive)
    calls = _mock_npm(monkeypatch, node)
    output = tmp_path / "build/agent/runtime"
    agent_runtime.build_agent_runtime(output, source, "windows-x86-64", node=node, npm_cli=npm_cli)
    previous = (output / "runtime-receipt.json").stat().st_mtime_ns
    (source / "agent.py").write_text("changed = True\n", encoding="utf-8")

    agent_runtime.build_agent_runtime(output, source, "windows-x86-64", node=node, npm_cli=npm_cli)

    assert len(calls) == 2
    assert (output / "runtime-receipt.json").stat().st_mtime_ns == previous


def test_runtime_rebuilds_tampered_payload_without_destroying_previous_tree_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = _agent_source(tmp_path / "agent-source")
    node, npm_cli = _build_tools(tmp_path)
    archive = _node_archive("windows-x86-64")
    _point_config_at_archive(tmp_path, monkeypatch, "windows-x86-64", archive)
    _mock_download(monkeypatch, archive)
    calls = _mock_npm(monkeypatch, node)
    output = tmp_path / "build/agent/runtime"
    agent_runtime.build_agent_runtime(output, source, "windows-x86-64", node=node, npm_cli=npm_cli)
    (output / "node/node.exe").write_bytes(b"changed")

    agent_runtime.build_agent_runtime(output, source, "windows-x86-64", node=node, npm_cli=npm_cli)

    assert len(calls) == 4
    assert (output / "node/node.exe").read_bytes() == b"pinned-node-binary"
    agent_runtime.verify_agent_runtime(output)


def test_builder_refuses_sdk_platform_cli_payload_and_does_not_publish_partial_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The shipped ACP adapter cannot smuggle the SDK's optional Claude CLI into the package."""
    source = _agent_source(tmp_path / "agent-source")
    node, npm_cli = _build_tools(tmp_path)
    archive = _node_archive("windows-x86-64")
    _point_config_at_archive(tmp_path, monkeypatch, "windows-x86-64", archive)
    _mock_download(monkeypatch, archive)

    def install_with_sdk_cli(argv: Sequence[str], *, cwd: Path, **kwargs: Any) -> Any:
        if argv[1:] == ["--version"]:
            return SimpleNamespace(returncode=0, stdout=f"v{_NODE_VERSION}\n", stderr="")
        _install_fixture_acp(cwd / "node_modules")
        sdk_cli = cwd / "node_modules/@anthropic-ai/claude-agent-sdk-win32-x64"
        sdk_cli.mkdir(parents=True)
        (sdk_cli / "claude.exe").write_bytes(b"platform cli")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(agent_runtime, "run_command", install_with_sdk_cli)
    output = tmp_path / "build" / "agent" / "runtime"
    with pytest.raises(ValueError, match="platform CLI payload"):
        agent_runtime.build_agent_runtime(output, source, "windows-x86-64", node=node, npm_cli=npm_cli)
    assert not output.exists()


def test_verifier_refuses_changed_or_added_runtime_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A package cannot be staged after a receipt-covered file changes or an unlisted file appears."""
    output = _build_runtime(tmp_path, monkeypatch, "windows-x86-64")
    (output / _ACP_ENTRY_NAME).write_text("changed", encoding="utf-8")
    with pytest.raises(ValueError, match="differs from its receipt"):
        agent_runtime.verify_agent_runtime(output)

    (output / _ACP_ENTRY_NAME).write_text("acp entry\n", encoding="utf-8")
    (output / "unexpected-empty-directory").mkdir()
    with pytest.raises(ValueError, match="differs from its receipt"):
        agent_runtime.stage_agent_runtime(output, tmp_path / "app" / "cadrumo")
    assert not (tmp_path / "app" / "cadrumo" / "node").exists()


def test_stage_refuses_owned_path_collision_without_overwriting_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Staging owns only named runtime paths and does not replace an existing package member."""
    output = _build_runtime(tmp_path, monkeypatch, "windows-x86-64")
    package_root = tmp_path / "app" / "cadrumo"
    package_root.mkdir(parents=True)
    existing_node = package_root / "node"
    existing_node.mkdir()
    (existing_node / "owned-by-other-package").write_text("preserve", encoding="utf-8")

    with pytest.raises(ValueError, match="already contains owned paths"):
        agent_runtime.stage_agent_runtime(output, package_root)
    assert (existing_node / "owned-by-other-package").read_text(encoding="utf-8") == "preserve"


def test_download_rejects_wrong_archive_digest_and_removes_partial_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A failed hash admission leaves no archive or partial download in the output tree."""
    archive = tmp_path / "node.zip"
    payload = _node_archive("windows-x86-64")
    _mock_download(monkeypatch, payload)
    row = {
        "archive": "node-v26.10.0-win-x64.zip",
        "sha256": "0" * 64,
    }

    with pytest.raises(ValueError, match="SHA256 mismatch"):
        agent_runtime._download_node_archive(archive, _NODE_VERSION, row)
    assert not archive.exists()
    assert not archive.with_name(archive.name + ".partial").exists()


_ACP_ENTRY_NAME = "node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js"


def _build_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> Path:
    source = _agent_source(tmp_path / "agent-source")
    node, npm_cli = _build_tools(tmp_path)
    archive = _node_archive(target)
    _point_config_at_archive(tmp_path, monkeypatch, target, archive)
    _mock_download(monkeypatch, archive)
    _mock_npm(monkeypatch, node)
    output = tmp_path / "build" / "agent" / "runtime"
    agent_runtime.build_agent_runtime(output, source, target, node=node, npm_cli=npm_cli)
    return output


def _agent_source(source: Path) -> Path:
    source.mkdir(parents=True)
    package = {
        "private": True,
        "name": "cadrumo-agent",
        "engines": {"node": _NODE_VERSION},
        "dependencies": {_ACP_PACKAGE: "0.85.1"},
        "devDependencies": {"dev-only-fixture": "1.2.3"},
    }
    (source / "package.json").write_text(json.dumps(package), encoding="utf-8")
    (source / "package-lock.json").write_bytes(_package_lock_bytes())
    (source / ".node-version").write_text(f"{_NODE_VERSION}\n", encoding="utf-8")
    development_dependency = source / "node_modules/dev-only-fixture"
    development_dependency.mkdir(parents=True)
    (development_dependency / "index.js").write_text("source-only\n", encoding="utf-8")
    return source


def _package_lock_bytes() -> bytes:
    return (
        json.dumps(
            {
                "name": "cadrumo-agent",
                "lockfileVersion": 3,
                "packages": {"": {"name": "cadrumo-agent", "dependencies": {_ACP_PACKAGE: "0.85.1"}}},
            }
        )
    ).encode("utf-8")


def _build_tools(root: Path) -> tuple[Path, Path]:
    node = root / "build tools" / "node.exe"
    npm_cli = root / "build tools" / "npm-cli.js"
    node.parent.mkdir(parents=True, exist_ok=True)
    node.write_bytes(b"builder node executable")
    npm_cli.write_text("builder npm cli", encoding="utf-8")
    return node, npm_cli


def _node_archive(target: str, *, include_distribution_symlink: bool = False) -> bytes:
    suffix, kind = agent_runtime._NODE_TARGETS[target]
    archive_root = f"node-v{_NODE_VERSION}-{suffix}"
    if kind == "zip":
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr(f"{archive_root}/node.exe", b"pinned-node-binary")
            bundle.writestr(f"{archive_root}/LICENSE", b"Node runtime license\n")
            bundle.writestr(f"{archive_root}/node_modules/npm/bin/npm-cli.js", b"not shipped")
        return output.getvalue()

    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode="w:gz") as bundle:
        executable = tarfile.TarInfo(f"{archive_root}/bin/node")
        executable.size = len(b"pinned-node-binary")
        executable.mode = 0o755
        bundle.addfile(executable, io.BytesIO(b"pinned-node-binary"))
        license_entry = tarfile.TarInfo(f"{archive_root}/LICENSE")
        license_entry.size = len(b"Node runtime license\n")
        bundle.addfile(license_entry, io.BytesIO(b"Node runtime license\n"))
        if include_distribution_symlink:
            symlink = tarfile.TarInfo(f"{archive_root}/bin/npm")
            symlink.type = tarfile.SYMTYPE
            symlink.linkname = "node"
            bundle.addfile(symlink)
    return output.getvalue()


def _point_config_at_archive(root: Path, monkeypatch: pytest.MonkeyPatch, target: str, archive: bytes) -> None:
    config_path = root / "runtime.json"
    configuration = json.loads(agent_runtime._RUNTIME_CONFIG.read_text(encoding="utf-8"))
    configuration["targets"][target]["sha256"] = hashlib.sha256(archive).hexdigest()
    config_path.write_text(json.dumps(configuration), encoding="utf-8")
    monkeypatch.setattr(agent_runtime, "_RUNTIME_CONFIG", config_path)


def _mock_download(monkeypatch: pytest.MonkeyPatch, archive: bytes) -> None:
    @contextmanager
    def stream(method: str, url: str | httpx.URL, **_kwargs: Any) -> Any:
        response = httpx.Response(200, content=archive, request=httpx.Request(method, url))
        try:
            yield response
        finally:
            response.close()

    monkeypatch.setattr(agent_runtime.httpx, "stream", stream)


def _mock_npm(monkeypatch: pytest.MonkeyPatch, node: Path) -> list[tuple[list[str], Path, Mapping[str, str]]]:
    calls: list[tuple[list[str], Path, Mapping[str, str]]] = []

    def run(argv: Sequence[str], *, cwd: Path, environment: Mapping[str, str] | None = None, **_kwargs: Any) -> Any:
        actual = list(argv)
        env = dict(environment or {})
        calls.append((actual, cwd, env))
        if actual == [str(node.resolve()), "--version"]:
            return SimpleNamespace(returncode=0, stdout=f"v{_NODE_VERSION}\n", stderr="")
        _install_fixture_acp(cwd / "node_modules")
        dependency = cwd / "node_modules/@agentclientprotocol/sdk/dist/index.js"
        dependency.parent.mkdir(parents=True, exist_ok=True)
        dependency.write_text("locked dependency\n", encoding="utf-8")
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(agent_runtime, "run_command", run)
    return calls


def _install_fixture_acp(node_modules: Path) -> None:
    package = node_modules / "@agentclientprotocol/claude-agent-acp"
    (package / "dist").mkdir(parents=True, exist_ok=True)
    (package / "package.json").write_text(
        json.dumps(
            {
                "name": _ACP_PACKAGE,
                "version": "0.85.1",
                "bin": {"claude-agent-acp": "dist/index.js"},
            }
        ),
        encoding="utf-8",
    )
    (package / "dist/index.js").write_text("acp entry\n", encoding="utf-8")
    (package / "LICENSE").write_text("ACP license\n", encoding="utf-8")
    (package / "NOTICE").write_text("ACP notice\n", encoding="utf-8")
