"""Unsigned bundle metadata checks use synthetic payloads, never native login registration."""

from __future__ import annotations

import json
import plistlib
from dataclasses import replace
from pathlib import Path

import pytest

from dev.packaging.tests.test_native_installation import bundle_fixture, payload_fixture

from ..identity import identity
from ..installation import member, prepare, verify_inventory
from ..layout import application_bundle, application_images, load_layout
from ..macos_launchagent import author_agent, verify_agent

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize("channel", ["stable", "preview"])
def test_agent_uses_projected_identity_and_accepted_profile(channel: str) -> None:
    product = identity("macos-arm64", channel)
    layout = load_layout("macos-arm64")
    manager = next(image for image in application_images(layout) if image.target == "rust_manager")
    bundle = application_bundle(layout)
    assert bundle is not None
    agent = author_agent(product, manager, bundle)
    value = plistlib.loads(agent.contents)
    assert agent.destination.as_posix() == f"Contents/Library/LaunchAgents/{product.manager_id}.plist"
    assert value == {
        "Label": product.manager_id,
        "BundleProgram": f"Contents/Resources/app/{manager.file}",
        "ProgramArguments": [manager.file, "--sign-in"],
        "LimitLoadToSessionType": "Aqua",
        "RunAtLoad": True,
        "KeepAlive": {"SuccessfulExit": False},
        "AbandonProcessGroup": True,
    }
    verify_agent(agent.contents, product, manager, bundle)
    value["KeepAlive"] = True
    with pytest.raises(ValueError, match="differs"):
        verify_agent(plistlib.dumps(value), product, manager, bundle)
    with pytest.raises(ValueError, match="root-level"):
        author_agent(product, replace(manager, placement="bin"), bundle)
    with pytest.raises(ValueError, match="macOS"):
        author_agent(identity("linux-x86-64"), manager, bundle)


def test_unsigned_bundle_carries_dormant_inventory_owned_agent(tmp_path: Path) -> None:
    payload, identity_file = payload_fixture(tmp_path, "macos-arm64", manager=True)
    build = tmp_path / "build"
    build.mkdir()
    (build / "build-paths.json").write_text(
        json.dumps(
            {"paths": {f"installation_{name}": f"installation/{name}" for name in ("stage", "metadata", "work")}}
        ),
        encoding="utf-8",
    )
    stage = prepare(payload, identity_file, build, "cadrumo", bundle=bundle_fixture(tmp_path))
    product = identity("macos-arm64")
    bundle = member(stage, f"{product.name}.app")
    agent = bundle / f"Contents/Library/LaunchAgents/{product.manager_id}.plist"
    assert agent.is_file()
    assert plistlib.loads(agent.read_bytes())["BundleProgram"] == "Contents/Resources/app/cadrumo-manager"
    assert (bundle / "Contents/Resources/app/cadrumo-manager").read_bytes() == (
        payload / "cadrumo-manager"
    ).read_bytes()
    assert not (stage / "Library/LaunchAgents").exists()
    assert not list(stage.rglob("_CodeSignature"))
    receipt = build / "installation/metadata/installation.json"
    verify_inventory(stage, receipt)
    agent.write_bytes(agent.read_bytes().replace(b"Aqua", b"Background"))
    with pytest.raises(ValueError, match="changed"):
        verify_inventory(stage, receipt)
