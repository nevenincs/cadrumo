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


def locations(root: Path) -> dict[str, object]:
    """Resolve each relocatable location and name the ones outside ``root``."""
    from cadrumo.application.provisioning_browser import playwright_browsers_root
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


def credentials() -> list[dict[str, object]]:
    """Return the Cadrumo credential entries by target, type and user name only."""
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    count = ctypes.c_uint32(0)
    entries = ctypes.POINTER(ctypes.POINTER(_Credential))()
    if not advapi.CredEnumerateW(None, 0, ctypes.byref(count), ctypes.byref(entries)):
        return []
    try:
        found = [
            {
                "target": str(entries[index].contents.TargetName or ""),
                "type": int(entries[index].contents.Type),
                "user": str(entries[index].contents.UserName or ""),
            }
            for index in range(count.value)
        ]
    finally:
        advapi.CredFree(entries)
    return sorted(
        (entry for entry in found if "cadrumo" in f"{entry['target']} {entry['user']}".lower()),
        key=lambda entry: (str(entry["target"]), int(entry["type"]), str(entry["user"])),
    )


def delete(wanted: list[dict[str, object]]) -> list[dict[str, object]]:
    """Delete exactly the named entries and return those still present."""
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    for entry in wanted:
        advapi.CredDeleteW(str(entry["target"]), int(entry["type"]), 0)
    pairs = {(str(entry["target"]), int(entry["type"])) for entry in wanted}
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
