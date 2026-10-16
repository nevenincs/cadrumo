"""Build and stage the pinned Node/ACP runtime used by cadrumo-agent."""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tarfile
import tempfile
import zipfile
from collections.abc import Callable
from pathlib import Path, PurePosixPath
from typing import Any

import httpx

from dev._paths import REPO_ROOT

from ..command_execution import run_command
from ..runtime_wheelhouse_contract import SUPPORTED_TARGETS, target_platform
from .hashing import digest

_RUNTIME_CONFIG = REPO_ROOT / "native/agent/runtime.json"
_MAX_NODE_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_NODE_ARCHIVE_EXPANSION_BYTES = 1024 * 1024 * 1024
_MAX_NODE_ARCHIVE_MEMBERS = 100_000
_MAX_NODE_EXECUTABLE_BYTES = 256 * 1024 * 1024
_MAX_NODE_LICENSE_BYTES = 4 * 1024 * 1024
_ACP_PACKAGE = "@agentclientprotocol/claude-agent-acp"
_ACP_ENTRY = PurePosixPath("node_modules/@agentclientprotocol/claude-agent-acp/dist/index.js")
_SDK_CLI_PREFIX = "claude-agent-sdk-"
_RECEIPT_NAME = "runtime-receipt.json"
_STAGED_RECEIPT_NAME = "agent-runtime.json"
_STAGED_NAMES = (
    "node",
    "node_modules",
    "package.json",
    "package-lock.json",
    ".node-version",
    _STAGED_RECEIPT_NAME,
)
_NODE_TARGETS = {
    "windows-x86-64": ("win-x64", "zip"),
    "linux-x86-64": ("linux-x64", "tar.xz"),
    "linux-aarch64": ("linux-arm64", "tar.xz"),
    "macos-arm64": ("darwin-arm64", "tar.gz"),
}
_RUNTIME_FILES = ("package.json", "package-lock.json", ".node-version")
_NODE_VERSION_RE = re.compile(r"[0-9]+\.[0-9]+\.[0-9]+")
_SHA256_RE = re.compile(r"[0-9a-f]{64}")
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)


def build_agent_runtime(output: Path, source: Path, target: str, *, node: Path, npm_cli: Path) -> None:
    """Build an isolated, production-only Node/ACP tree from the configured agent source."""
    configuration = _load_configuration()
    archive_record = _target_archive(configuration, target)
    source = source.resolve(strict=True)
    if not source.is_dir():
        raise ValueError("Configured agent source must be a directory")
    _validate_agent_source(source, configuration["node_version"])
    node = node.resolve(strict=True)
    npm_cli = npm_cli.resolve(strict=True)
    if not node.is_file() or not npm_cli.is_file():
        raise ValueError("Configured Node and npm CLI must be regular files")

    output_parent = output.parent.resolve()
    output_parent.mkdir(parents=True, exist_ok=True)
    output = output_parent / output.name
    if output == source or output.is_relative_to(source):
        raise ValueError("Agent runtime output must be outside the agent source tree")
    if _lstat(output) is not None:
        if _is_link_or_reparse(output) or not output.is_dir():
            raise ValueError("Agent runtime output must be a regular directory")
        try:
            prior = verify_agent_runtime(output)
        except ValueError:
            prior = None
        if (
            prior is not None
            and prior["target"] == target
            and all(prior["files"].get(name) == digest(source / name) for name in _RUNTIME_FILES)
        ):
            return

    with tempfile.TemporaryDirectory(prefix=".agent-runtime-", dir=output_parent) as temporary:
        work = Path(temporary)
        runtime = work / "runtime"
        runtime.mkdir()
        for name in _RUNTIME_FILES:
            shutil.copyfile(source / name, runtime / name)
        (runtime / "node").mkdir()

        archive_path = work / archive_record["archive"]
        _download_node_archive(archive_path, configuration["node_version"], archive_record)
        _install_node_archive(archive_path, runtime / "node", target, archive_record)

        node_version = configuration["node_version"]
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

        _validate_runtime_payload(runtime, target, configuration)
        receipt = _make_receipt(runtime, target, archive_record, node_version)
        (runtime / _RECEIPT_NAME).write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        verify_agent_runtime(runtime)
        previous = work / "previous"
        if output.exists():
            output.rename(previous)
        try:
            runtime.rename(output)
        except BaseException:
            if previous.exists():
                previous.rename(output)
            raise


def verify_agent_runtime(source: Path) -> dict[str, Any]:
    """Verify a build receipt against the exact runtime tree and return that receipt."""
    if _lstat(source) is None or _is_link_or_reparse(source) or not source.is_dir():
        raise ValueError("Agent runtime source must be a regular directory")
    source = source.resolve(strict=True)
    receipt_path = source / _RECEIPT_NAME
    if _is_link_or_reparse(receipt_path) or not receipt_path.is_file():
        raise ValueError("Agent runtime receipt is missing or is not a regular file")
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Agent runtime receipt is invalid") from exc
    if not isinstance(receipt, dict) or set(receipt) != {
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
    target = receipt["target"]
    if not isinstance(target, str):
        raise ValueError("Agent runtime receipt target is invalid")
    configuration = _load_configuration()
    archive_record = _target_archive(configuration, target)
    if (
        receipt["node_version"] != configuration["node_version"]
        or receipt["node_archive"] != archive_record["archive"]
        or receipt["node_archive_sha256"] != archive_record["sha256"]
    ):
        raise ValueError("Agent runtime receipt differs from the pinned target declaration")

    directories = receipt["directories"]
    files = receipt["files"]
    if not isinstance(directories, list) or not all(isinstance(item, str) for item in directories):
        raise ValueError("Agent runtime receipt directory inventory is invalid")
    if not isinstance(files, dict) or not all(
        isinstance(name, str) and isinstance(value, str) and _SHA256_RE.fullmatch(value)
        for name, value in files.items()
    ):
        raise ValueError("Agent runtime receipt file inventory is invalid")
    for name in [*directories, *files]:
        _validate_relative_name(name)
    if _RECEIPT_NAME in files:
        raise ValueError("Agent runtime receipt cannot hash itself")

    actual_directories, actual_files = _inventory(source)
    if actual_directories != directories or actual_files != files:
        raise ValueError("Agent runtime tree differs from its receipt")
    if receipt["package_lock_sha256"] != files.get("package-lock.json"):
        raise ValueError("Agent runtime receipt lock digest is inconsistent")
    _validate_runtime_payload(source, target, configuration)
    return receipt


def stage_agent_runtime(
    source: Path, destination: Path, *, copy_function: Callable[[Path, Path], object] = shutil.copyfile
) -> None:
    """Copy a verified runtime into the installed ``app/cadrumo`` package root."""
    verify_agent_runtime(source)
    destination_parent = destination.parent.resolve()
    destination_parent.mkdir(parents=True, exist_ok=True)
    destination = destination_parent / destination.name
    if _is_link_or_reparse(destination):
        raise ValueError("Agent runtime destination cannot be a link or junction")
    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve(strict=True)
    if os.path.normcase(os.path.abspath(destination)) != os.path.normcase(str(resolved_destination)):
        raise ValueError("Agent runtime destination escapes through a link or junction")

    collisions = [name for name in _STAGED_NAMES if _lstat(destination / name) is not None]
    if collisions:
        raise ValueError(f"Agent runtime destination already contains owned paths: {', '.join(collisions)}")

    source = source.resolve(strict=True)
    for name in ("node", "node_modules"):
        shutil.copytree(
            source / name,
            destination / name,
            symlinks=False,
            copy_function=lambda src, dst: copy_function(Path(src), Path(dst)),
        )
    for name in _RUNTIME_FILES:
        copy_function(source / name, destination / name)
    copy_function(source / _RECEIPT_NAME, destination / _STAGED_RECEIPT_NAME)


def _load_configuration() -> dict[str, Any]:
    try:
        configuration = json.loads(_RUNTIME_CONFIG.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Pinned agent runtime declaration is invalid") from exc
    if not isinstance(configuration, dict) or set(configuration) != {"schema_version", "node_version", "targets"}:
        raise ValueError("Pinned agent runtime declaration has an unsupported shape")
    if type(configuration["schema_version"]) is not int or configuration["schema_version"] != 1:
        raise ValueError("Pinned agent runtime declaration schema is unsupported")
    version = configuration["node_version"]
    if not isinstance(version, str) or not _NODE_VERSION_RE.fullmatch(version):
        raise ValueError("Pinned Node runtime version is invalid")
    targets = configuration["targets"]
    expected_targets = {item.name for item in SUPPORTED_TARGETS}
    if not isinstance(targets, dict) or set(targets) != expected_targets or expected_targets != set(_NODE_TARGETS):
        raise ValueError("Pinned agent runtime targets do not match supported package targets")
    for target, row in targets.items():
        suffix, extension = _NODE_TARGETS[target]
        expected_archive = f"node-v{version}-{suffix}.{extension}"
        if (
            not isinstance(row, dict)
            or set(row) != {"archive", "sha256"}
            or row["archive"] != expected_archive
            or not isinstance(row["sha256"], str)
            or not _SHA256_RE.fullmatch(row["sha256"])
        ):
            raise ValueError(f"Pinned Node archive declaration is invalid for {target}")
    return configuration


def _target_archive(configuration: dict[str, Any], target: str) -> dict[str, str]:
    target_platform(target)
    row = configuration["targets"][target]
    return {"archive": row["archive"], "sha256": row["sha256"]}


def _validate_agent_source(source: Path, node_version: str) -> None:
    for name in _RUNTIME_FILES:
        path = source / name
        if _is_link_or_reparse(path) or not path.is_file():
            raise ValueError(f"Configured agent source is missing a regular {name}")
    try:
        package = json.loads((source / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((source / "package-lock.json").read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Configured agent package or lock is invalid") from exc
    if not isinstance(package, dict) or package.get("name") != "cadrumo-agent":
        raise ValueError("Configured Node project must be cadrumo-agent")
    if (source / ".node-version").read_text(encoding="utf-8").strip() != node_version:
        raise ValueError("Agent .node-version differs from the pinned Node runtime")
    engines = package.get("engines")
    if not isinstance(engines, dict) or engines.get("node") != node_version:
        raise ValueError("Agent package Node engine differs from the pinned runtime")
    dependencies = package.get("dependencies")
    if not isinstance(dependencies, dict):
        raise ValueError("Agent package must declare the ACP production dependency")
    acp_version = dependencies.get(_ACP_PACKAGE)
    lock_packages = lock.get("packages") if isinstance(lock, dict) else None
    lock_root = lock_packages.get("") if isinstance(lock_packages, dict) else None
    lock_dependencies = lock_root.get("dependencies") if isinstance(lock_root, dict) else None
    if (
        not isinstance(acp_version, str)
        or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", acp_version)
        or not isinstance(lock, dict)
        or lock.get("lockfileVersion") != 3
        or not isinstance(lock_dependencies, dict)
        or lock_dependencies.get(_ACP_PACKAGE) != acp_version
    ):
        raise ValueError("Agent ACP production dependency differs from its v3 package lock")


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


def _download_node_archive(archive: Path, version: str, record: dict[str, str]) -> None:
    url = httpx.URL(f"https://nodejs.org/dist/v{version}/{record['archive']}")
    if url.scheme != "https" or url.host != "nodejs.org" or url.port not in {None, 443} or url.userinfo:
        raise ValueError("Node runtime archive must use the pinned official HTTPS origin")
    partial = archive.with_name(archive.name + ".partial")
    try:
        with httpx.stream("GET", url, timeout=120, follow_redirects=False) as response:
            response.raise_for_status()
            content_length = response.headers.get("content-length")
            if content_length is not None and int(content_length) > _MAX_NODE_ARCHIVE_BYTES:
                raise ValueError("Node runtime archive exceeds the download size limit")
            size = 0
            with partial.open("xb") as output:
                for chunk in response.iter_bytes():
                    size += len(chunk)
                    if size > _MAX_NODE_ARCHIVE_BYTES:
                        raise ValueError("Node runtime archive exceeds the download size limit")
                    output.write(chunk)
        partial.rename(archive)
    finally:
        partial.unlink(missing_ok=True)
    if digest(archive) != record["sha256"]:
        archive.unlink(missing_ok=True)
        raise ValueError("Node runtime archive SHA256 mismatch")


def _install_node_archive(archive: Path, destination: Path, target: str, record: dict[str, str]) -> None:
    suffix, _extension = _NODE_TARGETS[target]
    archive_root = f"node-v{_load_configuration()['node_version']}-{suffix}"
    node_member = f"{archive_root}/node.exe" if target == "windows-x86-64" else f"{archive_root}/bin/node"
    license_member = f"{archive_root}/LICENSE"
    if record["archive"].endswith(".zip"):
        _install_node_from_zip(archive, destination, node_member, license_member)
    else:
        _install_node_from_tar(archive, destination, node_member, license_member)


def _install_node_from_zip(archive: Path, destination: Path, node_member: str, license_member: str) -> None:
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if (
            len(members) > _MAX_NODE_ARCHIVE_MEMBERS
            or sum(item.file_size for item in members) > _MAX_NODE_ARCHIVE_EXPANSION_BYTES
        ):
            raise ValueError("Node runtime ZIP exceeds the archive expansion limit")
        selected: dict[str, zipfile.ZipInfo] = {}
        for item in members:
            if item.orig_filename not in {node_member, license_member}:
                continue
            kind = stat.S_IFMT(item.external_attr >> 16)
            maximum = _MAX_NODE_EXECUTABLE_BYTES if item.orig_filename == node_member else _MAX_NODE_LICENSE_BYTES
            if (
                item.orig_filename in selected
                or item.is_dir()
                or kind not in {0, stat.S_IFREG}
                or item.file_size > maximum
            ):
                raise ValueError("Node runtime ZIP expected members must be bounded regular files")
            selected[item.orig_filename] = item
        if set(selected) != {node_member, license_member}:
            raise ValueError("Node runtime ZIP is missing an expected regular file")
        for name in (node_member, license_member):
            target = destination / ("node.exe" if name == node_member else "LICENSE")
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(selected[name]) as incoming, target.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)


def _install_node_from_tar(archive: Path, destination: Path, node_member: str, license_member: str) -> None:
    selected: dict[str, tarfile.TarInfo] = {}
    with tarfile.open(archive, mode="r:*") as bundle:
        for index, member in enumerate(bundle):
            if index >= _MAX_NODE_ARCHIVE_MEMBERS:
                raise ValueError("Node runtime tar archive exceeds the member limit")
            if member.name not in {node_member, license_member}:
                continue
            if member.name in selected or not member.isfile():
                raise ValueError("Node runtime tar archive expected members must be regular files")
            maximum = _MAX_NODE_EXECUTABLE_BYTES if member.name == node_member else _MAX_NODE_LICENSE_BYTES
            if member.size < 0 or member.size > maximum:
                raise ValueError("Node runtime tar archive member exceeds the size limit")
            selected[member.name] = member
        if set(selected) != {node_member, license_member}:
            raise ValueError("Node runtime tar archive is missing an expected regular file")
        for member_name in (node_member, license_member):
            source = bundle.extractfile(selected[member_name])
            if source is None:
                raise ValueError("Node runtime tar archive member cannot be read")
            target = destination / "bin/node" if member_name == node_member else destination / "LICENSE"
            target.parent.mkdir(parents=True, exist_ok=True)
            with source, target.open("xb") as output:
                shutil.copyfileobj(source, output)
            if member_name == node_member:
                target.chmod(0o755)


def _validate_runtime_payload(runtime: Path, target: str, configuration: dict[str, Any]) -> None:
    target_platform(target)
    node_path = runtime / "node" / ("node.exe" if target == "windows-x86-64" else "bin/node")
    if not node_path.is_file() or not (runtime / "node/LICENSE").is_file():
        raise ValueError("Agent runtime is missing its pinned Node executable or license")
    for name in _RUNTIME_FILES:
        if not (runtime / name).is_file():
            raise ValueError(f"Agent runtime is missing {name}")
    if not (runtime / _ACP_ENTRY).is_file():
        raise ValueError("Agent runtime is missing the locked Claude ACP entry point")
    if not (runtime / "node_modules").is_dir():
        raise ValueError("Agent runtime is missing its locked production dependency closure")
    # Check the complete tree before a recursive package-name scan can encounter a link.
    _directories, files = _inventory(runtime)
    expected_node_files = {"node/LICENSE"}
    expected_node_files.add("node/node.exe" if target == "windows-x86-64" else "node/bin/node")
    if {name for name in files if name.startswith("node/")} != expected_node_files:
        raise ValueError("Agent runtime must contain only the pinned Node executable and license")

    try:
        package = json.loads((runtime / "package.json").read_text(encoding="utf-8"))
        lock = json.loads((runtime / "package-lock.json").read_text(encoding="utf-8"))
        node_version = (runtime / ".node-version").read_text(encoding="utf-8").strip()
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Agent runtime package metadata is invalid") from exc
    if not isinstance(package, dict) or package.get("name") != "cadrumo-agent":
        raise ValueError("Agent runtime package identity is invalid")
    engines = package.get("engines")
    if node_version != configuration["node_version"] or not isinstance(engines, dict):
        raise ValueError("Agent runtime Node pin differs from the declared runtime")
    if engines.get("node") != configuration["node_version"]:
        raise ValueError("Agent runtime package engine differs from the declared Node pin")
    dependencies = package.get("dependencies")
    if not isinstance(dependencies, dict):
        raise ValueError("Agent runtime must declare the ACP production dependency")
    acp_version = dependencies.get(_ACP_PACKAGE)
    lock_packages = lock.get("packages") if isinstance(lock, dict) else None
    lock_root = lock_packages.get("") if isinstance(lock_packages, dict) else None
    lock_dependencies = lock_root.get("dependencies") if isinstance(lock_root, dict) else None
    if (
        not isinstance(acp_version, str)
        or not isinstance(lock, dict)
        or lock.get("lockfileVersion") != 3
        or not isinstance(lock_dependencies, dict)
        or lock_dependencies.get(_ACP_PACKAGE) != acp_version
    ):
        raise ValueError("Agent runtime ACP dependency differs from its package lock")
    acp_package_path = runtime / "node_modules" / "@agentclientprotocol" / "claude-agent-acp" / "package.json"
    if not acp_package_path.is_file():
        raise ValueError("Agent runtime is missing the installed Claude ACP package metadata")
    acp_package = json.loads(acp_package_path.read_text(encoding="utf-8"))
    acp_bins = acp_package.get("bin")
    if (
        acp_package.get("name") != _ACP_PACKAGE
        or acp_package.get("version") != acp_version
        or not isinstance(acp_bins, dict)
        or acp_bins.get("claude-agent-acp") != "dist/index.js"
    ):
        raise ValueError("Installed Claude ACP package differs from the locked entry point")
    for path in (runtime / "node_modules").rglob("*"):
        parts = path.relative_to(runtime / "node_modules").parts
        for index in range(len(parts) - 1):
            if parts[index].casefold() == "@anthropic-ai" and parts[index + 1].casefold().startswith(_SDK_CLI_PREFIX):
                raise ValueError("Agent runtime contains a forbidden Claude SDK platform CLI payload")


def _make_receipt(runtime: Path, target: str, archive_record: dict[str, str], node_version: str) -> dict[str, Any]:
    directories, files = _inventory(runtime)
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


def _inventory(root: Path) -> tuple[list[str], dict[str, str]]:
    directories: list[str] = []
    files: dict[str, str] = {}
    stack = [root]
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda item: item.name)
        except OSError as exc:
            raise ValueError("Agent runtime tree cannot be enumerated") from exc
        child_directories: list[Path] = []
        for entry in entries:
            path = Path(entry.path)
            if _is_link_or_reparse(path):
                raise ValueError("Agent runtime tree cannot contain links or junctions")
            relative = path.relative_to(root).as_posix()
            _validate_relative_name(relative)
            if entry.is_dir(follow_symlinks=False):
                directories.append(relative)
                child_directories.append(path)
            elif entry.is_file(follow_symlinks=False):
                if relative != _RECEIPT_NAME:
                    files[relative] = digest(path)
            else:
                raise ValueError("Agent runtime tree cannot contain special files")
        stack.extend(reversed(child_directories))
    return sorted(directories), dict(sorted(files.items()))


def _validate_relative_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name
        or path.is_absolute()
        or "\\" in name
        or ":" in name
        or "\x00" in name
        or any(part in {"", ".", ".."} for part in name.split("/"))
        or path.as_posix() != name
    ):
        raise ValueError("Agent runtime receipt contains an invalid relative path")


def _lstat(path: Path) -> os.stat_result | None:
    try:
        return path.lstat()
    except FileNotFoundError:
        return None


def _is_link_or_reparse(path: Path) -> bool:
    info = _lstat(path)
    return info is not None and (
        stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & _REPARSE_POINT)
    )
