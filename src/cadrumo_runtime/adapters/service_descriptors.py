"""Load and validate package-owned installed service descriptors."""

from __future__ import annotations

import json
import sys
from pathlib import Path, PurePosixPath
from typing import cast

from cadrumo.core.hashing import canonical_json_bytes, reject_duplicate_json_members, reject_json_constant, sha256_hex
from cadrumo.core.link_safety import is_link_like
from cadrumo.core.path_confinement import HostPathRefusal, opened_confined_file
from cadrumo_client.contracts.service_access import InstalledServiceDescriptor

from .boot_record import runtime_package_directory

_MAXIMUM_PACKAGE_MANIFEST_BYTES = 16 * 1024 * 1024
_MAXIMUM_SERVICE_DESCRIPTOR_BYTES = 1024 * 1024


def _capabilities_valid(document: dict[str, object]) -> bool:
    raw_records = document.get("record_capabilities")
    if type(raw_records) is not list:
        return False
    capabilities: list[str] = []
    for raw_record in cast(list[object], raw_records):
        if type(raw_record) is not dict:
            return False
        record = cast(dict[str, object], raw_record)
        capability = record.get("capability")
        if type(capability) is not str:
            return False
        capabilities.append(capability)
    return len(capabilities) == len(set(capabilities))


def _resolve_parents(root: Path, files: dict[object, object], document: dict[str, object]) -> bool:
    parents = document.get("allowed_parent_images", [])
    if type(parents) is not list:
        return False
    for raw_parent in cast(list[object], parents):
        if type(raw_parent) is not dict:
            return False
        parent = cast(dict[str, object], raw_parent)
        parent_path = package_member_path(root, parent.get("launch_image"))
        if parent_path is None:
            return False
        _parent_image, resolved_parent = parent_path
        if files.get(parent.get("launch_image")) != parent.get("image_digest"):
            return False
        parent["launch_image"] = str(resolved_parent)
    return True


def _descriptor_digest_valid(document: dict[str, object]) -> bool:
    digest_document = {key: value for key, value in document.items() if key != "descriptor_digest"}
    return sha256_hex(canonical_json_bytes(digest_document)) == document["descriptor_digest"]


def _descriptor(
    root: Path, files: dict[object, object], item: object, service_ids: set[str]
) -> InstalledServiceDescriptor | None:
    if type(item) is not dict:
        return None
    document = dict(cast(dict[str, object], item))
    if not _descriptor_digest_valid(document):
        return None
    service_id = document["service_id"]
    if type(service_id) is not str or service_id in service_ids:
        return None
    service_ids.add(service_id)
    if not _capabilities_valid(document):
        return None
    launch_image = package_member_path(root, document.get("launch_image"))
    if launch_image is None:
        return None
    _image, resolved_image = launch_image
    if files.get(document["launch_image"]) != document["image_digest"]:
        return None
    document["launch_image"] = str(resolved_image)
    if not _resolve_parents(root, files, document):
        return None
    return InstalledServiceDescriptor.model_validate_json(canonical_json_bytes(document))


def _package_root() -> Path | None:
    package = runtime_package_directory(Path(sys.executable))
    if package is None:
        return None
    root = Path(package)
    if any(is_link_like(part) for part in (root, *root.parents)):
        return None
    try:
        root = root.resolve(strict=True)
    except OSError:
        return None
    return root


def installed_service_descriptors() -> tuple[InstalledServiceDescriptor, ...]:
    """Load package-owned capabilities, with image identity fixed by package inventory."""
    root = _package_root()
    if root is None:
        return ()
    path = root / "data" / "service-descriptors.json"
    try:
        manifest_raw = _read_package_member(
            root / "data" / "package-manifest.json", root=root, maximum_bytes=_MAXIMUM_PACKAGE_MANIFEST_BYTES
        )
        raw = _read_package_member(path, root=root, maximum_bytes=_MAXIMUM_SERVICE_DESCRIPTOR_BYTES)
        manifest: object = json.loads(
            manifest_raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        if type(manifest) is not dict:
            return ()
        manifest_object = cast(dict[str, object], manifest)
        raw_files = manifest_object.get("files")
        if type(raw_files) is not dict:
            return ()
        files = cast(dict[object, object], raw_files)
        expected = files.get("data/service-descriptors.json")
        if type(expected) is not str or sha256_hex(raw) != expected:
            return ()
        documents: object = json.loads(
            raw, object_pairs_hook=reject_duplicate_json_members, parse_constant=reject_json_constant
        )
        if type(documents) is not list:
            return ()
        descriptors: list[InstalledServiceDescriptor] = []
        service_ids: set[str] = set()
        for item in cast(list[object], documents):
            descriptor = _descriptor(root, files, item, service_ids)
            if descriptor is None:
                return ()
            descriptors.append(descriptor)
        return tuple(descriptors)
    except (OSError, ValueError, TypeError, KeyError):
        return ()


def _read_package_member(path: Path, *, root: Path, maximum_bytes: int) -> bytes:
    with opened_confined_file(path, max_bytes=maximum_bytes, root=root) as opened:
        if isinstance(opened, HostPathRefusal):
            raise ValueError("package member is not a confined regular file")
        payload = opened.read_bytes()
    if isinstance(payload, HostPathRefusal):
        raise ValueError("package member exceeds its byte bound")
    return payload


def _package_relative(member: object) -> PurePosixPath | None:
    if type(member) is not str or not member or "\\" in member:
        return None
    relative = PurePosixPath(member)
    if relative.is_absolute() or relative.as_posix() != member or any(part in {".", ".."} for part in relative.parts):
        return None
    return relative


def package_member_path(root: Path, member: object) -> tuple[Path, Path] | None:
    """Resolve an exact confined package member, rejecting links."""
    relative = _package_relative(member)
    if relative is None:
        return None
    path = root.joinpath(*relative.parts)
    if any(is_link_like(part) for part in (path, *path.parents)):
        return None
    try:
        resolved = path.resolve(strict=True)
    except OSError:
        return None
    if not resolved.is_relative_to(root):
        return None
    return path, resolved
