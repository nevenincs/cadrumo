"""Service admission images agree with each platform's desktop child launcher."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.core.hashing import canonical_json_bytes, sha256_hex
from dev.packaging.native.hashing import digest
from dev.packaging.native.layout import application_images, entrypoint_files, load_layout
from dev.packaging.native.service_descriptors import stage_service_descriptors

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("platform", "with_desktop", "expected_holder"),
    [
        ("windows-x64", True, "cadrumo.exe"),
        ("windows-x64", False, "bin/cadrumo-runtime.exe"),
        ("linux-x86-64", True, "bin/cadrumo-runtime"),
        ("macos-arm64", True, "bin/cadrumo-runtime"),
    ],
)
def test_holder_admission_binds_the_platform_launcher(
    tmp_path: Path, platform: str, with_desktop: bool, expected_holder: str
) -> None:
    layout = load_layout(platform)
    images = tuple(image for image in application_images(layout) if with_desktop or not image.desktop)
    for relative in [*entrypoint_files(layout).values(), *(image.package_path for image in images)]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(relative.encode())

    relative = stage_service_descriptors(tmp_path, layout, images)

    descriptors = json.loads((tmp_path / relative).read_bytes())
    holder = next(item for item in descriptors if item["service_id"] == "desktop-session")
    assert holder["launch_image"] == expected_holder
    expected_arguments = ["--role", "runtime", "session", "hold"] if expected_holder == "cadrumo.exe" else None
    assert holder.get("launch_arguments") == expected_arguments
    assert holder["image_digest"] == digest(tmp_path / expected_holder)
    assert holder["allowed_parent_images"] == [
        {"launch_image": image.package_path, "image_digest": digest(tmp_path / image.package_path)}
        for image in images
        if image.desktop
    ]
    assert not holder["allow_descendants"]
    assert holder["operation_scope"]["operations"] == []
    expected_digest = holder.pop("descriptor_digest")
    assert expected_digest == sha256_hex(canonical_json_bytes(holder))
