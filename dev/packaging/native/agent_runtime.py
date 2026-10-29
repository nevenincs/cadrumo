"""Build and stage the pinned Node/ACP runtime used by cadrumo-agent.

The agent project owns its Node distribution pin, ``runtime/node.json``: the Node
version and each target's official archive name and SHA-256 digest. The build reads
it from the configured agent folder and keeps no copy of its own.
"""

from __future__ import annotations

import json
import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path

from ..command_execution import run_command
from .agent_runtime_archive import download_node_archive, install_node_archive
from .agent_runtime_inventory import RECEIPT_NAME, is_link_or_reparse, lstat
from .agent_runtime_validation import (
    RUNTIME_FILES,
    NodeRuntimeDeclaration,
    load_runtime_declaration,
    make_receipt,
    target_archive,
    validate_agent_source,
    validate_runtime_payload,
    verify_agent_runtime,
)
from .hashing import digest
from .tree_copy import copy_tree

_STAGED_RECEIPT_NAME = "agent-runtime.json"
_STAGED_NAMES = (
    "node",
    "node_modules",
    "package.json",
    "package-lock.json",
    ".node-version",
    _STAGED_RECEIPT_NAME,
)


def _runtime_current(output: Path, source: Path, target: str, configuration: NodeRuntimeDeclaration) -> bool:
    if lstat(output) is not None:
        if is_link_or_reparse(output) or not output.is_dir():
            raise ValueError("Agent runtime output must be a regular directory")
        try:
            prior = verify_agent_runtime(output, configuration)
        except ValueError:
            prior = None
        if (
            prior is not None
            and prior["target"] == target
            and all(prior["files"].get(name) == digest(source / name) for name in RUNTIME_FILES)
        ):
            return True

    return False


def _install_locked_dependencies(
    runtime: Path, source: Path, work: Path, node: Path, npm_cli: Path, node_version: str
) -> None:
    result = run_command([str(node), "--version"], cwd=work, timeout_seconds=30)
    if result.returncode != 0 or result.stdout.strip() != f"v{node_version}":
        raise ValueError("Configured build Node version differs from the pinned agent runtime")

    npm_config = work / "npm-config"
    npm_config.mkdir()
    user_config = npm_config / "user.npmrc"
    global_config = npm_config / "global.npmrc"
    user_config.write_text("", encoding="utf-8")
    global_config.write_text("", encoding="utf-8")
    environment = _npm_environment(node, user_config, global_config, npm_config / "cache")
    npm_arguments = [
        str(node),
        str(npm_cli),
        "ci",
        "--omit=dev",
        "--omit=optional",
        "--ignore-scripts",
        "--bin-links=false",
        "--no-audit",
        "--no-fund",
    ]
    result = run_command(
        npm_arguments,
        cwd=runtime,
        environment=environment,
        timeout_seconds=900,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Installing the locked agent production dependencies failed with exit status {result.returncode}"
        )
    if digest(runtime / "package-lock.json") != digest(source / "package-lock.json"):
        raise ValueError("npm ci changed the copied agent package lock")


def _publish_runtime(output: Path, runtime: Path, work: Path) -> None:
    previous = work / "previous"
    if output.exists():
        output.rename(previous)
    try:
        runtime.rename(output)
    except BaseException:
        if previous.exists():
            previous.rename(output)
        raise


def build_agent_runtime(output: Path, source: Path, target: str, *, node: Path, npm_cli: Path) -> None:
    """Build an isolated, production-only Node/ACP tree from the configured agent source."""
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError("Configured agent source must be a directory")
    configuration = load_runtime_declaration(source)
    archive_record = target_archive(configuration, target)
    validate_agent_source(source, configuration["node_version"])
    node = node.resolve(strict=True)
    npm_cli = npm_cli.resolve(strict=True)
    if not node.is_file() or not npm_cli.is_file():
        raise ValueError("Configured Node and npm CLI must be regular files")

    output_parent = output.parent.resolve()
    output_parent.mkdir(parents=True, exist_ok=True)
    output = output_parent / output.name
    if output == source or output.is_relative_to(source):
        raise ValueError("Agent runtime output must be outside the agent source tree")
    if _runtime_current(output, source, target, configuration):
        return

    with tempfile.TemporaryDirectory(prefix=".agent-runtime-", dir=output_parent) as temporary:
        work = Path(temporary)
        runtime = work / "runtime"
        runtime.mkdir()
        for name in RUNTIME_FILES:
            shutil.copyfile(source / name, runtime / name)
        (runtime / "node").mkdir()

        archive_path = work / archive_record["archive"]
        download_node_archive(archive_path, configuration["node_version"], archive_record)
        install_node_archive(archive_path, runtime / "node", target, archive_record, configuration["node_version"])

        node_version = configuration["node_version"]
        _install_locked_dependencies(runtime, source, work, node, npm_cli, node_version)

        validate_runtime_payload(runtime, target, configuration)
        receipt = make_receipt(runtime, target, archive_record, node_version)
        (runtime / RECEIPT_NAME).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verify_agent_runtime(runtime, configuration)
        _publish_runtime(output, runtime, work)


def stage_agent_runtime(
    source: Path,
    destination: Path,
    *,
    declaration: NodeRuntimeDeclaration,
    copy_function: Callable[[Path, Path], object] = shutil.copyfile,
) -> None:
    """Copy a verified runtime into the installed ``app/cadrumo`` package root."""
    verify_agent_runtime(source, declaration)
    destination_parent = destination.parent.resolve()
    destination_parent.mkdir(parents=True, exist_ok=True)
    destination = destination_parent / destination.name
    if is_link_or_reparse(destination):
        raise ValueError("Agent runtime destination cannot be a link or junction")
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve(strict=True)
    if os.path.normcase(os.path.abspath(destination)) != os.path.normcase(str(resolved_destination)):
        raise ValueError("Agent runtime destination escapes through a link or junction")

    collisions = [name for name in _STAGED_NAMES if lstat(destination / name) is not None]
    if collisions:
        raise ValueError(f"Agent runtime destination already contains owned paths: {', '.join(collisions)}")

    source = source.resolve(strict=True)
    for name in ("node", "node_modules"):
        copy_tree(source / name, destination / name, copy_function=copy_function)
    for name in RUNTIME_FILES:
        copy_function(source / name, destination / name)
    copy_function(source / RECEIPT_NAME, destination / _STAGED_RECEIPT_NAME)


def _npm_environment(node: Path, user_config: Path, global_config: Path, cache: Path) -> dict[str, str]:
    """Retain only process/network prerequisites; exclude user npm and provider credentials."""
    allowed = {
        "all_proxy",
        "appdata",
        "comspec",
        "curl_ca_bundle",
        "homedrive",
        "homepath",
        "https_proxy",
        "http_proxy",
        "lang",
        "lc_all",
        "localappdata",
        "no_proxy",
        "path",
        "pathext",
        "requests_ca_bundle",
        "shell",
        "ssl_cert_dir",
        "ssl_cert_file",
        "systemroot",
        "temp",
        "tmp",
        "tmpdir",
        "userprofile",
        "windir",
        "node_extra_ca_certs",
    }
    environment = {name: value for name, value in os.environ.items() if name.casefold() in allowed}
    path_key = next((name for name in environment if name.casefold() == "path"), "PATH")
    prior_path = environment.get(path_key, "")
    environment[path_key] = os.pathsep.join(filter(None, (str(node.parent), prior_path)))
    environment.update(
        {
            "npm_config_userconfig": str(user_config),
            "npm_config_globalconfig": str(global_config),
            "npm_config_cache": str(cache),
            "npm_config_audit": "false",
            "npm_config_fund": "false",
            "npm_config_ignore_scripts": "true",
            "npm_config_bin_links": "false",
            "npm_config_update_notifier": "false",
        }
    )
    return environment
