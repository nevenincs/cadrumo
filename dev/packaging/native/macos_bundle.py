"""Seal the staged macOS application bundle in a native package's own staging copy.

The installation stage stays the receipt-bound projection. CPack copies it before
it builds an image; this helper signs that copy, so the bundle seal never changes
a receipt-owned file. Nested images were already sealed during package assembly.
"""

from __future__ import annotations

import argparse
import json
import plistlib
from pathlib import Path

from ..command_execution import run_command
from .installation import member
from .layout import application_bundle, load_layout


def _bundle(root: Path, identity: dict[str, str]) -> Path:
    bundle = member(root, f"{identity['name']}.app")
    if not bundle.is_dir():
        raise ValueError(f"Packaging staging lacks the application bundle {bundle.name}")
    wrapper = application_bundle(load_layout(identity["target"]))
    if wrapper is None:
        raise ValueError(f"{identity['target']} declares no application bundle")
    info = plistlib.loads(member(bundle, "Contents/Info.plist").read_bytes())
    if info.get("CFBundleIdentifier") != identity["application_id"]:
        raise ValueError("Application bundle identifier differs from the distribution identity")
    executable = member(bundle, f"{wrapper.executable_directory}/{info['CFBundleExecutable']}")
    if not executable.is_file():
        raise ValueError("Application bundle lacks its main executable")
    return bundle


def _run(*arguments: str) -> str:
    result = run_command(arguments, cwd=Path(arguments[-1]).parent, timeout_seconds=600)
    if result.returncode != 0:
        raise ValueError(f"{Path(arguments[0]).name} failed ({result.returncode}): {result.stderr.strip()}")
    # codesign reports on standard error.
    return result.stderr


def sign(root: Path, identity_file: Path, codesign: Path, signing_identity: str) -> Path:
    """Sign the bundle with the hardened runtime, then verify the complete seal."""
    if not codesign.is_absolute() or not codesign.is_file():
        raise ValueError("Supply the configured absolute codesign tool")
    if not signing_identity:
        raise ValueError("Supply an explicit signing identity; '-' selects an ad-hoc local seal")
    identity = json.loads(identity_file.read_text(encoding="utf-8"))
    bundle = _bundle(root, identity)
    timestamp = ["--timestamp=none"] if signing_identity == "-" else ["--timestamp"]
    _run(str(codesign), "--force", "--sign", signing_identity, "--options", "runtime", *timestamp, str(bundle))
    _run(str(codesign), "--verify", "--strict", "--deep", "--verbose=2", str(bundle))
    details = _run(str(codesign), "--display", "--verbose=2", str(bundle))
    if f"Identifier={identity['application_id']}\n" not in details or "flags=" not in details:
        raise ValueError("Sealed bundle does not carry the distribution identifier")
    if "runtime" not in details.split("flags=", 1)[1].split("\n", 1)[0]:
        raise ValueError("Sealed bundle lacks the hardened runtime")
    return bundle


def main() -> None:
    """Command-line entry for the CPack pre-build script."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--codesign", type=Path, required=True)
    parser.add_argument("--signing-identity", required=True)
    arguments = parser.parse_args()
    bundle = sign(arguments.root, arguments.identity, arguments.codesign, arguments.signing_identity)
    print(f"[cadrumo:bundle] sealed {bundle.name}")


if __name__ == "__main__":
    main()
