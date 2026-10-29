"""Build the existing Python product wheels in a stable native-build snapshot."""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Mapping
from functools import partial
from pathlib import Path, PurePosixPath

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo.core.toml import parse_toml
from dev.first_party_source import PYTEST_CONFTEST
from dev.source_tree import line_ending_policies, normalise_with, repository_files, snapshot

from .hashing import digest, transformed_digest

BUNDLED_EXTRAS: tuple[str, ...] = ("llm", "browser")
"""Optional extras the native application ships with its core closure.

The application serves the local model's review operations, which refuse
without ``llm``, and the AEAT browser sessions, which refuse without
``browser``. Playwright's Node driver ships with it; the Chromium builds are
provisioned into profile storage on demand. The wheel's core install stays
without either extra.
"""

_PRODUCT_INPUT_EXCLUSIONS = frozenset({"__pycache__", ".git", "tests"})


def _product_source_roots(root: Path) -> tuple[str, ...]:
    """Read the package roots from the same declarations used by CMake."""
    project = parse_toml((root / "pyproject.toml").read_text(encoding="utf-8"))
    paths = [project["tool"]["uv"]["sources"][name]["path"] for name in PRODUCT_IDENTITY.companion_distributions]
    hook = Path(project["tool"]["hatch"]["build"]["targets"]["wheel"]["hooks"]["custom"]["path"])
    paths.append(hook.parent.as_posix())

    root = root.resolve()
    resolved: list[str] = ["src"]
    for value in paths:
        candidate = (root / value).resolve(strict=False)
        try:
            relative = candidate.relative_to(root).as_posix()
        except ValueError as exc:
            raise ValueError("Product wheel source roots must stay inside the repository") from exc
        resolved.append("" if relative == "." else relative)
    return tuple(dict.fromkeys(resolved))


def _excluded_product_input(relative: str) -> bool:
    """Mirror cadrumo_product_inputs' exclusions for the snapshot source census."""
    path = PurePosixPath(relative)
    parts = path.parts
    return (
        relative == "src/cadrumo/_data/google/oauth_client.json"
        or any(part in _PRODUCT_INPUT_EXCLUSIONS for part in parts)
        or path.suffix in {".pyc", ".lock"}
        or path.name == PYTEST_CONFTEST
        or any(
            part.startswith(
                (".aeat-generated-export-transaction-", ".generated-export-backup-", ".generated-export-stage-")
            )
            for part in parts
        )
    )


def _input_manifest_members(root: Path, inputs: Path | None) -> frozenset[str] | None:
    """Return manifest paths that belong to the source snapshot."""
    if inputs is None:
        return None
    repository = root.resolve()
    members: set[str] = set()
    for line in inputs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        candidate = Path(line)
        if not candidate.is_absolute():
            candidate = repository / candidate
        try:
            relative = candidate.resolve(strict=False).relative_to(repository).as_posix()
        except ValueError:
            # Runtime receipts and generated authority are admitted by CMake but
            # live outside the source snapshot and are checked by its input hash.
            continue
        # CMake has already filtered recursive inputs. Keep explicit owners such
        # as the root uv.lock even when their suffix matches that filter.
        members.add(relative)
    return frozenset(members)


def _membership_changed(detail: str) -> RuntimeError:
    return RuntimeError(
        "Product source membership changed while capturing the wheel inputs "
        f"({detail}). Re-run the CMake build so CONFIGURE_DEPENDS refreshes inputs-product.txt, then retry."
    )


def _normalised_digest(root: Path, relative: str, policy: str) -> str:
    """The digest of one source file's content as the repository records it."""
    return transformed_digest(root / relative, f"line-endings:{policy}", partial(normalise_with, policy))


def _framed_digest(digests: Mapping[str, str]) -> str:
    """Frame member digests exactly as ``source_tree.member_content_digest`` frames member bytes."""
    framed = hashlib.sha256()
    for relative in sorted(digests):
        framed.update(relative.encode("utf-8"))
        framed.update(b"\0")
        framed.update(bytes.fromhex(digests[relative]))
        framed.update(b"\n")
    return framed.hexdigest()


def _source_digest(root: Path, files: tuple[str, ...]) -> str:
    """``source_tree.content_digest`` of ``files``, answered from the digest cache where it can be."""
    policies = line_ending_policies(root, files)
    return _framed_digest({relative: _normalised_digest(root, relative, policies[relative]) for relative in files})


def _enrolled_members(
    package_members: frozenset[str], file_members: frozenset[str], manifest_members: frozenset[str] | None
) -> tuple[str, ...]:
    if manifest_members is None:
        # Standalone callers still receive a bounded content-stability check.
        enrolled = set(package_members)
        if "pyproject.toml" in file_members:
            enrolled.add("pyproject.toml")
    else:
        missing = sorted(package_members - manifest_members)
        if missing:
            raise _membership_changed(f"{missing[0]} is absent from inputs-product.txt")
        enrolled = set(file_members & manifest_members)
    return tuple(sorted(enrolled))


def _check_current_members(
    root: Path,
    source_roots: tuple[str, ...],
    package_members: frozenset[str],
    manifest_members: frozenset[str] | None,
) -> None:
    current_roots = _product_source_roots(root)
    current_package_members = frozenset(
        name for name in repository_files(root, under=current_roots) if not _excluded_product_input(name)
    )
    if current_roots != source_roots or current_package_members != package_members:
        raise _membership_changed("wheel package roots or source files changed during snapshotting")
    if manifest_members is not None:
        missing = sorted(current_package_members - manifest_members)
        if missing:
            raise _membership_changed(f"{missing[0]} is absent from inputs-product.txt")


def _check_captured_members(destination: Path, source_roots: tuple[str, ...], package_members: frozenset[str]) -> None:
    captured_package_members = frozenset(
        name for name in repository_files(destination, under=source_roots) if not _excluded_product_input(name)
    )
    if captured_package_members != package_members:
        raise _membership_changed("the captured wheel source membership differs from its initial census")


def capture_product_source_snapshot(root: Path, destination: Path, inputs: Path | None) -> None:
    """Capture and verify one coherent, enrolled source set before building any wheel."""
    root = root.resolve()
    source_roots = _product_source_roots(root)
    metadata = ("pyproject.toml", "uv.lock", "README.md", "LICENSE", "NOTICE", ".gitignore", ".gitattributes")
    # One census names the package members; the snapshot adds the project's metadata files.
    package_members = frozenset(
        name for name in repository_files(root, under=source_roots) if not _excluded_product_input(name)
    )
    files = tuple(sorted({*package_members, *(name for name in metadata if (root / name).is_file())}))
    file_members = frozenset(files)

    manifest_members = _input_manifest_members(root, inputs)
    enrolled_members = _enrolled_members(package_members, file_members, manifest_members)
    before = _source_digest(root, enrolled_members)

    _sync_source_snapshot(root, files, destination)
    captured = _framed_digest({name: digest(destination / name) for name in enrolled_members})
    _check_captured_members(destination, source_roots, package_members)

    _check_current_members(root, source_roots, package_members, manifest_members)
    after = _source_digest(root, enrolled_members)
    if before != captured or captured != after:
        raise RuntimeError(
            "Enrolled product source content changed while capturing the wheel inputs; "
            "retry after the enrolled source files are stable."
        )


def _check_snapshot_links(destination: Path) -> None:
    for ancestor in (destination, *destination.parents):
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError("Product source snapshot contains a linked member")
    pending = [destination] if destination.is_dir() else []
    while pending:
        for member in pending.pop().iterdir():
            if member.is_symlink() or member.is_junction():
                raise ValueError("Product source snapshot contains a linked member")
            if member.is_dir():
                pending.append(member)


def _remove_obsolete_snapshot_files(destination: Path, files: tuple[str, ...]) -> None:
    expected = set(files)
    for path in destination.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(destination).as_posix()
        if relative.startswith(".authority/") or relative == "src/cadrumo/_data/google/oauth_client.json":
            continue
        if relative not in expected:
            path.unlink()


def _sync_source_snapshot(root: Path, files: tuple[str, ...], destination: Path) -> None:
    """Preserve unchanged normalized source files and remove obsolete snapshot members."""
    _check_snapshot_links(destination)
    if not destination.exists():
        snapshot(root, files, destination)
        return
    _remove_obsolete_snapshot_files(destination, files)
    # The line-ending rules are read once for every file, not once per file.
    policies = line_ending_policies(root, files)
    for relative in files:
        path = destination / relative
        expected = _normalised_digest(root, relative, policies[relative])
        if path.is_file() and digest(path) == expected:
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(normalise_with(policies[relative], (root / relative).read_bytes()))
        shutil.copystat(root / relative, path)
    for directory in sorted(destination.rglob("*"), reverse=True):
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
