"""Compile and inspect scoped MSI products without installing them."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from defusedxml import ElementTree

from ..command_execution import run_command
from .build_paths import build_paths
from .hashing import digest
from .installation import member
from .windows_msi import MAINTENANCE_GATE, WIX_NAMESPACE, author
from .windows_msi_database import verify_upgrade_order

_NS = {"w": WIX_NAMESPACE}


def _run(wix: Path, arguments: list[str], directory: Path) -> str:
    result = run_command([str(wix), *arguments], cwd=directory, timeout_seconds=300)
    if result.returncode:
        raise ValueError(f"WiX failed ({result.returncode}): {result.stdout}{result.stderr}")
    return result.stdout.strip()


def verify_database(source: Path, database: Path) -> None:
    """Check actual decompiled MSI identity, installation gate and upgrade ownership."""
    original = ElementTree.parse(source).find("w:Package", _NS)
    tree = ElementTree.parse(database)
    package = tree.find("w:Package", _NS)
    if original is None or package is None:
        raise ValueError("MSI database lacks its package identity")
    for key in ("ProductCode", "UpgradeCode"):
        if UUID(package.attrib[key]) != UUID(original.attrib[key]):
            raise ValueError(f"MSI database {key} differs from its source")
    if package.attrib["Version"] != original.attrib["Version"]:
        raise ValueError("MSI database version differs from its source")
    conditions = tree.findall(".//w:Launch", _NS)
    if not any(item.attrib == {"Condition": "0", "Message": MAINTENANCE_GATE} for item in conditions):
        raise ValueError("MSI database lost its unconditional installation gate")
    upgrade = tree.find(".//w:MajorUpgrade", _NS)
    if original.attrib["UpgradeStrategy"] == "none":
        if upgrade is not None or tree.find(".//w:RemoveExistingProducts", _NS) is not None:
            raise ValueError("Version MSI schedules removal of another product")
    elif upgrade is None:
        raise ValueError("Registration MSI lost its major upgrade")


def compile_products(build: Path, identity: Path, wix: Path, desktop: str | None = None) -> None:
    """Publish four gated products and a hash receipt only after all databases pass."""
    wix = wix.resolve(strict=True)
    sources = author(build, identity, desktop)
    paths = build_paths(build)
    directory = member(paths["packages"], "msi")
    directory.mkdir(parents=True, exist_ok=True)
    receipt = member(directory, "compiled.json")
    # A failed retry must not leave an earlier receipt presenting this run as successful.
    receipt.unlink(missing_ok=True)
    version = _run(wix, ["--version"], build)
    if not version.split(".", 1)[0].isdigit() or int(version.split(".", 1)[0]) < 5:
        raise ValueError("Scoped MSI products require WiX 5 or newer")
    inputs = {name: digest(path) for name, path in sources.items()}
    authoring = member(paths["installation_metadata"], "wix/authoring.json")
    authoring_hash = digest(authoring)
    with TemporaryDirectory(prefix="compile-", dir=directory) as temporary:
        work = Path(temporary)
        artifacts = {}
        for name, source in sources.items():
            artifact = work / Path(name).with_suffix(".msi").name
            _run(wix, ["build", "-arch", "x64", "-wx", "-o", str(artifact), str(source)], work)
            database = work / name
            _run(wix, ["msi", "decompile", "-o", str(database), str(artifact)], work)
            verify_database(source, database)
            verify_upgrade_order(artifact, version_product=source.stem.endswith("-version"))
            artifacts[artifact.name] = digest(artifact)
        # Re-admit the payload after compilation, detecting a concurrently changed stage.
        author(build, identity, desktop)
        if inputs != {name: digest(path) for name, path in sources.items()} or digest(authoring) != authoring_hash:
            raise ValueError("MSI inputs changed during compilation")
        for name in artifacts:
            os.replace(work / name, member(directory, name))
        document = {
            "installable": False,
            "compiler": {"path": str(wix), "version": version},
            "authoring_sha256": authoring_hash,
            "sources": inputs,
            "artifacts": artifacts,
        }
        pending = work / "compiled.json"
        pending.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
        os.replace(pending, receipt)


def verify_products(build: Path, identity: Path, desktop: str | None = None) -> None:
    """Reject stale or altered build artifacts against the current admitted payload."""
    sources = author(build, identity, desktop)
    paths = build_paths(build)
    directory = member(paths["packages"], "msi")
    receipt = json.loads(member(directory, "compiled.json").read_text(encoding="utf-8"))
    expected = {Path(name).with_suffix(".msi").name for name in sources}
    if receipt["installable"] is not False or set(receipt["artifacts"]) != expected:
        raise ValueError("MSI compilation receipt has invalid ownership or installation state")
    if receipt["sources"] != {name: digest(path) for name, path in sources.items()}:
        raise ValueError("MSI compilation receipt has stale sources")
    if receipt["authoring_sha256"] != digest(member(paths["installation_metadata"], "wix/authoring.json")):
        raise ValueError("MSI compilation receipt has stale payload identity")
    for name, checksum in receipt["artifacts"].items():
        if digest(member(directory, name)) != checksum:
            raise ValueError(f"MSI artifact has changed: {name}")


def main() -> None:
    """Expose build, verification and the still-closed native installation boundary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "verify", "check-installation"))
    parser.add_argument("--build", type=Path, required=True)
    parser.add_argument("--identity", type=Path, required=True)
    parser.add_argument("--desktop")
    parser.add_argument("--wix", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "check-installation":
            raise ValueError(
                f"{MAINTENANCE_GATE} Required: transaction publication, scope-conflict admission, "
                "same-version integrity, anchor retention, safe in-use removal; manager IPC/readiness, "
                "cutover/rollback, login opt-out and uninstall detection. Acceptance requires a disposable "
                "interactive Windows runner and two genuinely built distinct releases; Session 0 is insufficient. "
                "Signing remains a release prerequisite."
            )
        if args.command == "build":
            if args.wix is None or not args.wix.is_file():
                raise ValueError("Set CADRUMO_WIX_EXECUTABLE to an installed WiX 5+ executable")
            compile_products(args.build.resolve(), args.identity, args.wix, args.desktop)
        else:
            verify_products(args.build.resolve(), args.identity, args.desktop)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
