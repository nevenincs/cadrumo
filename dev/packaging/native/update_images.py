"""Update CMake-built native images without rebuilding the staged Python payload."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import os
import shutil
import tempfile
from pathlib import Path

from packaging.utils import canonicalize_name
from pydantic import JsonValue, TypeAdapter

from .assemble import image_artifact, named_application_images
from .build_paths import build_paths
from .hashing import digest
from .layout import bundled_image_files, entrypoint_files, load_layout
from .process_quiescence import quiesce
from .service_descriptors import refresh_service_image_digests, stage_service_descriptors


def publish(path: Path, document: dict[str, JsonValue]) -> None:
    """Publish complete metadata; retain the previous manifest on write failure."""
    content = json.dumps(document, indent=2).encode("utf-8")
    if path.is_file() and path.read_bytes() == content:
        return
    descriptor, temporary = tempfile.mkstemp(prefix=".native-update-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def recover(root: Path, contract: dict[str, JsonValue], artifacts: dict[str, Path]) -> dict[str, JsonValue]:
    """Inventory a locally interrupted stage, explicitly retaining recovery provenance.

    This does not recreate release provenance or rebuild/copy Python. Full release
    assembly remains responsible for its wheel and relocation receipts.
    """
    strings = TypeAdapter(dict[str, str])
    files = strings.validate_python(contract["files"], strict=True)
    layout = strings.validate_python(contract["paths"], strict=True)
    user_docs = TypeAdapter(dict[str, JsonValue]).validate_python(contract["user_docs"], strict=True)
    docs_directory = TypeAdapter(str).validate_python(user_docs["directory"], strict=True)
    build = TypeAdapter(dict[str, JsonValue]).validate_json((root / files["build_metadata"]).read_bytes(), strict=True)
    native = TypeAdapter(dict[str, JsonValue]).validate_json(
        (root / files["native_manifest"]).read_bytes(), strict=True
    )
    if build["layout_abi"] != contract["abi"]:
        raise ValueError("Staged layout ABI differs from the configured contract")
    for member in strings.validate_python(native["modules"], strict=True).values():
        path = root / member
        if not path.resolve(strict=True).is_relative_to(root) or not path.is_file():
            raise ValueError(f"Staged native module is unavailable: {member}")
    distributions = {
        canonicalize_name(dist.metadata["Name"]): dist.version
        for dist in importlib.metadata.distributions(path=[str(root / layout["packages"])])
    }
    if distributions.get("cadrumo") != build["version"] or "cadrumo-agent" not in distributions:
        raise ValueError("Staged application distribution metadata is incomplete")
    startup = [
        layout["executable"],
        *entrypoint_files(contract).values(),
        *bundled_image_files(contract).values(),
        *(image.package_path for image in named_application_images(contract, artifacts) if image.startup),
        layout["stdlib"],
        files["path_file"],
        files["build_metadata"],
        files["native_manifest"],
        f"{layout['native']}/{files['bridge']}",
        f"{layout['native']}/{files['runtime']}",
    ]
    startup.append(stage_service_descriptors(root, contract, named_application_images(contract, artifacts)))
    for member in startup:
        if not (root / member).is_file():
            raise ValueError(f"Staged startup file is missing: {member}")
    inventory = {}
    manifest_name = files["package_manifest"]
    for path in root.rglob("*"):
        if path.is_symlink() or path.is_junction():
            raise ValueError(f"Linked member in interrupted stage: {path}")
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative != manifest_name:
                inventory[relative] = digest(path)
    docs = f"{layout['docs']}/{docs_directory}"
    if (root / docs).exists():
        raise ValueError("Interrupted documentation inventory requires normal release assembly")
    return TypeAdapter(dict[str, JsonValue]).validate_python(
        {
            "kind": "application",
            "build": build,
            "layout": contract,
            "python": build["python"],
            "distributions": distributions,
            "startup_files": startup,
            "files": inventory,
            "delegated_inventories": {},
            "user_docs": {"directory": docs, "bundled": False},
            "recovery": {"source": "existing-staged-payload", "release_provenance_available": False},
        },
        strict=True,
    )


def update(build: Path, config: str, artifacts: dict[str, Path], *, recovery: bool = False) -> None:
    """Replace changed native images and update only their inventory entries."""
    build = build.resolve(strict=True)
    paths = build_paths(build)
    target = json.loads((paths["generated"] / "identity.json").read_text(encoding="utf-8"))["target"]
    contract = load_layout(target)
    root = (paths["stage"] / config / "app").resolve(strict=True)
    if not root.is_relative_to(build):
        raise ValueError("Package must belong to this CMake binary directory")
    manifest_path = root / contract["files"]["package_manifest"]
    images = named_application_images(contract, artifacts)
    if set(artifacts) != {image.file for image in images}:
        raise ValueError("Undeclared native image")
    replacements = {}
    for image in images:
        source = artifacts[image.file].resolve(strict=True)
        destination = root / image.package_path
        if not source.is_relative_to(build) or not destination.resolve().is_relative_to(root):
            raise ValueError("Native image escapes its CMake package")
        replacements[image.package_path] = source
    # C/interpreter hosts are also native outputs, not Python source payloads.
    for member in [
        contract["paths"]["executable"],
        *entrypoint_files(contract).values(),
        *bundled_image_files(contract).values(),
        f"{contract['paths']['native']}/{contract['files']['bridge']}",
    ]:
        source = paths["bin"] / config / Path(member).name
        if source.is_file():
            replacements[member] = source
    if manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest["layout"] != contract:
            raise ValueError("Native update cannot change the packaged layout")
    elif recovery:
        manifest = recover(root, contract, artifacts)
    else:
        raise ValueError("Package manifest missing; explicitly recover the interrupted stage first")
    inventory = TypeAdapter(dict[str, JsonValue]).validate_python(manifest["files"], strict=True)
    manifest["files"] = inventory
    descriptor_member = contract["files"]["service_descriptors"]
    if inventory.get(descriptor_member) != digest(root / descriptor_member):
        raise ValueError("Staged service descriptors differ from the package manifest")
    changed = {
        member: (source, digest(source))
        for member, source in replacements.items()
        if not (root / member).is_file() or digest(source) != digest(root / member)
    }
    if changed:
        quiesce(build, target)
        for member, (source, expected) in changed.items():
            shutil.copy2(source, root / member)
            inventory[member] = expected
    for member, source in replacements.items():
        inventory[member] = digest(source)
    if changed:
        refresh_service_image_digests(root, descriptor_member)
        inventory[descriptor_member] = digest(root / descriptor_member)
    publish(manifest_path, manifest)
    print(f"Native images updated: {len(changed)}; Python payload preserved", flush=True)


def main() -> None:
    """Run the native-only CMake staging or explicit local recovery action."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--config", choices=("Debug", "Release"), required=True)
    parser.add_argument("--image", action="append", default=[])
    parser.add_argument("--recover", action="store_true")
    args = parser.parse_args()
    update(args.build, args.config, dict(image_artifact(value) for value in args.image), recovery=args.recover)


if __name__ == "__main__":
    main()
