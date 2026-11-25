"""Validate the pinned agent runtime and its receipts."""

from __future__ import annotations

import json
import re
from pathlib import Path, PurePosixPath
from typing import TypedDict, TypeGuard, cast

from ..runtime_wheelhouse_contract import SUPPORTED_TARGETS, target_platform
from .agent_runtime_archive import NODE_TARGETS
from .agent_runtime_inventory import RECEIPT_NAME, inventory_runtime, is_link_or_reparse, lstat, validate_relative_name


def _is_mapping(value: object) -> TypeGuard[dict[str, object]]:
    return isinstance(value, dict)


def _is_string_list(value: object) -> TypeGuard[list[str]]:
    return isinstance(value, list) and all(isinstance(item, str) for item in cast(list[object], value))


def _is_file_inventory(value: object) -> TypeGuard[dict[str, str]]:
    return isinstance(value, dict) and all(
        isinstance(name, str) and isinstance(digest, str) and _SHA256_RE.fullmatch(digest)
        for name, digest in cast(dict[object, object], value).items()
    )


class NodeRuntimeDeclaration(TypedDict):
    """Validated agent-owned Node version and per-target archive pins."""

    schema_version: int
    node_version: str
    targets: dict[str, dict[str, str]]


class AgentRuntimeReceipt(TypedDict):
    """Validated receipt for one exact runtime tree."""

    schema_version: int
    target: str
    node_version: str
    node_archive: str
    node_archive_sha256: str
    package_lock_sha256: str
    directories: list[str]
    files: dict[str, str]


RUNTIME_DECLARATION = PurePosixPath("runtime/node.json")
"""The agent-owned Node distribution pin, relative to the agent project folder."""
_ACP_PACKAGE = "@agentclientprotocol/claude-agent-acp"
_ACP_ENTRY = PurePosixPath("node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js")
_SDK_CLI_PREFIX = "claude-agent-sdk-"
RUNTIME_FILES = ("package.json", "package-lock.json", ".node-version")
_NODE_VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")


def _read_runtime_receipt(receipt_path: Path) -> dict[str, object]:
    if is_link_or_reparse(receipt_path) or not receipt_path.is_file():
        raise ValueError("Agent runtime receipt is missing or is not a regular file")
    try:
        receipt: object = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Agent runtime receipt is invalid") from exc
    if not _is_mapping(receipt) or set(receipt) != {
        "schema_version",
        "target",
        "node_version",
        "node_archive",
        "node_archive_sha256",
        "package_lock_sha256",
        "directories",
        "files",
    }:
        raise ValueError("Agent runtime receipt has an unsupported shape")
    if type(receipt["schema_version"]) is not int or receipt["schema_version"] != 1:
        raise ValueError("Agent runtime receipt schema is unsupported")
    return receipt


def _verify_receipt_pin(receipt: dict[str, object], declaration: NodeRuntimeDeclaration) -> str:
    target = receipt["target"]
    if not isinstance(target, str):
        raise ValueError("Agent runtime receipt target is invalid")
    archive_record = target_archive(declaration, target)
    if (
        receipt["node_version"] != declaration["node_version"]
        or receipt["node_archive"] != archive_record["archive"]
        or receipt["node_archive_sha256"] != archive_record["sha256"]
    ):
        raise ValueError("Agent runtime receipt differs from the pinned target declaration")

    return target


def _validate_receipt_paths(directories: list[str], files: dict[str, str]) -> None:
    for name in [*directories, *files]:
        validate_relative_name(name)


def _receipt_inventory(receipt: dict[str, object]) -> tuple[list[str], dict[str, str]]:
    directories = receipt["directories"]
    files = receipt["files"]
    if not _is_string_list(directories):
        raise ValueError("Agent runtime receipt directory inventory is invalid")
    if not _is_file_inventory(files):
        raise ValueError("Agent runtime receipt file inventory is invalid")
    _validate_receipt_paths(directories, files)
    if RECEIPT_NAME in files:
        raise ValueError("Agent runtime receipt cannot hash itself")

    return directories, files


def verify_agent_runtime(source: Path, declaration: NodeRuntimeDeclaration) -> AgentRuntimeReceipt:
    """Verify a build receipt against the exact runtime tree and the agent's Node pin; return the receipt."""
    if lstat(source) is None or is_link_or_reparse(source) or not source.is_dir():
        raise ValueError("Agent runtime source must be a regular directory")
    source = source.resolve(strict=True)
    receipt = _read_runtime_receipt(source / RECEIPT_NAME)
    target = _verify_receipt_pin(receipt, declaration)
    directories, files = _receipt_inventory(receipt)
    actual_directories, actual_files = inventory_runtime(source)
    if actual_directories != directories or actual_files != files:
        raise ValueError("Agent runtime tree differs from its receipt")
    if receipt["package_lock_sha256"] != files.get("package-lock.json"):
        raise ValueError("Agent runtime receipt lock digest is inconsistent")
    validate_runtime_payload(source, target, declaration)
    return cast(AgentRuntimeReceipt, receipt)


def _validate_target_archive(target: str, row: object, version: str) -> None:
    suffix, extension = NODE_TARGETS[target]
    expected_archive = f"node-v{version}-{suffix}.{extension}"
    if (
        not _is_mapping(row)
        or set(row) != {"archive", "sha256"}
        or row["archive"] != expected_archive
        or not isinstance(row["sha256"], str)
        or not _SHA256_RE.fullmatch(row["sha256"])
    ):
        raise ValueError(f"Pinned Node archive declaration is invalid for {target}")


def _validate_targets(targets: object, version: str) -> None:
    expected_targets = {item.name for item in SUPPORTED_TARGETS}
    if not _is_mapping(targets) or set(targets) != expected_targets or expected_targets != set(NODE_TARGETS):
        raise ValueError("Pinned agent runtime targets do not match supported package targets")
    for target, row in targets.items():
        _validate_target_archive(target, row, version)


def load_runtime_declaration(source: Path) -> NodeRuntimeDeclaration:
    """Read and check the agent project's Node distribution pin."""
    path = source / RUNTIME_DECLARATION
    if is_link_or_reparse(path) or not path.is_file():
        raise ValueError(f"Configured agent project has no regular {RUNTIME_DECLARATION}: {source}")
    try:
        configuration: object = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Pinned agent runtime declaration is invalid") from exc
    if not _is_mapping(configuration) or set(configuration) != {"schema_version", "node_version", "targets"}:
        raise ValueError("Pinned agent runtime declaration has an unsupported shape")
    if type(configuration["schema_version"]) is not int or configuration["schema_version"] != 1:
        raise ValueError("Pinned agent runtime declaration schema is unsupported")
    version = configuration["node_version"]
    if not isinstance(version, str) or not _NODE_VERSION_RE.fullmatch(version):
        raise ValueError("Pinned Node runtime version is invalid")
    _validate_targets(configuration["targets"], version)
    return cast(NodeRuntimeDeclaration, configuration)


def target_archive(configuration: NodeRuntimeDeclaration, target: str) -> dict[str, str]:
    """Resolve the pinned archive for the requested target."""
    target_platform(target)
    row = configuration["targets"][target]
    return {"archive": row["archive"], "sha256": row["sha256"]}


def _require_source_files(source: Path) -> None:
    for name in RUNTIME_FILES:
        path = source / name
        if is_link_or_reparse(path) or not path.is_file():
            raise ValueError(f"Configured agent source is missing a regular {name}")


def validate_agent_source(source: Path, node_version: str) -> None:
    """Validate the agent project and its locked runtime inputs."""
    _require_source_files(source)
    try:
        package: object = json.loads((source / "package.json").read_text(encoding="utf-8"))
        lock: object = json.loads((source / "package-lock.json").read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Configured agent package or lock is invalid") from exc
    if not _is_mapping(package) or package.get("name") != "cadrumo-agent":
        raise ValueError("Configured Node project must be cadrumo-agent")
    if (source / ".node-version").read_text(encoding="utf-8").strip() != node_version:
        raise ValueError("Agent .node-version differs from the pinned Node runtime")
    engines = package.get("engines")
    if not _is_mapping(engines) or engines.get("node") != node_version:
        raise ValueError("Agent package Node engine differs from the pinned runtime")
    dependencies = package.get("dependencies")
    if not _is_mapping(dependencies):
        raise ValueError("Agent package must declare the ACP production dependency")
    _locked_acp_version(dependencies.get(_ACP_PACKAGE), lock)


def _locked_acp_details(lock: object) -> tuple[object, object]:
    lock_packages = lock.get("packages") if _is_mapping(lock) else None
    lock_root = lock_packages.get("") if _is_mapping(lock_packages) else None
    lock_dependencies = lock_root.get("dependencies") if _is_mapping(lock_root) else None
    entry = lock_packages.get(f"node_modules/{_ACP_PACKAGE}") if _is_mapping(lock_packages) else None
    version = entry.get("version") if _is_mapping(entry) else None
    return lock_dependencies, version


def _locked_acp_version(specification: object, lock: object) -> str:
    """Return the exact ACP adapter version the v3 lock installs for the package's declared spec.

    The package may declare an exact version or a range; the lock's root entry must carry
    the same spec, and the installed version is the lock's exact entry for the adapter.
    """
    lock_dependencies, version = _locked_acp_details(lock)
    if (
        not isinstance(specification, str)
        or not specification.strip()
        or not _is_mapping(lock)
        or lock.get("lockfileVersion") != 3
        or not _is_mapping(lock_dependencies)
        or lock_dependencies.get(_ACP_PACKAGE) != specification
        or not isinstance(version, str)
        or not _NODE_VERSION_RE.fullmatch(version)
    ):
        raise ValueError("Agent ACP production dependency differs from its v3 package lock")
    return version


def _require_runtime_files(runtime: Path) -> None:
    for name in RUNTIME_FILES:
        if not (runtime / name).is_file():
            raise ValueError(f"Agent runtime is missing {name}")


def _validate_payload_layout(runtime: Path, target: str) -> None:
    target_platform(target)
    node_path = runtime / "node" / ("node.exe" if target == "windows-x86-64" else "bin/node")
    if not node_path.is_file() or not (runtime / "node/LICENSE").is_file():
        raise ValueError("Agent runtime is missing its pinned Node executable or license")
    _require_runtime_files(runtime)
    if not (runtime / _ACP_ENTRY).is_file():
        raise ValueError("Agent runtime is missing the locked Claude ACP entry point")
    if not (runtime / "node_modules").is_dir():
        raise ValueError("Agent runtime is missing its locked production dependency closure")
    # Check the complete tree before a recursive package-name scan can encounter a link.
    _directories, files = inventory_runtime(runtime)
    expected_node_files = {"node/LICENSE"}
    expected_node_files.add("node/node.exe" if target == "windows-x86-64" else "node/bin/node")
    if {name for name in files if name.startswith("node/")} != expected_node_files:
        raise ValueError("Agent runtime must contain only the pinned Node executable and license")


def _validate_payload_metadata(runtime: Path, expected_node_version: str) -> str:
    try:
        package: object = json.loads((runtime / "package.json").read_text(encoding="utf-8"))
        lock: object = json.loads((runtime / "package-lock.json").read_text(encoding="utf-8"))
        node_version = (runtime / ".node-version").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Agent runtime package metadata is invalid") from exc
    if not _is_mapping(package) or package.get("name") != "cadrumo-agent":
        raise ValueError("Agent runtime package identity is invalid")
    engines = package.get("engines")
    if node_version != expected_node_version or not _is_mapping(engines):
        raise ValueError("Agent runtime Node pin differs from the declared runtime")
    if engines.get("node") != expected_node_version:
        raise ValueError("Agent runtime package engine differs from the declared Node pin")
    dependencies = package.get("dependencies")
    if not _is_mapping(dependencies):
        raise ValueError("Agent runtime must declare the ACP production dependency")
    try:
        acp_version = _locked_acp_version(dependencies.get(_ACP_PACKAGE), lock)
    except ValueError as exc:
        raise ValueError("Agent runtime ACP dependency differs from its package lock") from exc
    return acp_version


def _validate_installed_acp(runtime: Path, acp_version: str) -> None:
    acp_package_path = runtime / "node_modules" / "@agentclientprotocol" / "claude-agent-acp" / "package.json"
    if not acp_package_path.is_file():
        raise ValueError("Agent runtime is missing the installed Claude ACP package metadata")
    acp_package = cast(dict[str, object], json.loads(acp_package_path.read_text(encoding="utf-8")))
    acp_bins = acp_package.get("bin")
    if (
        acp_package.get("name") != _ACP_PACKAGE
        or acp_package.get("version") != acp_version
        or not _is_mapping(acp_bins)
        or acp_bins.get("claude-agent-acp") != "dist/index.js"
    ):
        raise ValueError("Installed Claude ACP package differs from the locked entry point")


def _reject_sdk_platform_clis(runtime: Path) -> None:
    for path in (runtime / "node_modules").rglob("*"):
        parts = path.relative_to(runtime / "node_modules").parts
        for index in range(len(parts) - 1):
            if parts[index].casefold() == "@anthropic-ai" and parts[index + 1].casefold().startswith(_SDK_CLI_PREFIX):
                raise ValueError("Agent runtime contains a forbidden Claude SDK platform CLI payload")


def validate_runtime_payload(runtime: Path, target: str, configuration: NodeRuntimeDeclaration) -> None:
    """Validate the complete pinned runtime and its installed dependency closure."""
    _validate_payload_layout(runtime, target)
    acp_version = _validate_payload_metadata(runtime, configuration["node_version"])
    _validate_installed_acp(runtime, acp_version)
    _reject_sdk_platform_clis(runtime)


def make_receipt(runtime: Path, target: str, archive_record: dict[str, str], node_version: str) -> AgentRuntimeReceipt:
    """Record the verified runtime tree and its pinned inputs."""
    directories, files = inventory_runtime(runtime)
    return {
        "schema_version": 1,
        "target": target,
        "node_version": node_version,
        "node_archive": archive_record["archive"],
        "node_archive_sha256": archive_record["sha256"],
        "package_lock_sha256": files["package-lock.json"],
        "directories": directories,
        "files": files,
    }
