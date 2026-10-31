"""Inside-out bundle sealing and seal verification of every bundle copy."""

from __future__ import annotations

import plistlib
import shutil
import sys
from pathlib import Path

import pytest

from ...command_execution import run_command
from ..identity import identity
from ..layout import application_bundle, load_layout
from ..macos_bundle import (
    CodesignSeal,
    PackageTools,
    locate_bundle,
    nested_images,
    sealed_members,
    verify_packages,
    verify_seal,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_CODESIGN = Path("/usr/bin/codesign")
_THIN_ARM64 = b"\xcf\xfa\xed\xfe" + b"\0" * 28
_UNIVERSAL = b"\xca\xfe\xba\xbe" + b"\0" * 28

# A stand-in codesign that records each invocation and reports a hardened seal.
_RECORDING_CODESIGN = """#!/bin/sh
printf '%s\\n' "$*" >> "{log}"
case "$1" in
  --display)
    printf 'Identifier={application_id}\\n' >&2
    printf 'CodeDirectory v=20500 size=304 flags=0x10002(adhoc,runtime) hashes=3+3 location=embedded\\n' >&2
    printf 'Info.plist entries=13\\n' >&2
    printf 'Sealed Resources version=2 rules=13 files=2\\n' >&2 ;;
esac
exit 0
"""


def _bundle(tmp_path: Path, bundle_id: str | None = None) -> tuple[Path, Path]:
    product = identity("macos-arm64")
    bundle = tmp_path / "stage" / f"{product.name}.app"
    contents = bundle / "Contents"
    (contents / "MacOS").mkdir(parents=True)
    (contents / "Resources/app/bin").mkdir(parents=True)
    (contents / "Resources/app/data").mkdir(parents=True)
    main = contents / "MacOS/cadrumo"
    main.write_bytes(_THIN_ARM64)
    (contents / "Resources/app/data/build.json").write_text("{}", encoding="utf-8")
    info = {"CFBundleIdentifier": bundle_id or product.application_id, "CFBundleExecutable": "cadrumo"}
    (contents / "Info.plist").write_bytes(plistlib.dumps(info))
    return bundle, main


def _recording_codesign(tmp_path: Path) -> tuple[Path, Path]:
    log = tmp_path / "codesign.log"
    tool = tmp_path / "tools/codesign"
    tool.parent.mkdir()
    tool.write_text(
        _RECORDING_CODESIGN.format(log=log, application_id=identity("macos-arm64").application_id), encoding="utf-8"
    )
    tool.chmod(0o755)
    return tool, log


def test_sealed_members_are_the_main_executable_and_the_resource_seal() -> None:
    wrapper = application_bundle(load_layout("macos-arm64"))
    assert wrapper is not None
    assert sealed_members("Cadrumo.app", wrapper, "cadrumo") == {
        "Cadrumo.app/Contents/MacOS/cadrumo",
        "Cadrumo.app/Contents/_CodeSignature/CodeResources",
    }


def test_nested_images_are_every_other_macho_and_no_data(tmp_path: Path) -> None:
    bundle, main = _bundle(tmp_path)
    payload = bundle / "Contents/Resources/app"
    (payload / "python").write_bytes(_THIN_ARM64)
    (payload / "bin/libpython.dylib").write_bytes(_UNIVERSAL)
    (payload / "data/notes.txt").write_text("not code", encoding="utf-8")
    (payload / "bin/linked").symlink_to(payload / "python")
    assert nested_images(bundle, main) == [payload / "bin/libpython.dylib", payload / "python"]


def test_seal_admits_nested_images_before_it_signs_the_bundle_last(tmp_path: Path) -> None:
    bundle, main = _bundle(tmp_path)
    nested = bundle / "Contents/Resources/app/bin/libpython.dylib"
    nested.write_bytes(_THIN_ARM64)
    tool, log = _recording_codesign(tmp_path)
    CodesignSeal(tool, "-").seal(bundle, main, identity("macos-arm64").application_id)
    calls = log.read_text(encoding="utf-8").splitlines()
    assert calls == [
        f"--verify --strict {nested}",
        f"--force --sign - --options runtime --timestamp=none {bundle}",
        f"--verify --deep --strict --verbose=2 {bundle}",
        f"--display --verbose=2 {bundle}",
    ]
    # Nested images keep the signatures their bytes were inventoried with.
    assert not any(call.startswith("--force") and str(nested) in call for call in calls)


def test_seal_refuses_a_main_executable_its_info_plist_does_not_declare(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    other = bundle / "Contents/MacOS/other"
    other.write_bytes(_THIN_ARM64)
    tool, log = _recording_codesign(tmp_path)
    with pytest.raises(ValueError, match="main executable"):
        CodesignSeal(tool, "-").seal(bundle, other, identity("macos-arm64").application_id)
    assert not log.exists()


def test_verification_refuses_another_identity_or_a_seal_without_resources(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    tool, _ = _recording_codesign(tmp_path)
    with pytest.raises(ValueError, match="distribution identifier"):
        verify_seal(tool, bundle, "md.neve.other")
    tool.write_text(
        tool.read_text(encoding="utf-8").replace(
            "Sealed Resources version=2 rules=13 files=2", "Sealed Resources=none"
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="resource seal"):
        verify_seal(tool, bundle, identity("macos-arm64").application_id)


def test_seal_requires_an_explicit_identity_and_tool(tmp_path: Path) -> None:
    tool, _ = _recording_codesign(tmp_path)
    with pytest.raises(ValueError, match="explicit signing identity"):
        CodesignSeal(tool, "")
    with pytest.raises(ValueError, match="codesign tool"):
        CodesignSeal(Path("codesign"), "-")


def test_package_verification_locates_one_bundle_and_refuses_undeclared_formats(tmp_path: Path) -> None:
    bundle, _ = _bundle(tmp_path)
    assert locate_bundle(tmp_path / "stage", bundle.name) == bundle
    assert locate_bundle(tmp_path, bundle.name) == bundle
    (tmp_path / "second" / bundle.name).mkdir(parents=True)
    with pytest.raises(ValueError, match="exactly one"):
        locate_bundle(tmp_path, bundle.name)
    tool, _ = _recording_codesign(tmp_path)
    tools = PackageTools(tool, tool, tool, tool)
    with pytest.raises(ValueError, match="No bundle verification"):
        verify_packages(tools, [tmp_path / "package.pkg"], bundle.name, identity("macos-arm64").application_id)


@pytest.mark.skipif(sys.platform != "darwin", reason="Requires the native macOS codesign tool")
def test_ad_hoc_seal_is_inside_out_complete_and_breaks_on_later_change(tmp_path: Path) -> None:
    product = identity("macos-arm64")
    bundle, main = _bundle(tmp_path)
    # Signed system images stand in for the launcher and a nested image; nothing runs them.
    shutil.copyfile("/usr/bin/true", main)
    nested = bundle / "Contents/Resources/app/bin/tool"
    shutil.copyfile("/usr/bin/true", nested)
    unsigned = run_command([str(_CODESIGN), "--remove-signature", str(nested)], cwd=tmp_path)
    assert unsigned.returncode == 0, unsigned.stderr
    seal = CodesignSeal(_CODESIGN, "-")
    with pytest.raises(ValueError, match="codesign --verify failed"):
        seal.seal(bundle, main, product.application_id)
    assert not (bundle / "Contents/_CodeSignature").exists()
    signed = run_command([str(_CODESIGN), "--force", "--sign", "-", str(nested)], cwd=tmp_path)
    assert signed.returncode == 0, signed.stderr
    nested_bytes = nested.read_bytes()
    seal.seal(bundle, main, product.application_id)
    assert nested.read_bytes() == nested_bytes
    sealed = plistlib.loads((bundle / "Contents/_CodeSignature/CodeResources").read_bytes())
    assert {"Resources/app/data/build.json", "Resources/app/bin/tool"} <= sealed["files2"].keys()
    details = verify_seal(_CODESIGN, bundle, product.application_id)
    assert "Info.plist entries=" in details
    # A copy that preserves only bytes and modes keeps the seal valid.
    copy = tmp_path / "copy" / bundle.name
    shutil.copytree(bundle, copy, copy_function=shutil.copyfile)
    for source in bundle.rglob("*"):
        (copy / source.relative_to(bundle)).chmod(source.stat().st_mode & 0o777)
    verify_seal(_CODESIGN, copy, product.application_id)
    # Any write beneath the bundle after sealing is a broken seal, not a valid bundle.
    (copy / "Contents/Resources/app/data/build.json").write_text('{"changed": true}', encoding="utf-8")
    with pytest.raises(ValueError, match="codesign --verify failed"):
        verify_seal(_CODESIGN, copy, product.application_id)
    (bundle / "Contents/_CodeSignature/CodeResources").unlink()
    with pytest.raises(ValueError, match="codesign --verify failed"):
        verify_seal(_CODESIGN, bundle, product.application_id)
