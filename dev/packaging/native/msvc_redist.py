"""Locate the pinned MSVC toolchain's redistributable runtime and prove the copies assembly stages.

The bundled llama-server imports the C++ runtime (``msvcp140.dll``, ``vcruntime140.dll`` and
``vcruntime140_1.dll``). A machine without the Visual C++ redistributable does not have them, and the
program loads from its own directory, not from the interpreter's. The package therefore carries app-local
copies of exactly those three libraries, taken from the redistributable folder of the MSVC toolset the
build selected, never from the search path.

CMake runs this module at configure time with the selected Visual Studio root and toolset version, and
records the folder and each library's SHA-256 in the build toolchain. Assembly then checks the files
against those digests before staging them.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Final, cast

from .hashing import digest

REQUIRED_LIBRARIES: Final = ("msvcp140.dll", "vcruntime140.dll", "vcruntime140_1.dll")
"""The runtime libraries the bundled program imports and the package must therefore carry."""
_VERSION: Final = re.compile(r"(\d+)\.(\d+)\.(\d+)")
_CRT_FOLDER: Final = "Microsoft.VC*.CRT"


class MsvcRedistError(ValueError):
    """The pinned toolchain's redistributable runtime is missing, incomplete or changed."""


def _inventory(directory: Path) -> dict[str, str]:
    missing = [name for name in REQUIRED_LIBRARIES if not (directory / name).is_file()]
    if missing:
        raise MsvcRedistError(f"the MSVC redistributable folder {directory} lacks {', '.join(missing)}")
    return {name: digest(directory / name) for name in REQUIRED_LIBRARIES}


def locate_msvc_redist(visual_studio: Path, msvc_version: str) -> Path:
    """Return the x64 runtime folder of the redistributable that belongs to the selected toolset.

    The redistributable's build number differs from the toolset's, so the toolset's ``major.minor`` line
    selects the folder and the newest build in that line wins.

    Raises:
        MsvcRedistError: The toolset version is unreadable, or no folder of its line holds all three libraries.
    """
    selected = _VERSION.fullmatch(msvc_version)
    if selected is None:
        raise MsvcRedistError(f"the selected MSVC toolset version is not major.minor.build: {msvc_version!r}")
    line = selected.groups()[:2]
    root = visual_studio / "VC" / "Redist" / "MSVC"
    candidates: list[tuple[tuple[int, ...], Path]] = []
    incomplete: list[str] = []
    for child in sorted(root.iterdir()) if root.is_dir() else []:
        version = _VERSION.fullmatch(child.name)
        if version is None or version.groups()[:2] != line or not child.is_dir():
            continue
        for crt in sorted((child / "x64").glob(_CRT_FOLDER)):
            missing = [name for name in REQUIRED_LIBRARIES if not (crt / name).is_file()]
            if missing:
                incomplete.append(f"{crt} lacks {', '.join(missing)}")
            else:
                candidates.append((tuple(int(part) for part in version.groups()), crt))
    if not candidates:
        raise MsvcRedistError(
            f"no x64 redistributable folder of the MSVC {'.'.join(line)} line holds "
            f"{', '.join(REQUIRED_LIBRARIES)} under {root}" + (f"; {'; '.join(incomplete)}" if incomplete else "")
        )
    return max(candidates, key=lambda item: item[0])[1]


def redist_record(visual_studio: Path, msvc_version: str) -> dict[str, object]:
    """Describe the located folder as the build toolchain records it: its path and each library's SHA-256."""
    directory = locate_msvc_redist(visual_studio, msvc_version)
    return {"directory": directory.as_posix(), "sha256": _inventory(directory)}


def verified_redist(record: object) -> dict[str, Path]:
    """Return the three libraries by name after proving each still matches the digest recorded at configure time.

    Raises:
        MsvcRedistError: The record is absent or malformed, or a library is missing or changed.
    """
    if not isinstance(record, dict):
        raise MsvcRedistError("the build toolchain records no MSVC redistributable; reconfigure CMake")
    fields = cast("Mapping[str, object]", record)
    directory, hashes = fields.get("directory"), fields.get("sha256")
    if not isinstance(directory, str) or not Path(directory).is_absolute() or not isinstance(hashes, dict):
        raise MsvcRedistError("the recorded MSVC redistributable is malformed; reconfigure CMake")
    recorded = cast("Mapping[str, object]", hashes)
    if sorted(recorded) != sorted(REQUIRED_LIBRARIES):
        raise MsvcRedistError(f"the recorded MSVC redistributable must name exactly {', '.join(REQUIRED_LIBRARIES)}")
    found = _inventory(Path(directory))
    if found != recorded:
        changed = sorted(name for name in REQUIRED_LIBRARIES if found[name] != recorded[name])
        raise MsvcRedistError(
            f"the MSVC redistributable differs from its configured digests ({', '.join(changed)}); reconfigure CMake"
        )
    return {name: Path(directory) / name for name in REQUIRED_LIBRARIES}


def main(argv: list[str] | None = None) -> int:
    """Print the located redistributable as JSON, or refuse with a typed error."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--visual-studio", type=Path, required=True, help="the selected Visual Studio root")
    parser.add_argument("--msvc-version", required=True, help="the selected MSVC toolset version")
    arguments = parser.parse_args(argv)
    try:
        record = redist_record(arguments.visual_studio, arguments.msvc_version)
    except MsvcRedistError as error:
        print(f"msvc-redist: {error}", file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(record))
    return 0


if __name__ == "__main__":
    sys.exit(main())
