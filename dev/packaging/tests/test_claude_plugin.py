"""The local Claude plugin generator's verifier, over the real materialiser and real harness data.

The cohort is synthetic bytes in the exact shape the cohort builder seals, so the
materialiser, the shipped skills and reference documents, and the verifier all
run for real; only the wheel contents are stand-ins.
"""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from cadrumo.core.product_identity import PRODUCT_IDENTITY
from cadrumo_harness.resources import harness_root, iter_reference_documents
from cadrumo_harness.workspace import materialise_plugin

from ..claude_plugin import PluginTreeError, verify_plugin_tree
from ..python_cohort import PythonCohort

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_VERSION = "1.2.3"
_TARGETS = ("linux-aarch64", "linux-x86-64", "macos-arm64", "windows-x86-64")


def _wheelhouse(directory: Path) -> tuple[Path, dict[str, object]]:
    name = "mcp-2.0.0-py3-none-any.whl"
    payload = b"sealed-test-wheel:mcp\n"
    manifest: dict[str, object] = {
        "lock_sha256": "b" * 64,
        "platform_floors": {
            "linux-aarch64": "glibc-2.28",
            "linux-x86-64": "glibc-2.28",
            "macos-arm64": "macos-14.0",
            "windows-x86-64": "windows-10",
        },
        "runtimes": {
            "3.13": {
                "platforms": {target: {"mcp": name} for target in _TARGETS},
                "python": "3.13",
                "status": "ready",
                "wheels": {
                    name: {
                        "distribution": "mcp",
                        "sha256": hashlib.sha256(payload).hexdigest(),
                        "size": len(payload),
                        "version": "2.0.0",
                    }
                },
            }
        },
        "schema": "cadrumo.runtime-wheelhouse.v3",
    }
    archive_path = directory / "cadrumo-runtime-wheelhouse.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("runtime-wheelhouse.json", json.dumps(manifest, sort_keys=True))
        archive.writestr(f"wheels/3.13/{name}", payload)
    return archive_path, manifest


def _cohort(directory: Path) -> PythonCohort:
    directory.mkdir(parents=True)
    files = {
        "cadrumo": f"cadrumo-{_VERSION}-py3-none-any.whl",
        "cadrumo-sdist": f"cadrumo-{_VERSION}.tar.gz",
        "source-archive": f"cadrumo-source-{'a' * 64}.zip",
        "cadrumo-data-manuals": f"cadrumo_data_manuals-{_VERSION}-py3-none-any.whl",
        "cadrumo-data-manuals-sdist": f"cadrumo_data_manuals-{_VERSION}.tar.gz",
        "cadrumo-data-official": f"cadrumo_data_official-{_VERSION}-py3-none-any.whl",
        "cadrumo-data-official-sdist": f"cadrumo_data_official-{_VERSION}.tar.gz",
        "cadrumo-data-normatives": f"cadrumo_data_normatives-{_VERSION}-py3-none-any.whl",
        "cadrumo-data-normatives-sdist": f"cadrumo_data_normatives-{_VERSION}.tar.gz",
    }
    paths = {name: directory / filename for name, filename in files.items()}
    for name, path in paths.items():
        path.write_bytes(f"sealed-test-artifact:{name}\n".encode())
    wheelhouse, wheelhouse_manifest = _wheelhouse(directory)
    sha256 = {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}
    sha256["runtime-wheelhouse"] = hashlib.sha256(wheelhouse.read_bytes()).hexdigest()
    return PythonCohort(
        directory=directory.resolve(strict=True),
        manifest=directory / "python-cohort.json",
        source_digest="a" * 64,
        version=_VERSION,
        root_wheel=paths["cadrumo"],
        root_sdist=paths["cadrumo-sdist"],
        source_archive=paths["source-archive"],
        runtime_wheelhouse=wheelhouse,
        runtime_wheelhouse_manifest=wheelhouse_manifest,
        manuals_wheel=paths["cadrumo-data-manuals"],
        manuals_sdist=paths["cadrumo-data-manuals-sdist"],
        official_wheel=paths["cadrumo-data-official"],
        official_sdist=paths["cadrumo-data-official-sdist"],
        normatives_wheel=paths["cadrumo-data-normatives"],
        normatives_sdist=paths["cadrumo-data-normatives-sdist"],
        sha256=sha256,
    )


@pytest.fixture
def generated(tmp_path: Path) -> tuple[Path, PythonCohort]:
    cohort = _cohort(tmp_path / "cohort")
    plugin = tmp_path / "plugin"
    materialise_plugin(plugin, cohort=cohort)
    return plugin, cohort


def test_generated_plugin_carries_identity_server_skills_and_every_cohort_wheel(
    generated: tuple[Path, PythonCohort],
) -> None:
    plugin, cohort = generated
    skills, references = verify_plugin_tree(plugin, cohort)

    shipped_skills = {
        child.name
        for child in harness_root().joinpath("skills").iterdir()
        if child.is_dir() and child.joinpath("SKILL.md").is_file()
    }
    assert skills == len(shipped_skills) > 0
    assert references == len(list(iter_reference_documents())) > 0
    manifest = json.loads((plugin / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert (manifest["name"], manifest["version"]) == ("cadrumo", _VERSION)
    server = json.loads((plugin / ".mcp.json").read_text(encoding="utf-8"))["mcpServers"]["cadrumo"]
    assert "cadrumo-mcp" in server["args"]
    embedded = plugin / "artifacts" / "python"
    for distribution, wheel in zip(PRODUCT_IDENTITY.cohort_distributions, cohort.product_wheels, strict=True):
        assert f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{wheel.name}" in server["args"], distribution
        assert (embedded / wheel.name).read_bytes() == wheel.read_bytes(), distribution


def test_tampered_embedded_wheel_is_refused(generated: tuple[Path, PythonCohort]) -> None:
    plugin, cohort = generated
    (plugin / "artifacts" / "python" / cohort.official_wheel.name).write_bytes(b"foreign bytes")
    with pytest.raises(PluginTreeError, match="cadrumo-data-official wheel bytes drifted"):
        verify_plugin_tree(plugin, cohort)


def test_undeclared_runtime_wheel_is_refused(generated: tuple[Path, PythonCohort]) -> None:
    plugin, cohort = generated
    (plugin / "artifacts" / "python" / "wheelhouse" / "unapproved-1.0-py3-none-any.whl").write_bytes(b"extra")
    with pytest.raises(PluginTreeError, match="runtime wheelhouse inventory drifted"):
        verify_plugin_tree(plugin, cohort)


def test_missing_skill_is_refused(generated: tuple[Path, PythonCohort]) -> None:
    plugin, cohort = generated
    (plugin / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").unlink()
    with pytest.raises(PluginTreeError, match="plugin skills differ"):
        verify_plugin_tree(plugin, cohort)


def test_foreign_plugin_identity_is_refused(generated: tuple[Path, PythonCohort]) -> None:
    plugin, cohort = generated
    manifest_path = plugin / ".claude-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest_path.write_text(json.dumps(manifest | {"name": "aeat"}), encoding="utf-8")
    with pytest.raises(PluginTreeError, match="plugin identity drifted"):
        verify_plugin_tree(plugin, cohort)
