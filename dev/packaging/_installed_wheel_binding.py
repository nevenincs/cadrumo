"""Bind an installed CLI environment to the exact immutable root wheel payload."""

from __future__ import annotations

import hashlib
import json
import subprocess
import zipfile
from pathlib import Path, PurePosixPath

from dev._paths import UTF_8

_GENERATED_METADATA = frozenset({"INSTALLER", "RECORD", "REQUESTED", "direct_url.json", "uv_cache.json"})


def _projection_digest(rows: list[tuple[str, str]]) -> str:
    payload = json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":")).encode(UTF_8)
    return hashlib.sha256(payload).hexdigest()


def sealed_wheel_payload_sha256(wheel: Path) -> str:
    """Return the canonical digest of immutable install payload members."""
    rows: list[tuple[str, str]] = []
    with zipfile.ZipFile(wheel) as archive:
        for info in archive.infolist():
            path = PurePosixPath(info.filename)
            if info.is_dir() or path.name in _GENERATED_METADATA:
                continue
            rows.append((path.as_posix(), hashlib.sha256(archive.read(info)).hexdigest()))
    return _projection_digest(rows)


def assert_archive_members_match_extraction(
    archive_path: Path,
    extracted_root: Path,
    *,
    allowed_generated_roots: frozenset[str] = frozenset(),
) -> str:
    """Verify every immutable archive member exists byte-for-byte in its extraction root."""
    rows: list[tuple[str, str]] = []
    root = extracted_root.resolve(strict=True)
    archive_files: set[str] = set()
    with zipfile.ZipFile(archive_path) as archive:
        for info in archive.infolist():
            if info.is_dir():
                continue
            member = PurePosixPath(info.filename)
            archive_files.add(member.as_posix())
            target = (root / Path(*member.parts)).resolve(strict=True)
            if not target.is_relative_to(root) or not target.is_file():
                raise RuntimeError(f"archive member escapes or is absent from extraction: {member}")
            expected = hashlib.sha256(archive.read(info)).hexdigest()
            if hashlib.sha256(target.read_bytes()).hexdigest() != expected:
                raise RuntimeError(f"extracted archive member digest drifted: {member}")
            rows.append((member.as_posix(), expected))
    if not rows:
        raise RuntimeError("sealed archive has no immutable members to bind")
    extracted_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file() and path.relative_to(root).parts[0] not in allowed_generated_roots
    }
    extras = extracted_files - archive_files
    if extras:
        raise RuntimeError(f"extraction carries unsealed extra members: {sorted(extras)[:10]!r}")
    return _projection_digest(rows)


def installed_python_for_cli(cli: Path) -> Path:
    """Resolve the interpreter that owns an installed console entry point."""
    resolved = cli.resolve(strict=True)
    if resolved.suffix.lower() == ".exe":
        candidate = resolved.parent / "python.exe"
        return candidate.resolve(strict=True)
    first_line = resolved.read_bytes().splitlines()[0].decode(UTF_8)
    if not first_line.startswith("#!"):
        raise RuntimeError(f"installed CLI has no absolute Python shebang: {resolved}")
    interpreter = first_line[2:].strip().split(" ", 1)[0]
    return Path(interpreter).resolve(strict=True)


def installed_distribution_payload_sha256(cli: Path, distribution: str) -> str:
    """Hash one installed distribution through the executable-owning interpreter."""
    python = installed_python_for_cli(cli)
    script = r"""
import hashlib, importlib.metadata, json
generated = {"INSTALLER", "RECORD", "direct_url.json", "REQUESTED"}
dist = importlib.metadata.distribution(__import__("sys").argv[1])
rows = []
for item in dist.files or ():
    path = item.as_posix()
    if (
        item.name in generated | {"uv_cache.json"}
        or ".." in item.parts
        or path.endswith(".pyc")
        or "/__pycache__/" in path
    ):
        continue
    resolved = dist.locate_file(item).resolve(strict=True)
    if resolved.is_file():
        rows.append((path, hashlib.sha256(resolved.read_bytes()).hexdigest()))
payload = json.dumps(sorted(rows), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
print(hashlib.sha256(payload).hexdigest())
"""
    completed = subprocess.run(  # noqa: S603 - interpreter is resolved from the installed CLI.
        [str(python), "-I", "-c", script, distribution],
        check=False,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="strict",
    )
    if completed.returncode != 0:
        raise RuntimeError(f"could not attest installed cadrumo payload: {completed.stderr.strip()}")
    digest = completed.stdout.strip()
    if len(digest) != 64:
        raise RuntimeError(f"installed payload returned invalid digest: {digest!r}")
    return digest


def assert_installed_console_entry_point(
    executable: Path,
    *,
    distribution: str,
    entry_point: str,
    expected_value: str,
) -> None:
    """Resolve an entry point independently through the confined interpreter."""
    resolved = executable.resolve(strict=True)
    python = installed_python_for_cli(resolved)
    launcher_name = f"{entry_point}.exe" if resolved.suffix.lower() == ".exe" else entry_point
    if resolved != (python.parent / launcher_name).resolve(strict=True):
        raise RuntimeError("console entry point is not the confined environment launcher")
    module_name, callable_name = expected_value.split(":", 1)
    expected_script = (
        f"#!{python}\n"
        "# -*- coding: utf-8 -*-\n"
        "import sys\n"
        f"from {module_name} import {callable_name}\n"
        'if __name__ == "__main__":\n'
        '    if sys.argv[0].endswith("-script.pyw"):\n'
        "        sys.argv[0] = sys.argv[0][:-11]\n"
        '    elif sys.argv[0].endswith(".exe"):\n'
        "        sys.argv[0] = sys.argv[0][:-4]\n"
        f"    sys.exit({callable_name}())\n"
    ).encode(UTF_8)
    if resolved.suffix.lower() == ".exe":
        try:
            with zipfile.ZipFile(resolved) as launcher:
                if launcher.namelist() != ["__main__.py"] or launcher.read("__main__.py") != expected_script:
                    raise RuntimeError("console entry-point launcher semantics drifted")
            peer_name = "cadrumo-mcp.exe" if entry_point == "aeat" else "aeat.exe"
            peer = resolved.with_name(peer_name).resolve(strict=True)
            executable_bytes = resolved.read_bytes()
            peer_bytes = peer.read_bytes()
            executable_zip = executable_bytes.find(b"PK\x03\x04")
            peer_zip = peer_bytes.find(b"PK\x03\x04")
            if executable_zip < 0 or peer_zip < 0 or executable_bytes[:executable_zip] != peer_bytes[:peer_zip]:
                raise RuntimeError("console entry-point launcher stub drifted")
        except (OSError, zipfile.BadZipFile) as exc:
            raise RuntimeError("console entry-point launcher is malformed") from exc
    elif resolved.read_bytes() != expected_script:
        raise RuntimeError("console entry-point launcher semantics drifted")
    script = r"""
import importlib, importlib.metadata, pathlib, sys
distribution, entry_name, expected = sys.argv[1:]
dist = importlib.metadata.distribution(distribution)
matches = [ep for ep in dist.entry_points if ep.group == "console_scripts" and ep.name == entry_name]
if len(matches) != 1 or matches[0].value != expected:
    raise SystemExit("console entry-point metadata drifted")
module = importlib.import_module(expected.split(":", 1)[0])
origin = pathlib.Path(module.__file__).resolve(strict=True)
site_root = pathlib.Path(dist.locate_file("")).resolve(strict=True)
if not origin.is_relative_to(site_root):
    raise SystemExit("console entry-point module escaped installed distribution root")
target = module
for component in expected.split(":", 1)[1].split("."):
    target = getattr(target, component)
if not callable(target):
    raise SystemExit("console entry-point target is not callable")
"""
    completed = subprocess.run(  # noqa: S603 - interpreter belongs to the confined installed environment.
        [str(python), "-I", "-c", script, distribution, entry_point, expected_value],
        check=False,
        capture_output=True,
        text=True,
        encoding=UTF_8,
        errors="strict",
        timeout=15,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"installed console entry-point binding failed: {completed.stderr.strip()}")


def installed_wheel_payload_sha256(cli: Path) -> str:
    """Hash the installed ``cadrumo`` payload through the CLI-owning interpreter."""
    return installed_distribution_payload_sha256(cli, "cadrumo")
