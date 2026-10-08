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
from collections.abc import Callable
from fnmatch import fnmatchcase
from pathlib import Path
from typing import Any

import httpx

from cadrumo.core.storage_environment import STORAGE_ROOT

from ...command_execution import run_command
from ...runtime_wheelhouse_contract import SUPPORTED_TARGETS
from ..hashing import digest

# These inputs describe assembly on the builder, rather than shipped runtime paths.
# Preserve every other contract field until the common manifest owns that projection.
_BUILD_LAYOUT_FIELDS = frozenset({"native_tools", "native_signing_identity"})
_SDK_DOWNLOAD_HOSTS = frozenset({"github.com", "release-assets.githubusercontent.com", "objects.githubusercontent.com"})
_SDK_DOWNLOAD_LIMIT = 1024 * 1024 * 1024


def _download_sdk(url: str, archive: Path) -> None:
    """Follow at most three HTTPS redirects within GitHub's release asset origins."""
    current = httpx.URL(url)
    if current.host != "github.com" or not current.path.startswith(
        "/astral-sh/python-build-standalone/releases/download/"
    ):
        raise ValueError("CPython SDK must originate from the pinned GitHub release")
    partial = archive.with_name(archive.name + ".partial")
    created = False
    try:
        for redirects in range(4):
            if (
                current.scheme != "https"
                or current.host not in _SDK_DOWNLOAD_HOSTS
                or current.port not in {None, 443}
                or current.userinfo
            ):
                raise ValueError("CPython SDK redirect leaves the admitted HTTPS origins")
            with httpx.stream("GET", current, timeout=120, follow_redirects=False) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location or redirects == 3:
                        raise ValueError("CPython SDK redirect is missing or exceeds the redirect limit")
                    current = current.join(location)
                    continue
                response.raise_for_status()
                size = 0
                with partial.open("xb") as output:
                    created = True
                    for chunk in response.iter_bytes():
                        size += len(chunk)
                        if size > _SDK_DOWNLOAD_LIMIT:
                            raise ValueError("CPython SDK exceeds the download size limit")
                        output.write(chunk)
                partial.rename(archive)
                created = False
                return
    finally:
        if created:
            partial.unlink(missing_ok=True)


def _archive_decoder(tools: dict[str, Any]) -> tuple[Path, dict[str, Any]]:
    """Admit an explicit, hash-pinned build tool without discovering a host decoder."""
    decoder = tools.get("cpython_archive_decoder")
    if not isinstance(decoder, dict):
        raise ValueError("tar.zst SDK requires an explicit pinned build-only archive decoder")
    provenance = decoder.get("provenance")
    if not isinstance(provenance, dict) or any(
        not isinstance(provenance.get(field), str) or not provenance[field]
        for field in ("provider", "release", "source", "source_sha256")
    ):
        raise ValueError("SDK archive decoder requires source provenance")
    if not re.fullmatch(r"[0-9a-f]{64}", provenance["source_sha256"]):
        raise ValueError("SDK archive decoder requires an exact source SHA256")
    source = httpx.URL(provenance["source"])
    if source.scheme != "https" or source.userinfo:
        raise ValueError("SDK archive decoder source requires HTTPS without credentials")
    executable = Path(str(decoder.get("executable", "")))
    if not executable.is_absolute() or not executable.is_file() or digest(executable) != decoder.get("sha256"):
        raise ValueError("SDK archive decoder must be an existing absolute hash-pinned executable")
    return executable, decoder


def acquire_sdk(destination: Path, pin: str, tools: dict[str, Any], contract: dict[str, Any]) -> Path:
    """Acquire only a reviewed, hash-pinned SDK archive supplied by the build owner."""
    provenance = tools.get("cpython_provenance")
    if not isinstance(provenance, dict) or provenance.get("version") != pin:
        raise ValueError("POSIX CPython SDK needs reviewed provenance for the exact release pin")
    for field in ("provider", "release", "license", "compatibility_evidence"):
        if not provenance.get(field):
            raise ValueError(f"POSIX CPython SDK provenance lacks {field}")
    if provenance.get("target") != contract["platform"] or provenance.get("abi") != "cp313":
        raise ValueError("POSIX CPython SDK provenance does not match target/release ABI")
    url = tools["cpython_source"].format(version=pin)
    if httpx.URL(url).scheme != "https":
        raise ValueError("CPython SDK requires HTTPS")
    archive_format = tools.get("cpython_archive_format", "tar")
    if archive_format not in {"tar", "tar.gz", "tar.zst"}:
        raise ValueError("Unsupported CPython SDK archive format")
    decoder = _archive_decoder(tools) if archive_format == "tar.zst" else None
    destination = destination.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    archive = destination / "cpython-sdk.tar"
    if archive.is_symlink():
        raise ValueError("CPython SDK archive must not be a symlink")
    if not archive.exists():
        _download_sdk(url, archive)
    if archive.is_symlink() or not archive.is_file() or digest(archive) != tools["cpython_sha256"]:
        raise ValueError("CPython SDK SHA256 mismatch")
    decoded = archive
    if decoder is not None:
        decoded = destination / "cpython-sdk-decoded.tar"
        if decoded.exists():
            raise ValueError("SDK decoding must use a fresh isolated destination")
        command(str(decoder[0]), "--decompress", "--no-progress", "-o", str(decoded), "--", str(archive))
        if not decoded.is_file() or decoded.is_symlink():
            raise ValueError("SDK archive decoder did not produce a regular tar file")
    extraction = destination / "sdk-extraction"
    if extraction.exists():
        raise ValueError("SDK extraction must use a fresh isolated destination")
    extraction.mkdir()
    with tarfile.open(decoded) as package:
        package.extractall(extraction, filter="data")
    relative = Path(contract["sdk"]["archive_root"])
    sdk = (extraction / relative).resolve()
    if not sdk.is_relative_to(extraction.resolve()) or not sdk.is_dir():
        raise ValueError("Declared SDK archive root is missing or escapes extraction")
    selected = (destination / str(contract["sdk"]["root"])).resolve()
    if selected.is_relative_to(sdk) or sdk.is_relative_to(selected):
        raise ValueError("SDK destination must not overlap its extracted archive root")
    if not selected.is_relative_to(destination.resolve()) or selected.exists():
        raise ValueError("SDK destination must be a fresh child of the build destination")
    selected.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(sdk, selected)
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
    runtime_layout = {key: value for key, value in layout.items() if key not in _BUILD_LAYOUT_FIELDS}
    runtime_declared = {key: value for key, value in declared.items() if key not in _BUILD_LAYOUT_FIELDS}
    if runtime_layout != runtime_declared:
        raise ValueError("Artifact layout differs from the selected target contract")
    # The caller passes the extracted package, never a build-host Python substitute.
    if already_relocated:
        relocated = package
    else:
        relocated = destination / "relocated ñ with spaces"
        if relocated.exists():
            raise ValueError("Native acceptance requires a fresh relocation directory")
        shutil.copytree(package, relocated)
    before = {path.relative_to(relocated).as_posix(): digest(path) for path in relocated.rglob("*") if path.is_file()}
    executable = relocated / layout["paths"]["executable"]
    modules = sorted({name for names in manifest["smoke_modules"].values() for name in names})
    script = (
        "import importlib,json,subprocess,sys; "
        f"[importlib.import_module(name) for name in {modules!r}]; "
        "child=subprocess.check_output([sys.executable,'-c','import sys; print(sys.executable)'],text=True).strip(); "
        "child==sys.executable or sys.exit('Child interpreter escaped the package'); "
        "print(json.dumps({'executable':sys.executable}))"
    )
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
    after = {path.relative_to(relocated).as_posix(): digest(path) for path in relocated.rglob("*") if path.is_file()}
    if before != after:
        raise ValueError("Native acceptance mutated the package")
    runtime = relocated / layout["paths"]["native"] / layout["files"]["runtime"]
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
    restored = {path.relative_to(relocated).as_posix(): digest(path) for path in relocated.rglob("*") if path.is_file()}
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


def native_image(path: Path) -> bool:
    """Recognize supported native image containers without executing them."""
    if not path.is_file():
        return False
    with path.open("rb") as source:
        magic = source.read(4)
        return magic.startswith(b"MZ") or magic in {
            b"\x7fELF",
            b"\xcf\xfa\xed\xfe",
            b"\xfe\xed\xfa\xcf",
            b"\xce\xfa\xed\xfe",
            b"\xfe\xed\xfa\xce",
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
            b"\xca\xfe\xba\xbf",
            b"\xbf\xba\xfe\xca",
        }


def relative_loader_path(origin: Path, target: Path, token: str) -> str:
    """Name a package dependency from the directory of the requesting image."""
    return token + "/" + Path(os.path.relpath(target, origin)).as_posix()


def assemble(
    python: Path,
    packages: Path,
    native: Path,
    root: Path,
    contract: dict[str, Any],
    relocate: Callable[[list[Path], Path, dict[str, Any]], None],
) -> dict[str, Any]:
    """Stage declared SDK images and wheel native files before per-object relocation."""
    modules: dict[str, str] = {}
    relocation: dict[str, str] = {}
    if list(packages.glob("*.pth")):
        raise ValueError("POSIX wheel .pth files require explicit review")
    sdk = contract["sdk"]
    suffix = sdk["extension_suffix"]
    if not suffix.endswith(".so") or suffix == ".so":
        raise ValueError("The target CPython extension suffix must identify its ABI")
    exclusions = sdk.get("extension_exclusions", [])
    if not isinstance(exclusions, list) or any(
        not isinstance(entry, dict)
        or not isinstance(entry.get("pattern"), str)
        or not entry["pattern"]
        or "/" in entry["pattern"]
        or "\\" in entry["pattern"]
        or not isinstance(entry.get("reason"), str)
        or not entry["reason"]
        for entry in exclusions
    ):
        raise ValueError("SDK extension exclusions require basename patterns and reasons")
    excluded = []
    # B1 supplies exact SDK-relative native inputs; no host library discovery.
    for relative in sdk["native_files"]:
        source = (python / relative).resolve()
        if not source.is_relative_to(python.resolve()) or not native_image(source):
            raise ValueError(f"Invalid SDK native image: {relative}")
        target = native / Path(relative).name
        if target.exists() and digest(target) != digest(source):
            raise ValueError(f"Conflicting SDK native image: {target.name}")
        shutil.copy2(source, target)
    extensions = (python / sdk["extensions"]).resolve()
    if not extensions.is_relative_to(python.resolve()) or not extensions.is_dir():
        raise ValueError("SDK extension directory is missing or outside the SDK")
    for source in sorted(extensions.glob("*.so")):
        matches = [entry for entry in exclusions if fnmatchcase(source.name, entry["pattern"])]
        if matches:
            excluded.append(
                {
                    "file": source.relative_to(python).as_posix(),
                    "sha256": digest(source),
                    "reasons": [entry["reason"] for entry in matches],
                }
            )
            continue
        if (
            not source.name.endswith(suffix)
            or not source.resolve().is_relative_to(python.resolve())
            or not native_image(source)
        ):
            raise ValueError(f"Invalid SDK extension image or release ABI: {source.name}")
        target = native / source.name
        if target.exists():
            raise ValueError(f"Duplicate SDK extension: {source.name}")
        shutil.copy2(source, target)
        modules[source.name.split(".")[0]] = target.relative_to(root).as_posix()
    for source in sorted(packages.rglob("*")):
        if not native_image(source):
            continue
        if source.is_symlink():
            raise ValueError(f"Wheel native symlink requires explicit admission: {source}")
        relative = source.relative_to(packages)
        target = native / "packages" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            raise ValueError(f"Duplicate native destination: {target}")
        shutil.move(source, target)
        relocation[source.relative_to(root).as_posix()] = target.relative_to(root).as_posix()
        if source.name.endswith((suffix, ".abi3.so")):
            parts = [*relative.parts[:-1], relative.name.split(".")[0]]
            if parts[-1] == "__init__":
                parts.pop()
            identity = ".".join(parts)
            if identity in modules:
                raise ValueError(f"Duplicate extension identity: {identity}")
            modules[identity] = target.relative_to(root).as_posix()
    patches = []
    bindings = packages / "pypdfium2_raw/bindings.py"
    if bindings.is_file():
        candidates = list((native / "packages/pypdfium2_raw").glob("*pdfium*"))
        if len(candidates) != 1:
            raise ValueError("PDFium must have exactly one bundled native library")
        source = bindings.read_text(encoding="utf-8")
        old = "libpaths = ('./{prefix}{name}.{suffix}',),"
        if source.count(old) != 1:
            raise ValueError("Unrecognized pypdfium2 ctypesgen loader")
        before = digest(bindings)
        relative = candidates[0].relative_to(root).as_posix()
        parent = contract["package_root_from_executable"]
        replacement = f"libpaths = (str(pathlib.Path(sys.executable).parent / {parent!r} / {relative!r}),),"
        bindings.write_text(source.replace(old, replacement), encoding="utf-8")
        patches.append(
            {
                "file": bindings.relative_to(root).as_posix(),
                "before": before,
                "after": digest(bindings),
                "reason": "Relocated explicit PDFium library path",
            }
        )
    images = [path for path in root.rglob("*") if native_image(path)]
    relocate(images, root, contract)
    return {
        "modules": modules,
        "python_paths": [packages.relative_to(root).as_posix()],
        "relocation": relocation,
        "patches": patches,
        "sdk_extension_exclusions": excluded,
    }


def dependencies_by_name(images: list[Path]) -> dict[str, Path]:
    """Reject conflicting load identities before rewriting any native object."""
    names: dict[str, Path] = {}
    for path in images:
        previous = names.get(path.name)
        if previous is not None and digest(previous) != digest(path):
            raise ValueError(f"Ambiguous native dependency basename: {path.name}")
        names[path.name] = path
    return names
