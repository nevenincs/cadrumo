"""Read-only facts for the packaged setup acceptance, under the packaged interpreter.

``locations ROOT`` resolves every root-derived storage location, the browser
download root and the temporary directory as this environment's Cadrumo would,
and names those outside ``ROOT``. ``credentials`` lists the Windows credential
store entries whose target or user name mentions Cadrumo, without reading any
secret. ``delete`` removes the (target, type) pairs given as JSON on stdin and
lists what is still present. Output is one JSON document on stdout.
"""

from __future__ import annotations

import ctypes
import json
import os
import sys
from pathlib import Path
from typing import TypedDict


def locations(root: Path) -> dict[str, object]:
    """Resolve each relocatable location and name the ones outside ``root``."""
    from cadrumo.application.browser_location import playwright_browsers_root
    from cadrumo.core.storage_taxonomy_locations import ROOT_DERIVED_STORAGE_LOCATIONS, storage_path

    resolved = {location.category.value: storage_path(location.category) for location in ROOT_DERIVED_STORAGE_LOCATIONS}
    resolved["playwright_browsers_root"] = playwright_browsers_root()
    for name in ("TEMP", "TMP", "LOCALAPPDATA", "APPDATA"):
        resolved[name] = Path(os.environ[name])
    base = root.resolve()
    return {
        "resolved": {name: str(path) for name, path in sorted(resolved.items())},
        "outside": sorted(name for name, path in resolved.items() if not path.resolve().is_relative_to(base)),
    }


class _Credential(ctypes.Structure):
    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", ctypes.c_uint64),
        ("CredentialBlobSize", ctypes.c_uint32),
        ("CredentialBlob", ctypes.c_void_p),
        ("Persist", ctypes.c_uint32),
        ("AttributeCount", ctypes.c_uint32),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]


class CredentialEntry(TypedDict):
    """One credential store entry, named without its secret."""

    target: str
    type: int
    user: str


def credentials() -> list[CredentialEntry]:
    """Return the Cadrumo credential entries by target, type and user name only."""
    if sys.platform != "win32":
        raise SystemExit("the credential store probe requires Windows")
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    count = ctypes.c_uint32(0)
    entries = ctypes.POINTER(ctypes.POINTER(_Credential))()
    if not advapi.CredEnumerateW(None, 0, ctypes.byref(count), ctypes.byref(entries)):
        return []
    try:
        found = [
            CredentialEntry(
                target=str(entries[index].contents.TargetName or ""),
                type=int(entries[index].contents.Type),
                user=str(entries[index].contents.UserName or ""),
            )
            for index in range(count.value)
        ]
    finally:
        advapi.CredFree(entries)
    return sorted(
        (entry for entry in found if "cadrumo" in f"{entry['target']} {entry['user']}".lower()),
        key=lambda entry: (entry["target"], entry["type"], entry["user"]),
    )


def _wanted_pairs(wanted: object) -> set[tuple[str, int]]:
    """Read the (target, type) pairs of a JSON entry list, refusing any other shape."""
    if not isinstance(wanted, list):
        raise SystemExit("delete expects a JSON list of credential entries")
    pairs: set[tuple[str, int]] = set()
    for entry in wanted:
        if not isinstance(entry, dict):
            raise SystemExit(f"delete expects credential entries, got {entry!r}")
        target = entry.get("target")
        kind = entry.get("type")
        if not isinstance(target, str) or not isinstance(kind, int) or isinstance(kind, bool):
            raise SystemExit(f"a credential entry needs a string target and an integer type, got {entry!r}")
        pairs.add((target, kind))
    return pairs


def delete(wanted: object) -> list[CredentialEntry]:
    """Delete exactly the named entries and return those still present."""
    if sys.platform != "win32":
        raise SystemExit("the credential store probe requires Windows")
    pairs = _wanted_pairs(wanted)
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    for target, kind in sorted(pairs):
        advapi.CredDeleteW(target, kind, 0)
    return [entry for entry in credentials() if (entry["target"], entry["type"]) in pairs]


def main() -> None:
    """Answer one command."""
    command = sys.argv[1]
    if command == "locations":
        answer: object = locations(Path(sys.argv[2]))
    elif command == "credentials":
        answer = credentials()
    elif command == "delete":
        answer = delete(json.loads(sys.stdin.read()))
    else:
        raise SystemExit(f"unknown command {command!r}")
    sys.stdout.write(json.dumps(answer) + "\n")


if __name__ == "__main__":
    main()
