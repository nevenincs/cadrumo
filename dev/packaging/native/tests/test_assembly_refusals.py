"""Assembly rejects an incomplete or skewed product before copying payloads."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

import pytest

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from dev._paths import REPO_ROOT

from ...runtime_wheel_selection import active_requirements
from ...runtime_wheelhouse_contract import target_platform
from ..agent import AGENT_DEPENDENCIES, AGENT_DEPENDENCY_RECORD
from ..assemble import assemble
from ..hashing import digest
from ..product import BUNDLED_EXTRAS

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

#: The agent's resolved additions: one distribution only the agent needs, and one
#: shared distribution the resolution moved off Cadrumo's locked version.
_AGENT_ADDITIONS = {"websockets": "16.1.1", "httpx": "0.28.0"}


def _agent_dependencies(root: Path, versions: Mapping[str, str]) -> Path:
    """Record a resolution as the agent build writes it."""
    root.mkdir()
    path = root / AGENT_DEPENDENCIES
    path.write_bytes(
        "".join(f"{name}=={version} --hash=sha256:{'a' * 64}\n" for name, version in versions.items()).encode()
    )
    record = dict(
        target="windows-x86-64",
        python="3.13.11",
        requirements_sha256=digest(path),
        versions=dict(versions),
    )
    (root / AGENT_DEPENDENCY_RECORD).write_text(json.dumps(record), encoding="utf-8")
    return root


@pytest.mark.parametrize(
    ("defect", "message"),
    [
        ("missing", "closure mismatch"),
        ("core-only", "closure mismatch"),
        ("mixed", "cohort versions"),
        ("duplicate", "Duplicate installed"),
        ("target", "target/layout ABI"),
        ("agent-missing", "closure mismatch"),
        ("agent-version", "agent version"),
        ("agent-runtime-missing", "built agent runtime closure"),
        ("agent-dependency-version", "version differs from lock"),
        ("agent-dependency-missing", "closure mismatch"),
    ],
)
def test_invalid_cohort_never_reaches_payload_copy(tmp_path: Path, defect: str, message: str) -> None:
    dependencies = tmp_path / "dependencies"
    dependencies.mkdir()
    versions = {name: "1.2.3" for name in PRODUCT_IDENTITY.cohort_distributions}
    bundled = active_requirements(REPO_ROOT, target_platform("windows-x86-64"), "3.13.11", extras=BUNDLED_EXTRAS)
    for name, requirement in bundled.items():
        versions[name] = next(iter(requirement.specifier)).version
    assert "httpx" in bundled and "websockets" not in bundled
    versions.update(_AGENT_ADDITIONS)
    versions["cadrumo-agent"] = "0.1.0"
    companion = PRODUCT_IDENTITY.companion_distributions[0]
    if defect == "missing":
        del versions[companion]
    if defect == "core-only":
        del versions["nvidia-ml-py"]
    if defect == "mixed":
        versions[companion] = "1.2.2"
    if defect == "agent-missing":
        del versions["cadrumo-agent"]
    if defect == "agent-version":
        versions["cadrumo-agent"] = "0.0.1"
    if defect == "agent-dependency-version":
        versions["httpx"] = next(iter(bundled["httpx"].specifier)).version
    if defect == "agent-dependency-missing":
        del versions["websockets"]
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
            provenance={"agent": {"version": "0.1.0"}},
            agent_dependencies=_agent_dependencies(tmp_path / "agent", _AGENT_ADDITIONS),
        )
    assert not destination.exists()
