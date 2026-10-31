"""Seal the macOS application bundle inside-out and verify every copy of the seal.

Package assembly signs each nested image it owns, and those bytes are bound by the
package inventory, so sealing never re-signs them. Installation staging requires
that every nested image already carries a valid signature, then signs the bundle
last: the main executable's signature binds ``Info.plist`` and the resource seal
in ``Contents/_CodeSignature/CodeResources`` hashes every other member. Nothing
writes into the bundle afterwards; packaging only copies the sealed stage and
verifies each copy it produces. The staging check also starts the sealed bundle's
runtime role, only after the seal verifies, so no package is built from a bundle
that cannot start.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import plistlib
import posixpath
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Protocol

from ..command_execution import run_command
from .build_directory import require_enrolled_build
from .build_paths import build_paths
from .hashing import digest
from .layout import ApplicationBundle
from .platforms.posix_images import macho_image

_SEAL_RESOURCES = "_CodeSignature/CodeResources"


class BundleSealer(Protocol):
    """Seal an assembled application bundle and verify an existing seal."""

    def binding(self) -> dict[str, str]:
        """Return the sealing inputs that a changed seal must be rebuilt for."""
        ...

    def seal(self, bundle: Path, main_executable: Path, application_id: str) -> None:
        """Seal ``bundle`` after admitting its nested images, then verify the seal."""
        ...

    def verify(self, bundle: Path, application_id: str) -> None:
        """Refuse ``bundle`` unless its complete seal is valid for ``application_id``."""
        ...


def sealed_members(application: str, wrapper: ApplicationBundle, executable: str) -> frozenset[str]:
    """Return the stage members the bundle seal rewrites or creates.

    Signing the bundle replaces the main executable's signature and writes the
    resource seal beside the executable directory; every other member keeps the
    bytes its own owner projected.
    """
    contents = posixpath.dirname(wrapper.executable_directory)
    return frozenset(
        {
            f"{application}/{wrapper.executable_directory}/{executable}",
            f"{application}/{contents}/{_SEAL_RESOURCES}",
        }
    )


def _run(tool: Path, *arguments: str) -> str:
    result = run_command([str(tool), *arguments], cwd=Path.cwd(), timeout_seconds=900)
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ValueError(f"{tool.name} {arguments[0]} failed ({result.returncode}): {detail[:2000]}")
    # codesign and spctl report on standard error.
    return result.stderr


def _require_tool(tool: Path, name: str) -> None:
    if not tool.is_absolute() or not tool.is_file():
        raise ValueError(f"Supply the configured absolute {name} tool")


def nested_images(bundle: Path, main_executable: Path) -> list[Path]:
    """Return every Mach-O image in ``bundle`` other than its main executable, in path order."""
    return [
        path
        for path in sorted(bundle.rglob("*"))
        if not path.is_symlink() and path != main_executable and macho_image(path)
    ]


@dataclass(frozen=True)
class CodesignSeal:
    """The configured codesign tool and explicit identity that seal a bundle."""

    codesign: Path
    identity: str

    def __post_init__(self) -> None:
        """Refuse an implicit tool or identity before anything is signed."""
        _require_tool(self.codesign, "codesign")
        if not self.identity:
            raise ValueError("Supply an explicit signing identity; '-' selects an ad-hoc local seal")

    def binding(self) -> dict[str, str]:
        """Bind the seal to the exact tool bytes and the identity."""
        return {"codesign": str(self.codesign), "codesign_sha256": digest(self.codesign), "identity": self.identity}

    def seal(self, bundle: Path, main_executable: Path, application_id: str) -> None:
        """Admit every nested image's own signature, sign the bundle last, then verify it."""
        _require_main_executable(bundle, main_executable)
        nested = nested_images(bundle, main_executable)
        if nested:
            # Assembly owns these signatures; the bundle seal hashes them as they are.
            _run(self.codesign, "--verify", "--strict", *(str(path) for path in nested))
        timestamp = "--timestamp=none" if self.identity == "-" else "--timestamp"
        _run(self.codesign, "--force", "--sign", self.identity, "--options", "runtime", timestamp, str(bundle))
        self.verify(bundle, application_id)

    def verify(self, bundle: Path, application_id: str) -> None:
        """Verify the complete seal and that it is this application's hardened seal."""
        verify_seal(self.codesign, bundle, application_id)


def _require_main_executable(bundle: Path, main_executable: Path) -> None:
    info = plistlib.loads((main_executable.parent.parent / "Info.plist").read_bytes())
    if (
        info.get("CFBundleExecutable") != main_executable.name
        or main_executable.parent.parent.parent != bundle
        or not main_executable.is_file()
        or main_executable.is_symlink()
    ):
        raise ValueError("Application bundle lacks the main executable its Info.plist declares")


def verify_seal(codesign: Path, bundle: Path, application_id: str) -> str:
    """Refuse a bundle whose seal is missing, invalid or not this application's; return its details."""
    _require_tool(codesign, "codesign")
    if not bundle.is_dir() or bundle.is_symlink():
        raise ValueError(f"Application bundle is missing: {bundle}")
    _run(codesign, "--verify", "--deep", "--strict", "--verbose=2", str(bundle))
    details = _run(codesign, "--display", "--verbose=2", str(bundle))
    _require_hardened_seal(details.splitlines(), application_id)
    return details


def _require_hardened_seal(lines: list[str], application_id: str) -> None:
    if f"Identifier={application_id}" not in lines:
        raise ValueError("Sealed bundle does not carry the distribution identifier")
    flags = next((line for line in lines if line.startswith("CodeDirectory ")), "")
    if "runtime" not in flags.partition("flags=")[2].partition(" ")[0]:
        raise ValueError("Sealed bundle lacks the hardened runtime")
    if not any(line.startswith("Sealed Resources version=2 ") for line in lines):
        raise ValueError("Sealed bundle carries no version 2 resource seal")
    if not any(line.startswith("Info.plist entries=") for line in lines):
        raise ValueError("Sealed bundle signature does not bind its Info.plist")


_RUNTIME_ROLE = ("--role", "runtime", "--configured-root")
_RUNTIME_START_SECONDS = 60
_RUNTIME_STOP_SECONDS = 30


def _runtime_environment(root: Path) -> dict[str, str]:
    """The minimal environment of a health run: a private root and nothing written beside the bundle."""
    return {"PATH": "/usr/bin:/bin", "CADRUMO_STORAGE_ROOT": str(root), "PYTHONDONTWRITEBYTECODE": "1"}


_STDERR_TAIL_BYTES = 2000


async def _keep_tail(stream: asyncio.StreamReader, tail: bytearray) -> None:
    """Drain `stream` so the role never blocks on a full pipe, keeping only its last bytes."""
    while chunk := await stream.read(4096):
        tail.extend(chunk)
        del tail[:-_STDERR_TAIL_BYTES]


async def _failure(
    process: asyncio.subprocess.Process,
    draining: asyncio.Future[None] | None,
    tail: bytearray,
    message: str,
) -> ValueError:
    """Stops the role, collects what it wrote to standard error and returns the failure."""
    if process.returncode is None:
        process.kill()
    await process.wait()
    if draining is not None:
        await draining
    text = bytes(tail).decode("utf-8", "replace").strip()
    return ValueError(f"{message}; standard error tail: {text}" if text else message)


async def _serve_until_ready(main_executable: Path, root: Path) -> str:
    """Run the runtime role until it reports ready, close its input, require it to stop; return its version.

    The role binds its sockets in the account's per-user transport directory, since the
    platform offers no way to relocate that namespace without weakening its production
    resolution. The sockets are named for the private temporary root, so the run never
    contends with an installed runtime, and the role removes them when it stops. A failure
    carries the last bytes of the role's standard error.
    """
    process = await asyncio.create_subprocess_exec(
        str(main_executable),
        *_RUNTIME_ROLE,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=_runtime_environment(root),
    )
    tail = bytearray()
    draining = asyncio.ensure_future(_keep_tail(process.stderr, tail)) if process.stderr else None
    try:
        if process.stdout is None or process.stdin is None:
            raise ValueError("The runtime role's standard streams are unavailable")
        try:
            line = await asyncio.wait_for(process.stdout.readline(), _RUNTIME_START_SECONDS)
        except TimeoutError:
            raise await _failure(
                process, draining, tail, "Sealed bundle's runtime role did not report ready in time"
            ) from None
        try:
            ready = json.loads(line)
        except ValueError:
            ready = None
        if not isinstance(ready, dict) or ready.get("kind") != "runtime_ready":
            raise await _failure(
                process, draining, tail, f"Sealed bundle's runtime role did not report ready: {line[:300]!r}"
            )
        process.stdin.close()
        try:
            await asyncio.wait_for(process.wait(), _RUNTIME_STOP_SECONDS)
        except TimeoutError:
            raise await _failure(
                process, draining, tail, "Sealed bundle's runtime role did not stop when its input closed"
            ) from None
        return str(ready.get("product_version", ""))
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()
        if draining is not None:
            await draining


def verify_runtime_role(codesign: Path, bundle: Path, application_id: str, *, scratch_root: Path) -> str:
    """Start the sealed bundle's runtime role and require ready and a stop on closed input.

    The seal is verified first, so a bundle that fails its seal is never executed, and
    verified again afterwards, so a run that wrote beneath the bundle fails. The role
    serves a private storage root beneath the build testing directory and stops when its standard input closes.
    """
    verify_seal(codesign, bundle, application_id)
    info = plistlib.loads((bundle / "Contents/Info.plist").read_bytes())
    main_executable = bundle / "Contents/MacOS" / str(info["CFBundleExecutable"])
    with TemporaryDirectory(prefix="cadrumo-health-", dir=scratch_root) as directory:
        version = asyncio.run(_serve_until_ready(main_executable, Path(directory)))
    verify_seal(codesign, bundle, application_id)
    return version


def assess(spctl: Path, bundle: Path) -> str:
    """Return Gatekeeper's execution assessment; an ad-hoc seal is expected to be rejected."""
    _require_tool(spctl, "spctl")
    result = run_command(
        [str(spctl), "--assess", "--type", "execute", "--verbose=2", str(bundle)],
        cwd=Path.cwd(),
        timeout_seconds=300,
    )
    outcome = "accepted" if result.returncode == 0 else f"rejected (exit {result.returncode})"
    detail = " ".join((result.stderr or result.stdout).split())
    return f"{outcome}: {detail[:500]}"


@dataclass(frozen=True)
class PackageTools:
    """Reviewed absolute tools that open a built package without changing it."""

    codesign: Path
    spctl: Path
    hdiutil: Path
    ditto: Path


def _verify_copy(tools: PackageTools, bundle: Path, application_id: str, label: str) -> None:
    verify_seal(tools.codesign, bundle, application_id)
    print(f"[cadrumo:bundle] {label}: seal valid")
    print(f"[cadrumo:bundle] {label}: gatekeeper {assess(tools.spctl, bundle)}")


def _verify_disk_image(
    tools: PackageTools, image: Path, application: str, application_id: str, *, scratch_root: Path
) -> None:
    with TemporaryDirectory(prefix="cadrumo-dmg-", dir=scratch_root) as directory:
        mountpoint = Path(directory) / "volume"
        mountpoint.mkdir()
        _run(
            tools.hdiutil, "attach", "-nobrowse", "-readonly", "-noautoopen", "-mountpoint", str(mountpoint), str(image)
        )
        try:
            _verify_copy(tools, mountpoint / application, application_id, image.name)
        finally:
            detached = run_command([str(tools.hdiutil), "detach", str(mountpoint)], cwd=Path.cwd(), timeout_seconds=120)
            if detached.returncode != 0:
                _run(tools.hdiutil, "detach", "-force", str(mountpoint))


def _verify_archive(
    tools: PackageTools, archive: Path, application: str, application_id: str, *, scratch_root: Path
) -> None:
    with TemporaryDirectory(prefix="cadrumo-zip-", dir=scratch_root) as directory:
        extracted = Path(directory) / "archive"
        _run(tools.ditto, "-x", "-k", str(archive), str(extracted))
        _verify_copy(tools, locate_bundle(extracted, application), application_id, archive.name)


def locate_bundle(root: Path, application: str) -> Path:
    """Return the one ``application`` bundle at ``root`` or beneath its single top-level directory."""
    bundles = [path for path in (root / application, *root.glob(f"*/{application}")) if path.is_dir()]
    if len(bundles) != 1 or bundles[0].is_symlink():
        raise ValueError(f"{root.name} does not hold exactly one {application}")
    return bundles[0]


def verify_packages(
    tools: PackageTools, packages: Sequence[Path], application: str, application_id: str, *, scratch_root: Path
) -> None:
    """Verify the bundle seal inside every built disk image and archive, read-only."""
    for package in packages:
        if package.suffix == ".dmg":
            _verify_disk_image(tools, package, application, application_id, scratch_root=scratch_root)
        elif package.suffix == ".zip":
            _verify_archive(tools, package, application, application_id, scratch_root=scratch_root)
        else:
            raise ValueError(f"No bundle verification is declared for {package.name}")


def main() -> None:
    """Command-line entry for the CPack pre- and post-build verification scripts."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", type=require_enrolled_build, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--codesign", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    staged = commands.add_parser("verify-staging", help="Verify the bundle in a packager's staging copy")
    staged.add_argument("--root", type=Path, required=True)
    built = commands.add_parser("verify-packages", help="Verify the bundle inside each built package")
    built.add_argument("--spctl", type=Path, required=True)
    built.add_argument("--hdiutil", type=Path, required=True)
    built.add_argument("--ditto", type=Path, required=True)
    built.add_argument("packages", type=Path, nargs="+")
    arguments = parser.parse_args()
    scratch_root = build_paths(arguments.build)["testing"]
    scratch_root.mkdir(parents=True, exist_ok=True)
    identity = json.loads(arguments.identity.read_text(encoding="utf-8"))
    application = f"{identity['name']}.app"
    if arguments.command == "verify-staging":
        bundle = locate_bundle(arguments.root, application)
        verify_seal(arguments.codesign, bundle, identity["application_id"])
        print(f"[cadrumo:bundle] staged {application}: seal valid")
        version = verify_runtime_role(arguments.codesign, bundle, identity["application_id"], scratch_root=scratch_root)
        print(f"[cadrumo:bundle] staged {application}: runtime role ready ({version}), seal intact")
    else:
        tools = PackageTools(arguments.codesign, arguments.spctl, arguments.hdiutil, arguments.ditto)
        verify_packages(tools, arguments.packages, application, identity["application_id"], scratch_root=scratch_root)


if __name__ == "__main__":
    main()
