"""Shared POSIX native inventory and relocation; target loaders own binary edits."""

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import sys
import tarfile
import tempfile
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import httpx

from cadrumo.core.storage_environment import STORAGE_ROOT

from ...command_execution import run_command
from ...runtime_wheelhouse_contract import SUPPORTED_TARGETS
from ..hashing import digest
from .posix_sdk_download import download_sdk

# These inputs describe assembly on the builder, rather than shipped runtime paths.
# Preserve every other contract field until the common manifest owns that projection.
_BUILD_LAYOUT_FIELDS = frozenset({"native_tools", "native_signing_identity"})


def _validate_decoder_provenance(decoder: dict[str, object]) -> None:
    provenance = decoder.get("provenance")
    if not isinstance(provenance, dict) or any(
        not isinstance(cast(dict[str, object], provenance).get(field), str)
        or not cast(dict[str, object], provenance)[field]
        for field in ("provider", "release", "source", "source_sha256")
    ):
        raise ValueError("SDK archive decoder requires source provenance")
    provenance = cast(dict[str, str], provenance)
    if not re.fullmatch(r"[0-9a-f]{64}", provenance["source_sha256"]):
        raise ValueError("SDK archive decoder requires an exact source SHA256")
    source = httpx.URL(provenance["source"])
    if source.scheme != "https" or source.userinfo:
        raise ValueError("SDK archive decoder source requires HTTPS without credentials")


def _archive_decoder(tools: Mapping[str, object]) -> tuple[Path, dict[str, object]]:
    """Admit an explicit, hash-pinned build tool without discovering a host decoder."""
    decoder = tools.get("cpython_archive_decoder")
    if not isinstance(decoder, dict):
        raise ValueError("tar.zst SDK requires an explicit pinned build-only archive decoder")
    decoder = cast(dict[str, object], decoder)
    _validate_decoder_provenance(decoder)
    executable = Path(str(decoder.get("executable", "")))
    if not executable.is_absolute() or not executable.is_file() or digest(executable) != decoder.get("sha256"):
        raise ValueError("SDK archive decoder must be an existing absolute hash-pinned executable")
    return executable, decoder


def _sdk_source(
    pin: str, tools: Mapping[str, object], contract: Mapping[str, object]
) -> tuple[dict[str, object], str, str, tuple[Path, dict[str, object]] | None]:
    provenance = tools.get("cpython_provenance")
    if not isinstance(provenance, dict) or cast(dict[str, object], provenance).get("version") != pin:
        raise ValueError("POSIX CPython SDK needs reviewed provenance for the exact release pin")
    provenance = cast(dict[str, object], provenance)
    for field in ("provider", "release", "license", "compatibility_evidence"):
        if not provenance.get(field):
            raise ValueError(f"POSIX CPython SDK provenance lacks {field}")
    if provenance.get("target") != contract["platform"] or provenance.get("abi") != "cp313":
        raise ValueError("POSIX CPython SDK provenance does not match target/release ABI")
    url = cast(str, tools["cpython_source"]).format(version=pin)
    if httpx.URL(url).scheme != "https":
        raise ValueError("CPython SDK requires HTTPS")
    archive_format = tools.get("cpython_archive_format", "tar")
    if archive_format not in {"tar", "tar.gz", "tar.zst"}:
        raise ValueError("Unsupported CPython SDK archive format")
    decoder = _archive_decoder(tools) if archive_format == "tar.zst" else None
    return provenance, url, cast(str, archive_format), decoder


def _decode_sdk_archive(destination: Path, archive: Path, decoder: tuple[Path, dict[str, object]] | None) -> Path:
    decoded = archive
    if decoder is not None:
        decoded = destination / "cpython-sdk-decoded.tar"
        if decoded.exists():
            raise ValueError("SDK decoding must use a fresh isolated destination")
        command(str(decoder[0]), "--decompress", "--no-progress", "-o", str(decoded), "--", str(archive))
        if not decoded.is_file() or decoded.is_symlink():
            raise ValueError("SDK archive decoder did not produce a regular tar file")
    return decoded


def _extract_sdk(
    destination: Path, archive: Path, decoder: tuple[Path, dict[str, object]] | None, contract: Mapping[str, object]
) -> Path:
    decoded = _decode_sdk_archive(destination, archive, decoder)
    extraction = destination / "sdk-extraction"
    if extraction.exists():
        raise ValueError("SDK extraction must use a fresh isolated destination")
    extraction.mkdir()
    with tarfile.open(decoded) as package:
        package.extractall(extraction, filter="data")
    relative = Path(cast(dict[str, str], contract["sdk"])["archive_root"])
    sdk = (extraction / relative).resolve()
    if not sdk.is_relative_to(extraction.resolve()) or not sdk.is_dir():
        raise ValueError("Declared SDK archive root is missing or escapes extraction")
    selected = (destination / str(cast(dict[str, str], contract["sdk"])["root"])).resolve()
    if selected.is_relative_to(sdk) or sdk.is_relative_to(selected):
        raise ValueError("SDK destination must not overlap its extracted archive root")
    if not selected.is_relative_to(destination.resolve()) or selected.exists():
        raise ValueError("SDK destination must be a fresh child of the build destination")
    selected.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(sdk, selected)
    return selected


def _discard_derived_sdk(destination: Path, archive: Path, contract: Mapping[str, object]) -> None:
    # The build graph may create declared output directories before this runs, and a rebuild
    # finds the previous extraction. Both are derived from the verified archive.
    root = destination / str(cast(dict[str, str], contract["sdk"])["root"])
    derived = (destination / "cpython-sdk-decoded.tar", destination / "sdk-extraction", root)
    for path in derived:
        if path.is_symlink():
            raise ValueError("Derived SDK state must not be a symlink")
        resolved = path.resolve()
        if resolved in (destination, archive) or not resolved.is_relative_to(destination):
            raise ValueError("Derived SDK state must be a child of the build destination")
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()


def acquire_sdk(destination: Path, pin: str, tools: Mapping[str, object], contract: Mapping[str, object]) -> Path:
    """Acquire only a reviewed, hash-pinned SDK archive supplied by the build owner."""
    provenance, url, archive_format, decoder = _sdk_source(pin, tools, contract)
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "cpython-sdk.tar"
    if archive.is_symlink():
        raise ValueError("CPython SDK archive must not be a symlink")
    if not archive.exists():
        download_sdk(url, archive)
    if archive.is_symlink() or not archive.is_file() or digest(archive) != tools["cpython_sha256"]:
        raise ValueError("CPython SDK SHA256 mismatch")
    _discard_derived_sdk(destination, archive, contract)
    selected = _extract_sdk(destination, archive, decoder, contract)
    (destination / "sdk-provenance.json").write_text(
        json.dumps(
            {
                "source": url,
                "sha256": digest(archive),
                "archive_format": archive_format,
                "archive_decoder": decoder[1] if decoder is not None else None,
                **provenance,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return selected


def install_external_probe(destination: Path) -> list[str]:
    """Create a harmless executable outside the package for an explicit PATH override."""
    name = "cadrumo-override-probe"
    probe = destination / name
    with probe.open("x", encoding="utf-8", newline="\n") as output:
        output.write("#!/bin/sh\nexit 0\n")
    probe.chmod(0o700)
    return [name]


def _relocate_for_verification(package: Path, destination: Path, already_relocated: bool) -> Path:
    if already_relocated:
        relocated = package
    else:
        relocated = destination / "relocated ñ with spaces"
        if relocated.exists():
            raise ValueError("Native acceptance requires a fresh relocation directory")
        shutil.copytree(package, relocated)
    return relocated


def _probe_interpreter(executable: Path, destination: Path, script: str) -> dict[str, str]:
    with tempfile.TemporaryDirectory(prefix="cadrumo-native-state-", dir=destination) as temporary:
        environment = {key: value for key, value in os.environ.items() if not key.startswith(("LD_", "DYLD_"))}
        environment.update({STORAGE_ROOT.variable: temporary, "PYTHONPATH": temporary, "PYTHONHOME": temporary})
        for arguments in (["--check-package"], ["-c", script]):
            result = run_command(
                [str(executable), *arguments], environment=environment, cwd=Path(temporary), timeout_seconds=180
            )
            if result.returncode:
                raise ValueError(f"Native package probe failed: {result.stderr}")
        hostile = run_command(
            [str(executable), "-c", "raise SystemExit(0)"],
            environment={**environment, "LD_LIBRARY_PATH": temporary},
            cwd=Path(temporary),
            timeout_seconds=30,
        )
        if hostile.returncode == 0:
            raise ValueError("Interpreter admitted a hostile loader environment")
    return environment


def _probe_runtime_refusals(runtime: Path, executable: Path, environment: dict[str, str], destination: Path) -> None:
    backup = runtime.with_name(runtime.name + ".b2-probe-backup")
    if backup.exists():
        raise ValueError("Native runtime probe backup already exists")
    runtime.rename(backup)
    try:
        missing = run_command(
            [str(executable), "-c", "raise SystemExit(0)"], environment=environment, cwd=destination, timeout_seconds=30
        )
        if missing.returncode == 0 or "cannot load bundled" not in missing.stderr:
            raise ValueError("Interpreter started without its bundled runtime")
        runtime.write_bytes(b"not a native runtime library\n")
        damaged = run_command(
            [str(executable), "-c", "raise SystemExit(0)"], environment=environment, cwd=destination, timeout_seconds=30
        )
        if damaged.returncode == 0 or "cannot load bundled" not in damaged.stderr:
            raise ValueError("Interpreter started with a damaged bundled runtime")
    finally:
        runtime.unlink(missing_ok=True)
        backup.rename(runtime)


def _verify_runtime_layout(layout: Mapping[str, object], declared: Mapping[str, object]) -> None:
    runtime_layout = {key: value for key, value in layout.items() if key not in _BUILD_LAYOUT_FIELDS}
    runtime_declared = {key: value for key, value in declared.items() if key not in _BUILD_LAYOUT_FIELDS}
    if runtime_layout != runtime_declared:
        raise ValueError("Artifact layout differs from the selected target contract")


def _native_inventory(root: Path) -> dict[str, str]:
    return {path.relative_to(root).as_posix(): digest(path) for path in root.rglob("*") if path.is_file()}


def _smoke_modules(groups: Mapping[str, Sequence[str]]) -> list[str]:
    return sorted({name for names in groups.values() for name in names})


def verify_package(
    package: Path, destination: Path, expected_platform: str, *, already_relocated: bool = False
) -> None:
    """Exercise a relocated POSIX artifact and record immutable-file/child/import evidence."""
    from ..layout import load_layout
    from ..verification_paths import relocated_verification_package

    if sys.platform != expected_platform:
        raise ValueError("Native package verification requires a matching operating system")
    target = next(
        item
        for item in SUPPORTED_TARGETS
        if item.sys_platform == sys.platform and item.platform_machine == platform.machine()
    )
    declared = load_layout(target.name)
    if already_relocated:
        package = relocated_verification_package(package, destination)
    source_manifest = package / declared["files"]["package_manifest"]
    manifest = json.loads(source_manifest.read_text(encoding="utf-8"))
    layout = manifest["layout"]
    _verify_runtime_layout(layout, declared)
    # The caller passes the extracted package, never a build-host Python substitute.
    relocated = _relocate_for_verification(package, destination, already_relocated)
    before = _native_inventory(relocated)
    executable = relocated / layout["paths"]["executable"]
    modules = _smoke_modules(manifest["smoke_modules"])
    script = (
        "import importlib,json,subprocess,sys; "
        f"[importlib.import_module(name) for name in {modules!r}]; "
        "child=subprocess.check_output([sys.executable,'-c','import sys; print(sys.executable)'],text=True).strip(); "
        "child==sys.executable or sys.exit('Child interpreter escaped the package'); "
        "print(json.dumps({'executable':sys.executable}))"
    )
    environment = _probe_interpreter(executable, destination, script)
    after = _native_inventory(relocated)
    if before != after:
        raise ValueError("Native acceptance mutated the package")
    runtime = relocated / layout["paths"]["native"] / layout["files"]["runtime"]
    _probe_runtime_refusals(runtime, executable, environment, destination)
    restored = _native_inventory(relocated)
    if before != restored:
        raise ValueError("Native runtime refusal probes mutated the package")
    (destination / "native-verification.json").write_text(
        json.dumps(
            {
                "package": str(package.resolve()),
                "relocated": str(relocated.resolve()),
                "manifest_sha256": digest(source_manifest),
                "platform": sys.platform,
                "native_imports": modules,
                "child_identity": True,
                "package_immutable": True,
                "hostile_loader_refused": True,
                "missing_runtime_refused": True,
                "damaged_runtime_refused": True,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def command(tool: str, *arguments: str) -> str:
    """Run an explicitly supplied native tool, never a shell command."""
    executable = Path(tool)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError(f"Native tool must be an existing absolute path: {tool}")
    result = run_command([tool, *arguments], cwd=executable.parent, timeout_seconds=120)
    if result.returncode:
        raise ValueError(f"Native tool failed: {executable.name}: {result.stderr}")
    return result.stdout.strip()


def relative_loader_path(origin: Path, target: Path, token: str) -> str:
    """Name a package dependency from the directory of the requesting image."""
    return token + "/" + Path(os.path.relpath(target, origin)).as_posix()


def dependencies_by_name(images: list[Path]) -> dict[str, Path]:
    """Reject conflicting load identities before rewriting any native object."""
    names: dict[str, Path] = {}
    for path in images:
        previous = names.get(path.name)
        if previous is not None and digest(previous) != digest(path):
            raise ValueError(f"Ambiguous native dependency basename: {path.name}")
        names[path.name] = path
    return names
