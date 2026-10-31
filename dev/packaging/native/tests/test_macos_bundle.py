"""Bundle sealing against the real codesign tool, on a synthetic bundle copy."""

from __future__ import annotations

import json
import plistlib
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from ...command_execution import run_command
from ..identity import identity
from ..macos_bundle import sign

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CODESIGN = Path("/usr/bin/codesign")


def _staging(tmp_path: Path, bundle_id: str | None = None) -> tuple[Path, Path]:
    product = identity("macos-arm64")
    identity_file = tmp_path / "identity.json"
    identity_file.write_text(json.dumps(asdict(product)), encoding="utf-8")
    root = tmp_path / "cpack-staging"
    contents = root / f"{product.name}.app/Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources/app/data").mkdir(parents=True)
    # Any thin or universal Mach-O stands in for the launcher; its seal is replaced.
    shutil.copyfile("/usr/bin/true", contents / "MacOS/cadrumo")
    (contents / "MacOS/cadrumo").chmod(0o755)
    (contents / "Resources/app/data/build.json").write_text("{}", encoding="utf-8")
    info = {"CFBundleIdentifier": bundle_id or product.application_id, "CFBundleExecutable": "cadrumo"}
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    return root, identity_file


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires the native macOS codesign tool")
def test_ad_hoc_seal_covers_the_nested_payload_with_the_hardened_runtime(tmp_path: Path) -> None:
    root, identity_file = _staging(tmp_path)
    bundle = sign(root, identity_file, _CODESIGN, "-")
    assert (bundle / "Contents/_CodeSignature/CodeResources").is_file()
    sealed = plistlib.loads((bundle / "Contents/_CodeSignature/CodeResources").read_bytes())
    assert "Resources/app/data/build.json" in sealed["files2"]
    # A change beneath the payload after sealing breaks the bundle's verification.
    (bundle / "Contents/Resources/app/data/build.json").write_text('{"changed": true}', encoding="utf-8")
    check = run_command([str(_CODESIGN), "--verify", "--strict", "--deep", str(bundle)], cwd=tmp_path)
    assert check.returncode != 0
    assert "modified" in check.stderr or "sealed resource" in check.stderr


def test_seal_refuses_a_bundle_of_another_identity(tmp_path: Path) -> None:
    root, identity_file = _staging(tmp_path, bundle_id="md.neve.other")
    with pytest.raises(ValueError, match="identifier differs"):
        sign(root, identity_file, _CODESIGN, "-")


def test_seal_requires_an_explicit_identity_and_tool(tmp_path: Path) -> None:
    root, identity_file = _staging(tmp_path)
    with pytest.raises(ValueError, match="explicit signing identity"):
        sign(root, identity_file, _CODESIGN, "")
    with pytest.raises(ValueError, match="codesign tool"):
        sign(root, identity_file, Path("codesign"), "-")
