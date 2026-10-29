"""Component identities reach the C header, the version resources and the manifest; the package keeps its own."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ..assembly_identity import agent_closure, package_binaries, package_build_record, package_components
from ..build_stamp import BuildStamp, ComponentIdentity
from ..layout import application_images, load_layout
from ..metadata import generate

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

STAMP = BuildStamp("2026101903", 412, "2026-10-19T08:30:00Z")


def test_the_shared_record_and_header_carry_the_interpreter_identity_and_both_display_versions(
    tmp_path: Path,
) -> None:
    # The Linux backend renders no resources, so no build tools are needed.
    generate(tmp_path, STAMP, tmp_path, target="linux-x86-64")
    record = json.loads((tmp_path / "build.json").read_text(encoding="utf-8"))
    version = record["version"]
    assert record["interpreter"] == {
        "build_id": "2026101903",
        "build_sequence": 412,
        "build_number": 412,
        "build_date": "2026-10-19T08:30:00Z",
    }
    # The package identity is allocated at staging, and the type belongs to each staged package.
    assert not {"build_id", "build_sequence", "build_type", "display_version"} & set(record)
    header = (tmp_path / "build_metadata.h").read_text(encoding="utf-8")
    assert '#define CADRUMO_BUILD_ID "2026101903"' in header
    assert '#define CADRUMO_BUILD_SEQUENCE "412"' in header
    assert '#define CADRUMO_BUILD_NUMBER "412"' in header
    assert f'#define CADRUMO_DISPLAY_VERSION_RELEASE "{version}+2026101903"' in header
    assert f'#define CADRUMO_DISPLAY_VERSION_DEBUG "{version}+2026101903.debug"' in header
    selection = header[header.index("#ifndef CADRUMO_BUILD_DEBUG") :]
    debug, release = selection.split("#else")
    assert '#define CADRUMO_BUILD_TYPE "debug"' in debug and "CADRUMO_DISPLAY_VERSION_DEBUG" in debug
    assert '#define CADRUMO_BUILD_TYPE "release"' in release and "CADRUMO_DISPLAY_VERSION_RELEASE" in release


def _identity(component: str, build_id: str, sequence: int) -> ComponentIdentity:
    return ComponentIdentity(component, "0" * 64, "0.6.0", BuildStamp(build_id, sequence, "2026-10-19T08:30:00Z"))


def test_components_name_every_cadrumo_built_binary_with_its_own_component_build() -> None:
    layout = load_layout("windows-x86-64")
    identities = {
        "interpreter": _identity("interpreter", "2026101901", 1),
        "manager": _identity("manager", "2026101902", 2),
        "desktop": _identity("desktop", "2026101903", 3),
    }
    binaries = package_binaries(layout, interpreter=False, development=True, images=application_images(layout))
    components = package_components(binaries, identities, "debug")
    roles = {item["path"]: (item["name"], item["role"], item["component"]) for item in components}
    assert roles == {
        "python.exe": ("python", "interpreter", "interpreter"),
        "python_d.exe": ("python_d", "development-interpreter", "interpreter"),
        "bin/cadrumo_python.dll": ("cadrumo_python", "bridge", "interpreter"),
        "bin/aeat.exe": ("aeat", "entrypoint", "interpreter"),
        "bin/cadrumo-mcp.exe": ("cadrumo-mcp", "entrypoint", "interpreter"),
        "bin/cadrumo-runtime.exe": ("cadrumo-runtime", "entrypoint", "interpreter"),
        "bin/cadrumo-agent-service.exe": ("cadrumo-agent-service", "entrypoint", "interpreter"),
        "bin/cadrumo-agent.exe": ("cadrumo-agent", "bundled-image", "interpreter"),
        "cadrumo.exe": ("cadrumo", "desktop", "desktop"),
        "cadrumo-manager.exe": ("cadrumo-manager", "manager", "manager"),
    }
    assert [item["path"] for item in components] == sorted(roles)
    manager = next(item for item in components if item["role"] == "manager")
    assert (manager["build_id"], manager["build_sequence"], manager["build_type"], manager["display_version"]) == (
        "2026101902",
        2,
        "debug",
        "0.6.0+2026101902.debug",
    )
    assert {item["build_id"] for item in components if item["component"] == "interpreter"} == {"2026101901"}
    interpreter_only = package_binaries(layout, interpreter=True, development=False, images=())
    assert [role for role, _ in interpreter_only] == ["bridge", "interpreter"]


def test_the_staged_record_carries_the_package_identity_beside_the_interpreter_identity() -> None:
    shared = {"version": "0.6.0", "interpreter": {"build_id": "2026101901", "build_number": 1}}
    record = package_build_record(shared, BuildStamp("2026101907", 7, "2026-10-19T09:00:00Z"), "release")
    assert record["interpreter"] == shared["interpreter"]
    assert (record["build_id"], record["build_sequence"], record["build_number"]) == ("2026101907", 7, 7)
    assert (record["build_type"], record["display_version"]) == ("release", "0.6.0+2026101907")


def test_the_agent_closure_lists_its_installed_versions_by_name() -> None:
    installed = {"langgraph": "1.2.3", "anyio": "4.9.0", "cadrumo": "0.6.0", "cadrumo-agent": "0.4.0"}
    assert agent_closure(installed, ["langgraph", "anyio"]) == [
        {"name": "anyio", "version": "4.9.0"},
        {"name": "langgraph", "version": "1.2.3"},
    ]
