"""Assembly rejects an incomplete or skewed product before copying payloads."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT

from ...runtime_wheel_selection import active_requirements
from ...runtime_wheelhouse_contract import target_platform
from ..assemble import assemble

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("missing", "closure mismatch"),
        ("mixed", "cohort versions"),
        ("duplicate", "Duplicate installed"),
        ("target", "target/layout ABI"),
    ],
)
def test_invalid_cohort_never_reaches_payload_copy(tmp_path: Path, defect: str, message: str) -> None:
    dependencies = tmp_path / "dependencies"
    dependencies.mkdir()
    versions = {name: "1.2.3" for name in PRODUCT_IDENTITY.cohort_distributions}
    for name, requirement in active_requirements(REPO_ROOT, target_platform("windows-x86-64"), "3.13.11").items():
        versions[name] = next(iter(requirement.specifier)).version
    companion = PRODUCT_IDENTITY.companion_distributions[0]
    if defect == "missing":
        del versions[companion]
    if defect == "mixed":
        versions[companion] = "1.2.2"
    for name, version in versions.items():
        directory = dependencies / f"{name.replace('-', '_')}-{version}.dist-info"
        directory.mkdir()
        (directory / "METADATA").write_text(
            f"Metadata-Version: 2.1\nName: {name}\nVersion: {version}\n", encoding="utf-8"
        )
    if defect == "duplicate":
        directory = dependencies / "duplicate-1.2.3.dist-info"
        directory.mkdir()
        (directory / "METADATA").write_text(f"Name: {companion}\nVersion: 1.2.3\n", encoding="utf-8")
    metadata = tmp_path / "build.json"
    metadata.write_text(
        json.dumps(
            {
                "target": "linux-aarch64" if defect == "target" else "windows-x86-64",
                "layout_abi": 1,
                "python": "3.13.11",
                "version": "1.2.3",
            }
        ),
        encoding="utf-8",
    )
    destination = tmp_path / "package"
    with pytest.raises(ValueError, match=message):
        assemble(
            tmp_path / "sdk",
            dependencies,
            tmp_path / "bin",
            destination,
            metadata,
            None,
            images={},
            binary_dir=tmp_path,
            target="windows-x86-64",
        )
    assert not destination.exists()
