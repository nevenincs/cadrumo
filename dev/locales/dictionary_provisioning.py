"""Provision the pinned Hunspell dictionary packages without Node or npm.

``package.json`` names the dictionary packages and their exact versions;
``package-lock.json`` pins each one's registry tarball and its ``sha512``
integrity. This module reads that lock, downloads each tarball over HTTPS,
verifies the digest before a single byte is unpacked, and publishes the package
under ``node_modules/<package>/`` in the layout
:func:`dev.locales._spelling.load_dictionaries` accepts. It is the only
provisioner for those packages: ``just setup`` and
``just setup-locale-spelling`` both run it, so a machine with no Node reaches
the same state as one with ``npm ci``.

Stdlib-only, because setup runs it before the project environment is relied on.
It writes nothing outside ``node_modules/`` in the chosen root and leaves any
other package there alone.

The controls, in the order they act:

* the package set, the versions and the tarball URLs come from the lock and
  must agree with ``package.json``; a URL other than the registry's own for the
  pinned version is refused;
* the download is bounded in size and time and never follows a redirect;
* the integrity digest is checked before the archive is opened;
* archive members are never trusted: a name that is absolute, climbs out of the
  package, carries a drive or stream separator, or a member that is not a plain
  file or directory (links, devices) is refused, and files are written by this
  module to paths it computed rather than by ``extractall``;
* the unpacked package must carry the manifest name and version the lock pins;
* the package is built in a sibling staging directory and renamed into place,
  so an interrupted run leaves either the previous state or a complete package.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import io
import json
import os
import shutil
import sys
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import uuid
import zlib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import TYPE_CHECKING, Final, cast, override

from dev.exit_codes import FAILED, OK
from dev.paths import REPO_ROOT

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence
    from email.message import Message
    from typing import IO

REGISTRY_ORIGIN: Final = "https://registry.npmjs.org/"
"""The only origin a tarball is fetched from."""

MAX_ARCHIVE_BYTES: Final = 32 * 1024 * 1024
"""Largest compressed download accepted; the pinned dictionaries are under 3 MiB."""

MAX_UNPACKED_BYTES: Final = 128 * 1024 * 1024
"""Largest total unpacked size accepted, which bounds a decompression bomb."""

MAX_MEMBERS: Final = 512
"""Most archive members accepted."""

FETCH_TIMEOUT_SECONDS: Final = 60.0
"""Seconds a connection or a read may block before the download is abandoned."""

STALE_STAGING_SECONDS: Final = 3600.0
"""Age after which a staging directory left by a killed run is removed."""

ARCHIVE_ROOT: Final = "package"
"""The single directory every npm tarball nests its files under."""

STAGING_PREFIX: Final = ".dictionary-staging-"
RETIRED_PREFIX: Final = ".dictionary-retired-"
RESTORE_COMMAND: Final = "just setup-locale-spelling"


class ProvisioningError(RuntimeError):
    """Describe a refusal or failure for one package and the action that fixes it."""

    def __init__(self, package: str, detail: str, next_action: str) -> None:
        """Record the package, what went wrong and the next action."""
        super().__init__(f"{package}: {detail}")
        self.package = package
        self.detail = detail
        self.next_action = next_action


@dataclass(frozen=True)
class LockedPackage:
    """One dictionary package exactly as the lock pins it."""

    name: str
    version: str
    url: str
    digest: bytes


def _restore_inputs(package: str, detail: str) -> ProvisioningError:
    return ProvisioningError(
        package,
        detail,
        "restore package.json and package-lock.json from the repository, then run " + RESTORE_COMMAND,
    )


def _read_json(path: Path, package: str) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise _restore_inputs(package, f"cannot read {path.name}: {exc}") from exc
    if not isinstance(payload, dict):
        raise _restore_inputs(package, f"{path.name} is not a JSON object")
    return cast("dict[str, object]", payload)


def _parse_digest(package: str, integrity: object) -> bytes:
    """Return the raw sha512 digest of an SRI string that names exactly one sha512."""
    if not isinstance(integrity, str):
        raise _restore_inputs(package, "the lock has no integrity hash for it")
    algorithm, _, encoded = integrity.partition("-")
    if algorithm != "sha512" or " " in integrity:
        raise _restore_inputs(package, "the lock integrity must be a single sha512 hash")
    try:
        digest = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise _restore_inputs(package, f"the lock integrity hash is not valid base64: {exc}") from exc
    if len(digest) != hashlib.sha512().digest_size:
        raise _restore_inputs(package, "the lock integrity hash is not a sha512 digest")
    return digest


def read_locked_packages(root: Path) -> tuple[LockedPackage, ...]:
    """Return every ``devDependencies`` package of ``package.json`` as the lock pins it.

    Raises:
        ProvisioningError: if the manifest declares a range, the lock lacks the
            package or pins another version, or the pinned tarball URL is not
            the registry's own for that version.
    """
    manifest = _read_json(root / "package.json", "package.json")
    lock = _read_json(root / "package-lock.json", "package-lock.json")
    declared = manifest.get("devDependencies")
    entries = lock.get("packages")
    if not isinstance(declared, dict) or not declared:
        raise _restore_inputs("package.json", "it declares no devDependencies")
    if not isinstance(entries, dict):
        raise _restore_inputs("package-lock.json", "it has no packages table")
    packages: list[LockedPackage] = []
    for name, wanted in sorted(declared.items()):
        entry = entries.get(f"node_modules/{name}")
        if not isinstance(entry, dict):
            raise _restore_inputs(name, "the lock does not pin it")
        version = entry.get("version")
        if not isinstance(version, str) or version != wanted:
            raise _restore_inputs(name, f"package.json declares {wanted!r} but the lock pins {version!r}")
        url = entry.get("resolved")
        expected_url = f"{REGISTRY_ORIGIN}{name}/-/{name}-{version}.tgz"
        if url != expected_url:
            raise _restore_inputs(name, f"the lock resolves it to {url!r}, not the registry archive {expected_url}")
        packages.append(LockedPackage(name, version, expected_url, _parse_digest(name, entry.get("integrity"))))
    return tuple(packages)


def is_installed(root: Path, package: LockedPackage) -> bool:
    """Return whether ``node_modules`` already holds this exact package, without any network use."""
    directory = root / "node_modules" / package.name
    if directory.is_symlink() or not directory.is_dir():
        return False
    try:
        payload = json.loads((directory / "package.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError):
        return False
    if (
        not isinstance(payload, dict)
        or payload.get("name") != package.name
        or payload.get("version") != package.version
    ):
        return False
    return all((directory / f"index.{suffix}").is_file() for suffix in ("aff", "dic"))


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Refuse redirects, so the host check on the lock URL stays the host that answers."""

    @override
    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: Message,
        newurl: str,
    ) -> urllib.request.Request | None:
        raise urllib.error.HTTPError(req.full_url, code, f"redirect to {newurl} refused", headers, fp)


def fetch_https(path: str, limit: int, timeout: float) -> bytes:
    """Download one archive from the registry within a byte limit and a timeout.

    The caller passes a path under the registry, never a URL, so the scheme and
    host are the literal text below and no other origin is reachable.

    Raises:
        ValueError: if the path is not a plain registry path or the body exceeds ``limit``.
        OSError: for any transport failure, including timeouts and HTTP errors.
    """
    if path.startswith("/") or "://" in path or "\\" in path:
        raise ValueError(f"{path!r} is not a registry path")
    request = urllib.request.Request(
        f"https://registry.npmjs.org/{path}", headers={"Accept": "application/octet-stream"}
    )
    with urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout) as response:
        declared = response.headers.get("Content-Length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            raise ValueError(f"the response declares {declared} bytes, over the {limit} byte limit")
        body = bytes(response.read(limit + 1))
    if len(body) > limit:
        raise ValueError(f"the response exceeds the {limit} byte limit")
    return body


def verify_integrity(package: LockedPackage, archive: bytes) -> None:
    """Refuse an archive whose sha512 is not the one the lock pins."""
    actual = hashlib.sha512(archive).digest()
    if actual != package.digest:
        raise ProvisioningError(
            package.name,
            "the downloaded archive does not match the integrity hash in package-lock.json "
            f"(expected sha512-{base64.b64encode(package.digest).decode()}, "
            f"got sha512-{base64.b64encode(actual).decode()})",
            f"do not use this download; check the network path and package-lock.json, then run {RESTORE_COMMAND} again",
        )


def _member_parts(package: LockedPackage, name: str) -> tuple[str, ...]:
    """Return the path below the archive root for ``name`` or refuse the entry."""
    if not name or "\\" in name or "\x00" in name or name.startswith("/"):
        raise _unsafe(package, name)
    parts = PurePosixPath(name).parts
    if not parts or parts[0] != ARCHIVE_ROOT or any(part in {"..", ".", ""} or ":" in part for part in parts):
        raise _unsafe(package, name)
    return parts[1:]


def _unsafe(package: LockedPackage, name: str) -> ProvisioningError:
    return ProvisioningError(
        package.name,
        f"the archive entry {name!r} would be written outside the package directory",
        "do not use this archive; report it, because its hash matched but it is not a plain npm package",
    )


def extract_archive(package: LockedPackage, archive: bytes, destination: Path) -> None:
    """Unpack a verified archive into the empty ``destination``, member by member.

    Raises:
        ProvisioningError: for an unsafe entry, a non-file entry, an oversized
            archive, a corrupt stream or a manifest that is not the pinned package.
    """
    total = 0
    try:
        with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as bundle:
            members = bundle.getmembers()
            if len(members) > MAX_MEMBERS:
                raise ProvisioningError(
                    package.name, f"the archive has more than {MAX_MEMBERS} entries", "do not use this archive"
                )
            for member in members:
                parts = _member_parts(package, member.name)
                if not (member.isreg() or member.isdir()):
                    raise ProvisioningError(
                        package.name,
                        f"the archive entry {member.name!r} is a link or special file",
                        "do not use this archive; report it",
                    )
                target = destination.joinpath(*parts)
                if os.path.commonpath([destination.resolve(), target.resolve()]) != str(destination.resolve()):
                    raise _unsafe(package, member.name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                total += member.size
                if total > MAX_UNPACKED_BYTES:
                    raise ProvisioningError(
                        package.name, "the archive unpacks beyond the size limit", "do not use this archive"
                    )
                source = bundle.extractfile(member)
                if source is None:
                    raise _unsafe(package, member.name)
                target.parent.mkdir(parents=True, exist_ok=True)
                with source, target.open("xb") as out:
                    shutil.copyfileobj(source, out)
    except (tarfile.TarError, EOFError, zlib.error, OSError) as exc:
        raise ProvisioningError(
            package.name,
            f"the archive cannot be unpacked: {exc}",
            f"run {RESTORE_COMMAND} again; if it persists, the download or the target disk is faulty",
        ) from exc
    _require_pinned_manifest(package, destination)


def _require_pinned_manifest(package: LockedPackage, directory: Path) -> None:
    try:
        payload = json.loads((directory / "package.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ProvisioningError(
            package.name, f"the archive has no readable package.json: {exc}", "do not use this archive"
        ) from exc
    name = payload.get("name") if isinstance(payload, dict) else None
    version = payload.get("version") if isinstance(payload, dict) else None
    if name != package.name or version != package.version:
        raise ProvisioningError(
            package.name,
            f"the archive is {name!r}@{version!r}, not the locked {package.name!r}@{package.version!r}",
            "do not use this archive; check package-lock.json",
        )
    missing = [f"index.{suffix}" for suffix in ("aff", "dic") if not (directory / f"index.{suffix}").is_file()]
    if missing:
        raise ProvisioningError(package.name, f"the archive lacks {', '.join(missing)}", "do not use this archive")


def _discard(path: Path) -> None:
    """Remove a file, link or directory tree without following a link."""
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.exists():
        shutil.rmtree(path, ignore_errors=True)


def publish(staging: Path, destination: Path) -> None:
    """Move a finished package into place; any previous content is restored if the move fails."""
    retired: Path | None = None
    if destination.exists() or destination.is_symlink():
        retired = destination.parent / f"{RETIRED_PREFIX}{uuid.uuid4().hex}"
        os.replace(destination, retired)
    try:
        os.replace(staging, destination)
    except OSError:
        if retired is not None:
            os.replace(retired, destination)
        raise
    if retired is not None:
        _discard(retired)


def _clear_abandoned(modules: Path, now: float) -> None:
    """Remove staging and retired directories left by an interrupted run."""
    for entry in modules.iterdir():
        if not entry.name.startswith((STAGING_PREFIX, RETIRED_PREFIX)):
            continue
        try:
            age = now - entry.lstat().st_mtime
        except OSError:
            continue
        if age > STALE_STAGING_SECONDS:
            _discard(entry)


def install_package(root: Path, package: LockedPackage, fetch: Callable[[str, int, float], bytes]) -> None:
    """Download, verify, unpack and atomically publish one package under ``root/node_modules``."""
    modules = root / "node_modules"
    modules.mkdir(parents=True, exist_ok=True)
    _clear_abandoned(modules, time.time())
    try:
        archive = fetch(package.url.removeprefix(REGISTRY_ORIGIN), MAX_ARCHIVE_BYTES, FETCH_TIMEOUT_SECONDS)
    except (OSError, ValueError) as exc:
        raise ProvisioningError(
            package.name,
            f"cannot download {package.url}: {exc}",
            f"check network access to registry.npmjs.org (HTTPS proxy settings apply), then run {RESTORE_COMMAND}",
        ) from exc
    verify_integrity(package, archive)
    staging = Path(tempfile.mkdtemp(prefix=STAGING_PREFIX, dir=modules))
    try:
        extract_archive(package, archive, staging)
        publish(staging, modules / package.name)
    except OSError as exc:
        raise ProvisioningError(
            package.name,
            f"cannot publish into {modules}: {exc}",
            f"close anything using node_modules/{package.name}, then run {RESTORE_COMMAND} again",
        ) from exc
    finally:
        _discard(staging)


def provision(
    root: Path,
    fetch: Callable[[str, int, float], bytes] = fetch_https,
    say: Callable[[str], None] = print,
) -> tuple[str, ...]:
    """Make every locked dictionary package present under ``root``; return the names installed.

    Packages that are already valid cost no network use.
    """
    installed: list[str] = []
    for package in read_locked_packages(root):
        if is_installed(root, package):
            say(f"{package.name} {package.version}: already installed")
            continue
        say(f"{package.name} {package.version}: downloading {package.url}")
        install_package(root, package, fetch)
        installed.append(package.name)
        say(f"{package.name} {package.version}: installed")
    return tuple(installed)


def main(argv: Sequence[str] | None = None) -> int:
    """Provision the pinned dictionaries; exit 0 on success and 1 naming the package on failure."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument(
        "--root", type=Path, default=REPO_ROOT, help="Directory holding package.json and package-lock.json."
    )
    args = parser.parse_args(argv)
    try:
        provision(args.root, say=lambda line: print(line, file=sys.stderr))
    except ProvisioningError as exc:
        print(f"locale dictionaries: {exc}\n  next: {exc.next_action}", file=sys.stderr)
        return FAILED
    return OK


if __name__ == "__main__":
    raise SystemExit(main())
