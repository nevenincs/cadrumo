"""Tests for the plugin materialiser.

Asserts the plugin layout re-materialises the single authored harness source as
a schema-shaped plugin over a real
filesystem ``tmp_path``: a ``.claude-plugin/plugin.json`` manifest carrying the
required publication fields, a top-level ``skills/`` tree, and an
``.mcp.json`` declaring the stdio ``cadrumo-mcp`` server. Where the
``claude`` CLI is on PATH, the emitted tree is additionally asserted to pass
``claude plugin validate --strict``; the structural assertions always run so the
suite never silently degrades to a validator-only skip.
"""

from __future__ import annotations

import inspect
import json
import shutil
import subprocess
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from cadrumo.core.hashing import sha256_hex

from .._workspace import _PluginPythonCohort, materialise_plugin
from ..resources import harness_root, iter_reference_documents
from ._plugin_cohort import PluginTestCohort

pytestmark = [pytest.mark.integration, pytest.mark.hex_core]

_UTF_8 = "utf-8"


def _shipped_skill_names() -> list[str]:
    skills_root = harness_root().joinpath("skills")
    return sorted(
        child.name for child in skills_root.iterdir() if child.is_dir() and child.joinpath("SKILL.md").is_file()
    )


def test_plugin_manifest_carries_required_fields(tmp_path: Path, plugin_cohort: _PluginPythonCohort) -> None:
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    assert manifest.plugin_name == "cadrumo"

    document = json.loads((output / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    assert document["name"] == "cadrumo"
    assert document["displayName"] == "CADRUMO Spanish tax assistant"
    assert document["version"] == manifest.version
    assert document["defaultEnabled"] is False
    assert document["license"] == "Apache-2.0"
    assert document["author"] == {"name": "CADRUMO tax assistant project"}
    assert isinstance(document["keywords"], list) and document["keywords"]
    # Bilingual (English + Spanish) copy; "never files" stated in the English section.
    assert "never files" in document["description"].lower()
    assert document["description"].startswith("English: Operate Cadrumo, the deterministic Spanish-tax CLI,")
    assert "\nEspañol: " in document["description"]
    assert "aeat Spanish-tax CLI" not in document["description"]


def test_plugin_emits_the_skills_tree_from_the_authored_source(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    assert manifest.skills_written == len(_shipped_skill_names())

    assert (output / "skills" / "cadrumo-preparar-modelo-130" / "SKILL.md").is_file()
    # The progressive-disclosure reference a SKILL cites must travel with it.
    assert (output / "skills" / "cadrumo-preparar-modelo-130" / "reference" / "casillas.md").is_file()


def test_plugin_skill_document_keeps_the_shipped_frontmatter_and_body(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    for name in _shipped_skill_names():
        shipped = harness_root().joinpath("skills", name, "SKILL.md").read_text(encoding=_UTF_8)
        written = (output / "skills" / name / "SKILL.md").read_text(encoding=_UTF_8)
        _, frontmatter, body = shipped.split("---\n", 2)
        opening, authored_body = f"---\n{frontmatter}---\n", body.lstrip("\n")
        # Only the pointer to the plugin's reference documents is added, between the two authored parts.
        assert written.startswith(opening) and written.endswith(authored_body), name
        added = written.removeprefix(opening).removesuffix(authored_body)
        assert "`${CLAUDE_PLUGIN_ROOT}/reference/command-operations.md`" in added, name
        assert yaml.safe_load(frontmatter)["name"] == name
    # The material a skill cites beside itself is copied as authored.
    cited = ("skills", "cadrumo-preparar-modelo-130", "reference", "casillas.md")
    shipped_material = harness_root().joinpath(*cited).read_text(encoding=_UTF_8)
    assert output.joinpath(*cited).read_text(encoding=_UTF_8) == shipped_material


def test_plugin_ships_every_reference_document_and_points_each_skill_at_it(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    shipped = list(iter_reference_documents())
    assert shipped and manifest.references_written == len(shipped)

    assert {path.name for path in (output / "reference").iterdir()} == {document.name for document in shipped}
    for document in shipped:
        written = (output / "reference" / document.name).read_text(encoding=_UTF_8)
        assert written == document.read_text(encoding=_UTF_8)
    # A plugin carries no operating rules, so each skill is told where the documents are: under the
    # plugin root Claude resolves when it loads the skill, each named by its own title.
    remap = harness_root().joinpath("reference", "command-operations.md").read_text(encoding=_UTF_8)
    title = remap.splitlines()[0].removeprefix("# ")
    for name in _shipped_skill_names():
        skill = (output / "skills" / name / "SKILL.md").read_text(encoding=_UTF_8)
        for document in shipped:
            assert f"`${{CLAUDE_PLUGIN_ROOT}}/reference/{document.name}`" in skill, name
        assert f"`${{CLAUDE_PLUGIN_ROOT}}/reference/command-operations.md`: {title}" in skill, name


def test_exact_closed_world_cohort_interpolates_into_manifest_and_mcp_launch(
    tmp_path: Path, plugin_cohort: PluginTestCohort
) -> None:
    output = tmp_path / "plugin"
    materialise_plugin(output, cohort=plugin_cohort)
    document = json.loads((output / ".claude-plugin" / "plugin.json").read_text(encoding=_UTF_8))
    assert document["version"] == "1.2.3"
    profile = document["userConfig"]["profile_id"]
    assert profile["type"] == "string"
    assert profile["required"] is True
    credential_reference = document["userConfig"]["credential_reference"]
    assert credential_reference["type"] == "string"
    assert credential_reference["default"] == ""
    assert credential_reference["required"] is False

    mcp = json.loads((output / ".mcp.json").read_text(encoding=_UTF_8))
    assert "aeat" not in mcp["mcpServers"]
    server = mcp["mcpServers"]["cadrumo"]
    assert server["command"] == "uvx"
    assert server["args"] == [
        "--isolated",
        "--no-config",
        "--no-sources",
        "--offline",
        "--no-index",
        "--find-links",
        "${CLAUDE_PLUGIN_ROOT}/artifacts/python/wheelhouse",
        "--no-python-downloads",
        "--from",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.root_wheel.name}",
        "--with",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.manuals_wheel.name}",
        "--with",
        f"${{CLAUDE_PLUGIN_ROOT}}/artifacts/python/{plugin_cohort.official_wheel.name}",
        "cadrumo-mcp",
        "--profile-id",
        "${user_config.profile_id}",
        "--credential-reference",
        "${user_config.credential_reference}",
    ]
    retained = json.loads((output / "artifacts" / "python" / "plugin-python-cohort.json").read_text(encoding=_UTF_8))
    assert set(retained) == {
        "artifacts",
        "runtime_wheelhouse",
        "runtime_wheelhouse_sha256",
        "schema",
        "sha256",
        "source_digest",
        "version",
    }
    assert retained["schema"] == "cadrumo.plugin-python-cohort.v2"
    assert retained["artifacts"] == {
        "cadrumo": plugin_cohort.root_wheel.name,
        "cadrumo-data-manuals": plugin_cohort.manuals_wheel.name,
        "cadrumo-data-official": plugin_cohort.official_wheel.name,
    }
    assert retained["sha256"] == {
        name: plugin_cohort.sha256[name] for name in ("cadrumo", "cadrumo-data-manuals", "cadrumo-data-official")
    }
    assert retained["source_digest"] == plugin_cohort.source_digest
    assert retained["version"] == plugin_cohort.version
    assert retained["runtime_wheelhouse"] == plugin_cohort.runtime_wheelhouse_manifest
    assert retained["runtime_wheelhouse_sha256"] == plugin_cohort.sha256["runtime-wheelhouse"]
    artifact_directory = output / "artifacts" / "python"
    assert {path.name for path in artifact_directory.glob("*.whl")} == {
        wheel.name for wheel in plugin_cohort.product_wheels
    }
    for wheel in plugin_cohort.product_wheels:
        assert (artifact_directory / wheel.name).read_bytes() == wheel.read_bytes()
    assert server["env"] == {
        "CADRUMO_MCP_REQUIRED_VERSION": "1.2.3",
        "PYTHONNOUSERSITE": "1",
        "PYTHONPATH": "",
    }


def test_emitted_plugin_passes_claude_validate_strict_when_cli_present(
    tmp_path: Path, plugin_cohort: _PluginPythonCohort
) -> None:
    """The emitted tree is schema-valid; where ``claude`` exists, prove it strict.

    The structural materialisation and its assertion always run. The live
    ``claude plugin validate --strict`` assertion runs only when the CLI is on
    PATH - it is an ADDITIONAL gate, never a substitute that lets the test pass
    without exercising the emitter, so a missing CLI degrades to "structure
    checked" rather than a silent skip of the whole test.
    """
    output = tmp_path / "plugin"
    manifest = materialise_plugin(output, cohort=plugin_cohort)
    assert (output / ".claude-plugin" / "plugin.json").is_file()
    assert manifest.skills_written > 0

    claude = shutil.which("claude")
    if claude is not None:
        completed = subprocess.run(  # noqa: S603 - explicit validator executable and fixed argv, no shell
            [claude, "plugin", "validate", "--strict", str(output)],
            capture_output=True,
            check=False,
            timeout=None,
            encoding=_UTF_8,
        )
        assert completed.returncode == 0, (
            f"claude plugin validate --strict failed:\n{completed.stdout}\n{completed.stderr}"
        )


def test_materialiser_has_no_cohortless_or_version_override_compatibility() -> None:
    parameters = inspect.signature(materialise_plugin).parameters
    assert parameters["cohort"].default is inspect.Parameter.empty
    assert "version" not in parameters


@pytest.mark.parametrize("distribution", ["cadrumo", "cadrumo-data-manuals", "cadrumo-data-official"])
def test_foreign_product_wheel_bytes_are_refused(
    tmp_path: Path, plugin_cohort: PluginTestCohort, distribution: str
) -> None:
    wheels = {
        "cadrumo": plugin_cohort.root_wheel,
        "cadrumo-data-manuals": plugin_cohort.manuals_wheel,
        "cadrumo-data-official": plugin_cohort.official_wheel,
    }
    wheels[distribution].write_bytes(b"foreign product wheel")
    with pytest.raises(ValueError, match=f"digest mismatch for '{distribution}'"):
        materialise_plugin(tmp_path / "plugin", cohort=plugin_cohort)


def test_foreign_runtime_wheelhouse_bytes_are_refused(tmp_path: Path, plugin_cohort: PluginTestCohort) -> None:
    plugin_cohort.runtime_wheelhouse.write_bytes(b"foreign runtime wheelhouse")
    with pytest.raises(ValueError, match="digest mismatch for 'runtime-wheelhouse'"):
        materialise_plugin(tmp_path / "plugin", cohort=plugin_cohort)


def test_runtime_wheelhouse_rejects_undeclared_members(tmp_path: Path, plugin_cohort: PluginTestCohort) -> None:
    with zipfile.ZipFile(plugin_cohort.runtime_wheelhouse, "a") as archive:
        archive.writestr("wheels/3.13/unapproved-1.0-py3-none-any.whl", b"unapproved dependency")
    changed = replace(
        plugin_cohort,
        sha256=plugin_cohort.sha256 | {"runtime-wheelhouse": sha256_hex(plugin_cohort.runtime_wheelhouse.read_bytes())},
    )
    with pytest.raises(ValueError, match="member inventory drifted"):
        materialise_plugin(tmp_path / "plugin", cohort=changed)


@pytest.mark.parametrize("relationship", ["equal", "source-below-artifacts", "artifacts-below-source"])
def test_overlapping_output_refuses_without_deleting_source_artifacts(tmp_path: Path, relationship: str) -> None:
    from ._plugin_cohort import make_test_plugin_cohort

    output = tmp_path / "plugin"
    artifact_directory = output / "artifacts" / "python"
    if relationship == "equal":
        source_directory = artifact_directory
    elif relationship == "source-below-artifacts":
        source_directory = artifact_directory / "cohort"
    else:
        source_directory = output
    cohort = make_test_plugin_cohort(source_directory)
    # A non-normalized input must receive the same protection as an absolute one.
    cohort = replace(cohort, directory=source_directory / ".." / source_directory.name)
    original_bytes = {path: path.read_bytes() for path in source_directory.iterdir() if path.is_file()}
    with pytest.raises(ValueError, match="must not overlap"):
        materialise_plugin(output, cohort=cohort)
    assert {path: path.read_bytes() for path in original_bytes} == original_bytes
