"""Download and safely extract pinned Node archives."""

from __future__ import annotations

import shutil
import stat
import tarfile
import zipfile
from pathlib import Path

import httpx

from .hashing import digest

_MAX_NODE_ARCHIVE_BYTES = 512 * 1024 * 1024
_MAX_NODE_ARCHIVE_EXPANSION_BYTES = 1024 * 1024 * 1024
_MAX_NODE_ARCHIVE_MEMBERS = 100_000
_MAX_NODE_EXECUTABLE_BYTES = 256 * 1024 * 1024
_MAX_NODE_LICENSE_BYTES = 4 * 1024 * 1024
NODE_TARGETS = {
    "windows-x86-64": ("win-x64", "zip"),
    "linux-x86-64": ("linux-x64", "tar.xz"),
    "linux-aarch64": ("linux-arm64", "tar.xz"),
    "macos-arm64": ("darwin-arm64", "tar.gz"),
}


def download_node_archive(archive: Path, version: str, record: dict[str, str]) -> None:
    """Download and verify the exact pinned official archive."""
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


def install_node_archive(
    archive: Path, destination: Path, target: str, record: dict[str, str], node_version: str
) -> None:
    """Install only the pinned Node executable and license."""
    suffix, _extension = NODE_TARGETS[target]
    archive_root = f"node-v{node_version}-{suffix}"
    node_member = f"{archive_root}/node.exe" if target == "windows-x86-64" else f"{archive_root}/bin/node"
    license_member = f"{archive_root}/LICENSE"
    if record["archive"].endswith(".zip"):
        _install_node_from_zip(archive, destination, node_member, license_member)
    else:
        _install_node_from_tar(archive, destination, node_member, license_member)


def _select_zip_members(
    members: list[zipfile.ZipInfo], node_member: str, license_member: str
) -> dict[str, zipfile.ZipInfo]:
    selected: dict[str, zipfile.ZipInfo] = {}
    for item in members:
        if item.orig_filename not in {node_member, license_member}:
            continue
        kind = stat.S_IFMT(item.external_attr >> 16)
        maximum = _MAX_NODE_EXECUTABLE_BYTES if item.orig_filename == node_member else _MAX_NODE_LICENSE_BYTES
        if item.orig_filename in selected or item.is_dir() or kind not in {0, stat.S_IFREG} or item.file_size > maximum:
            raise ValueError("Node runtime ZIP expected members must be bounded regular files")
        selected[item.orig_filename] = item
    if set(selected) != {node_member, license_member}:
        raise ValueError("Node runtime ZIP is missing an expected regular file")
    return selected


def _install_node_from_zip(archive: Path, destination: Path, node_member: str, license_member: str) -> None:
    with zipfile.ZipFile(archive) as bundle:
        members = bundle.infolist()
        if (
            len(members) > _MAX_NODE_ARCHIVE_MEMBERS
            or sum(item.file_size for item in members) > _MAX_NODE_ARCHIVE_EXPANSION_BYTES
        ):
            raise ValueError("Node runtime ZIP exceeds the archive expansion limit")
        selected = _select_zip_members(members, node_member, license_member)
        for name in (node_member, license_member):
            target = destination / ("node.exe" if name == node_member else "LICENSE")
            target.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(selected[name]) as incoming, target.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)


def _select_tar_members(bundle: tarfile.TarFile, node_member: str, license_member: str) -> dict[str, tarfile.TarInfo]:
    selected: dict[str, tarfile.TarInfo] = {}
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
    return selected


def _install_node_from_tar(archive: Path, destination: Path, node_member: str, license_member: str) -> None:
    with tarfile.open(archive, mode="r:*") as bundle:
        selected = _select_tar_members(bundle, node_member, license_member)
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
