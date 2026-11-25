"""The identity-only property list the desktop embeds and the bundle's full one share one source."""

from __future__ import annotations

import plistlib
import sys
from dataclasses import asdict
from pathlib import Path

import pytest

from .. import identity as identity_module
from ..identity import identity
from ..macos_info import DESKTOP_INFO_PLIST_NAME, render_identity_plist

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_EXCLUDED = {"CFBundleExecutable", "CFBundleIconFile", "CFBundlePackageType"}


def test_identity_plist_carries_exactly_the_identity_keys() -> None:
    value = asdict(identity("macos-arm64"))
    parsed = plistlib.loads(render_identity_plist(value))
    assert set(parsed) == {
        "CFBundleIdentifier",
        "CFBundleName",
        "CFBundleDisplayName",
        "CFBundleShortVersionString",
        "CFBundleVersion",
        "LSMinimumSystemVersion",
        "NSHighResolutionCapable",
        "LSApplicationCategoryType",
    }
    assert not _EXCLUDED & set(parsed)
    assert parsed["CFBundleIdentifier"] == value["application_id"]
    assert parsed["CFBundleShortVersionString"] == value["version"]
    assert parsed["LSMinimumSystemVersion"] == value["compatibility_floor"].removeprefix("macos-")
    assert parsed["NSHighResolutionCapable"] is True


def test_preview_channel_identity_reaches_the_plist() -> None:
    stable = plistlib.loads(render_identity_plist(asdict(identity("macos-arm64"))))
    preview = plistlib.loads(render_identity_plist(asdict(identity("macos-arm64", "preview"))))
    assert preview["CFBundleIdentifier"] == stable["CFBundleIdentifier"] + ".preview"
    assert preview["CFBundleName"] != stable["CFBundleName"]


def test_identity_command_writes_the_plist_only_for_macos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for target, written in (("macos-arm64", True), ("linux-x86-64", False)):
        output = tmp_path / target
        monkeypatch.setattr(identity_module, "require_enrolled_output", lambda text: Path(text))
        monkeypatch.setattr(sys, "argv", ["identity", "--target", target, "--output", str(output)])
        identity_module.main()
        assert (output / DESKTOP_INFO_PLIST_NAME).is_file() is written
        assert (output / "identity.json").is_file()
    first = (tmp_path / "macos-arm64" / DESKTOP_INFO_PLIST_NAME).read_bytes()
    assert plistlib.loads(first)["CFBundleName"]
