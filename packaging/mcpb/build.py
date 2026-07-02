"""Assemble the aeat MCP console as an ``.mcpb`` Desktop Extension bundle.

ADR R8's distribution artefact: a signed ``.mcpb`` bundle a non-technical
taxpayer installs into their MCP client with one click, so "the user's own
client" is a real path rather than a manual JSON-config chore. The bundle
points at the ``aeat-mcp`` console script, which requires the ``aeat[agent]``
extra installed on-host beside the encrypted store (the server must run
locally; a remote-hosted server would defeat the on-host-data posture).

This script is deliberately dependency-light: it validates the manifest,
stages it, and zips the ``.mcpb`` (a zip with a ``.mcpb`` extension, per the
Desktop Extension format). SIGNING is honest: the bundle is signed only when a
signing identity is actually available (the ``mcpb`` CLI plus a configured
certificate); absent that, the script emits an UNSIGNED bundle and says so
plainly — it never fabricates a signature. An unsigned bundle installs with an
"unverified publisher" warning; signing is the operator's release step, not a
build-time fake.

Run it as a script (the repo-root ``packaging/`` directory intentionally shadows
nothing importable — the name collides with the installed PyPA ``packaging``
library, so this is never imported as ``packaging.mcpb``)::

    python packaging/mcpb/build.py            # build dist/aeat.mcpb (unsigned unless mcpb+identity present)
    python packaging/mcpb/build.py --check     # validate the manifest only, write nothing
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_MANIFEST = _HERE / "manifest.json"
_REQUIRED_TOP_LEVEL = ("manifest_version", "name", "version", "description", "server")
_REQUIRED_SERVER = ("type", "mcp_config")


class ManifestError(ValueError):
    """Raised when the bundle manifest is missing a required field."""


def load_manifest() -> dict[str, object]:
    """Load and validate ``manifest.json`` against the required-field contract."""
    data = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ManifestError("manifest.json must be a JSON object")
    missing = [key for key in _REQUIRED_TOP_LEVEL if key not in data]
    if missing:
        raise ManifestError(f"manifest.json missing required fields: {', '.join(missing)}")
    server = data["server"]
    if not isinstance(server, dict) or any(key not in server for key in _REQUIRED_SERVER):
        raise ManifestError("manifest.json 'server' must carry 'type' and 'mcp_config'")
    mcp_config = server["mcp_config"]
    if not isinstance(mcp_config, dict) or "command" not in mcp_config:
        raise ManifestError("manifest.json 'server.mcp_config' must carry a 'command'")
    return data


def _signing_available() -> bool:
    """True only when the ``mcpb`` CLI is on PATH (a genuine signing path exists)."""
    return shutil.which("mcpb") is not None


def _sign(bundle: Path) -> bool:
    """Sign ``bundle`` with the ``mcpb`` CLI; return True only on a real success.

    Never fabricates a signature: if the CLI is absent or signing fails (no
    configured identity), it reports and returns False, leaving the unsigned
    bundle in place.
    """
    if not _signing_available():
        return False
    completed = subprocess.run(  # noqa: S603
        ["mcpb", "sign", str(bundle)],  # noqa: S607
        capture_output=True,
        text=True,
        check=False,
        stdin=subprocess.DEVNULL,
    )
    if completed.returncode != 0:
        sys.stderr.write(f"mcpb sign failed (no identity?); shipping unsigned:\n{completed.stderr}\n")
        return False
    return True


def build(*, dist_dir: Path | None = None) -> Path:
    """Build ``dist/aeat.mcpb`` from the manifest and return its path."""
    manifest = load_manifest()
    dist = dist_dir if dist_dir is not None else _HERE.parents[1] / "dist"
    dist.mkdir(parents=True, exist_ok=True)
    bundle = dist / "aeat.mcpb"
    with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))
    signed = _sign(bundle)
    state = "signed" if signed else "UNSIGNED (no signing identity on this host)"
    sys.stdout.write(f"built {bundle} [{state}]\n")
    return bundle


def main(argv: list[str] | None = None) -> int:
    """CLI entry: ``--check`` validates the manifest; default builds the bundle."""
    parser = argparse.ArgumentParser(description="Build the aeat .mcpb Desktop Extension.")
    parser.add_argument("--check", action="store_true", help="Validate the manifest only; write nothing.")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest()
    except ManifestError as exc:
        sys.stderr.write(f"manifest invalid: {exc}\n")
        return 1
    if args.check:
        sys.stdout.write(f"manifest.json valid: {manifest['name']} {manifest['version']}\n")
        return 0
    build()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
