"""Fail-closed gates for the sealed installed CommandSpec cohort attestation."""

from __future__ import annotations

import ast
import dataclasses
from typing import cast

import pytest

from dev._paths import REPO_ROOT

from ..campaign import _LANES
from ..python_cohort import PythonCohort, _validate_command_spec_attestation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DIGEST_FIELDS = (
    "identities_sha256",
    "locales_sha256",
    "policies_sha256",
    "schemas_sha256",
    "import_budgets_sha256",
)
_SEALED_CONSUMERS = (
    "dev/packaging/acquire_claude_plugin.py",
    "dev/packaging/acquire_homebrew.py",
    "dev/packaging/acquire_mcpb.py",
    "dev/packaging/acquire_pypi.py",
    "dev/packaging/oracle_emit_cohort.py",
    "dev/packaging/smoke_absent_llm.py",
    "dev/packaging/smoke_browser.py",
    "dev/packaging/smoke_core.py",
    "dev/packaging/smoke_docker.py",
    "dev/packaging/smoke_extras.py",
    "dev/packaging/smoke_mcpb.py",
    "dev/packaging/smoke_pip_core.py",
    "dev/packaging/smoke_plugin_install.py",
    "dev/packaging/smoke_sdist_core.py",
    "dev/packaging/smoke_split_install.py",
    "dev/release/promote_python_cohort.py",
    "packaging/homebrew/generate.py",
    "packaging/mcpb/build.py",
    "packaging/scoop/generate.py",
)
_SHIPPING_WORKFLOWS = (
    ".github/workflows/packaging-smoke.yml",
    ".github/workflows/packaging-scoop.yml",
    ".github/workflows/packaging-homebrew.yml",
    ".github/workflows/packaging-claude.yml",
    ".github/workflows/publish-release.yml",
)


def _valid_attestation() -> dict[str, object]:
    return {
        "schema": "cadrumo.command-spec-cohort.v1",
        "node_count": 1,
        "forbidden_artifacts_absent": True,
        **{field: str(index) * 64 for index, field in enumerate(_DIGEST_FIELDS, start=1)},
    }


def _called_names(source: str) -> set[str]:
    return {
        node.func.attr if isinstance(node.func, ast.Attribute) else cast(ast.Name, node.func).id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }


def test_attestation_schema_refuses_every_missing_malformed_and_forbidden_dimension() -> None:
    valid = _valid_attestation()
    assert _validate_command_spec_attestation(valid) == valid
    for field in tuple(valid):
        planted = {key: value for key, value in valid.items() if key != field}
        with pytest.raises(SystemExit):
            _validate_command_spec_attestation(planted)
    for field in _DIGEST_FIELDS:
        with pytest.raises(SystemExit):
            _validate_command_spec_attestation({**valid, field: "not-a-digest"})
    with pytest.raises(SystemExit):
        _validate_command_spec_attestation({**valid, "forbidden_artifacts_absent": False})
    with pytest.raises(SystemExit):
        _validate_command_spec_attestation({**valid, "node_count": 0})


def test_every_downstream_consumer_loads_the_sealed_cohort_and_cannot_rebuild_it() -> None:
    forbidden_build_calls = {"build_python_cohort", "build_wheel", "build_sdist", "build_companion_wheels"}
    for relative in _SEALED_CONSUMERS:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        calls = _called_names(source)
        assert "load_python_cohort" in calls, relative
        assert not calls.intersection(forbidden_build_calls), relative

    for lane in _LANES.values():
        for form in lane.forms:
            if lane.name != "dev":
                assert "--cohort-dir" in form.command(), f"{lane.name}/{form.name} rebuild bypass"


def test_shipping_workflows_route_one_downloaded_cohort_without_python_rebuilds() -> None:
    forbidden = ("build_python_cohort", "build_wheel", "build_sdist", "uv build")
    for relative in _SHIPPING_WORKFLOWS:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        if relative.endswith("packaging-smoke.yml"):
            assert source.count("dev.packaging.release_cohort build") == 1
        else:
            cohort_marker = "release-cohort" if relative.endswith("publish-release.yml") else "python-cohort"
            assert cohort_marker in source and "--cohort-dir" in source, relative
            assert not any(token in source for token in forbidden), relative


def test_python_cohort_type_carries_the_validated_attestation() -> None:
    fields = {field.name for field in dataclasses.fields(PythonCohort)}
    assert "command_spec_attestation" in fields


def test_attestation_is_release_output_only_and_never_production_authority() -> None:
    production_root = REPO_ROOT / "src"
    offenders = []
    for path in production_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "command-spec-cohort" in source or "command_spec_attestation" in source:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert not offenders
    assert not any(path.name == "python-cohort.json" for path in production_root.rglob("*.json"))
