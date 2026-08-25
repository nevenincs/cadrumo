"""Fail-closed gates for the sealed installed CommandSpec cohort attestation."""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest

from dev._paths import REPO_ROOT

from ..campaign import _LANES
from ..python_cohort import (
    _COMMAND_SPEC_PROBE,
    PythonCohort,
    _artifact_command_projection,
    _projection_digest,
    _validate_command_spec_attestation,
)
from ._cohort_attestation import make_minimal_test_python_cohort, make_test_command_spec_attestation

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_DIGEST_FIELDS = (
    "root_wheel_sha256",
    "root_sdist_sha256",
    "source_archive_sha256",
    "artifact_members_sha256",
    "origins_sha256",
    "identities_sha256",
    "locales_sha256",
    "policies_sha256",
    "schemas_sha256",
    "import_budgets_sha256",
)
_SEALED_CONSUMERS = (
    "dev/packaging/acquire_homebrew.py",
    "dev/packaging/acquire_pypi.py",
    "dev/packaging/oracle_emit_cohort.py",
    "dev/packaging/smoke_absent_llm.py",
    "dev/packaging/smoke_browser.py",
    "dev/packaging/smoke_core.py",
    "dev/packaging/smoke_docker.py",
    "dev/packaging/smoke_extras.py",
    "dev/packaging/smoke_homebrew.py",
    "dev/packaging/smoke_pip_core.py",
    "dev/packaging/smoke_sdist_core.py",
    "dev/packaging/smoke_split_install.py",
    "dev/release/promote_python_cohort.py",
    "packaging/homebrew/generate.py",
    "packaging/scoop/generate.py",
)
_SHIPPING_WORKFLOWS = (
    ".github/workflows/packaging-smoke.yml",
    ".github/workflows/packaging-scoop.yml",
    ".github/workflows/packaging-homebrew.yml",
    ".github/workflows/publish-release.yml",
)


def _valid_attestation() -> dict[str, object]:
    value: dict[str, object] = {
        "schema": "cadrumo.command-spec-cohort.v1",
        "node_count": 1,
        "source_commit": "a" * 40,
        "forbidden_artifacts_absent": True,
        **{field: format(index, "x") * 64 for index, field in enumerate(_DIGEST_FIELDS, start=1)},
    }
    value["envelope_sha256"] = _projection_digest(value)
    return value


def _called_names(source: str) -> set[str]:
    return {
        node.func.attr if isinstance(node.func, ast.Attribute) else cast(ast.Name, node.func).id
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }


def _calls_canonical_loader(source: str) -> bool:
    tree = ast.parse(source)
    aliases: set[str] = set()
    module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith("python_cohort"):
            aliases.update(item.asname or item.name for item in node.names if item.name == "load_python_cohort")
        elif isinstance(node, ast.Import):
            module_aliases.update(
                item.asname or item.name for item in node.names if item.name.endswith("python_cohort")
            )
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            value = node.value
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            canonical = isinstance(value, ast.Name) and value.id in aliases
            canonical = canonical or (
                isinstance(value, ast.Attribute)
                and value.attr == "load_python_cohort"
                and isinstance(value.value, ast.Name)
                and value.value.id in module_aliases
            )
            if canonical:
                before = len(aliases)
                aliases.update(target.id for target in targets if isinstance(target, ast.Name))
                changed = changed or len(aliases) != before
    return any(
        (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in aliases)
        or (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "load_python_cohort"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_aliases
        )
        for node in ast.walk(tree)
    )


def _calls_forbidden_builder(source: str) -> bool:
    tree = ast.parse(source)
    forbidden = {"build_python_cohort", "build_wheel", "build_sdist", "build_companion_wheels"}
    aliases: set[str] = set()
    module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            aliases.update(item.asname or item.name for item in node.names if item.name in forbidden)
        elif isinstance(node, ast.Import):
            module_aliases.update(item.asname or item.name for item in node.names)
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Assign, ast.AnnAssign)):
                continue
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            canonical = isinstance(value, ast.Name) and value.id in aliases
            canonical = canonical or (
                isinstance(value, ast.Attribute)
                and value.attr in forbidden
                and isinstance(value.value, ast.Name)
                and value.value.id in module_aliases
            )
            if canonical:
                before = len(aliases)
                aliases.update(target.id for target in targets if isinstance(target, ast.Name))
                changed = changed or before != len(aliases)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if isinstance(node.func, ast.Name) and node.func.id in aliases:
            return True
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in forbidden
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id in module_aliases
        ):
            return True
        tokens = [
            item.value for item in ast.walk(node) if isinstance(item, ast.Constant) and isinstance(item.value, str)
        ]
        if "uv" in tokens and "build" in tokens:
            return True
    return False


def test_attestation_schema_refuses_every_missing_malformed_and_forbidden_dimension() -> None:
    valid = _valid_attestation()
    assert _validate_command_spec_attestation(valid) == valid
    for field in tuple(valid):
        planted = {key: value for key, value in valid.items() if key != field}
        with pytest.raises(SystemExit):
            _validate_command_spec_attestation(planted)
    for field in (*_DIGEST_FIELDS, "envelope_sha256"):
        with pytest.raises(SystemExit):
            _validate_command_spec_attestation({**valid, field: "not-a-digest"})
    with pytest.raises(SystemExit):
        _validate_command_spec_attestation({**valid, "forbidden_artifacts_absent": False})
    with pytest.raises(SystemExit):
        _validate_command_spec_attestation({**valid, "node_count": 0})
    with pytest.raises(SystemExit):
        _validate_command_spec_attestation(valid, expected_source_commit="b" * 40)
    with pytest.raises(SystemExit):
        _validate_command_spec_attestation(valid, expected_root_wheel_sha256="f" * 64)


def test_every_downstream_consumer_loads_the_sealed_cohort_and_cannot_rebuild_it() -> None:
    forbidden_build_calls = {"build_python_cohort", "build_wheel", "build_sdist", "build_companion_wheels"}
    for relative in _SEALED_CONSUMERS:
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        calls = _called_names(source)
        assert _calls_canonical_loader(source), relative
        assert not calls.intersection(forbidden_build_calls), relative
        assert not _calls_forbidden_builder(source), relative

    for lane in _LANES.values():
        for form in lane.forms:
            if lane.name != "dev":
                assert "--cohort-dir" in form.command(), f"{lane.name}/{form.name} rebuild bypass"
                command = form.command()
                module = command[command.index("-m") + 1]
                module_path = REPO_ROOT / f"{module.replace('.', '/')}.py"
                assert _calls_canonical_loader(module_path.read_text(encoding="utf-8")), (
                    f"campaign topology consumer bypasses validator: {lane.name}/{form.name}/{module}"
                )

    discovered = {
        path.relative_to(REPO_ROOT).as_posix()
        for root in (REPO_ROOT / "dev" / "packaging", REPO_ROOT / "dev" / "release", REPO_ROOT / "packaging")
        for path in root.rglob("*.py")
        if "tests" not in path.parts
        and path.name != "python_cohort.py"
        and "--cohort-dir" in path.read_text(encoding="utf-8")
        and any(marker in path.read_text(encoding="utf-8") for marker in ("load_python_cohort", "python-cohort.json"))
    }
    for relative in sorted(discovered):
        source = (REPO_ROOT / relative).read_text(encoding="utf-8")
        assert _calls_canonical_loader(source), f"discovered cohort consumer bypasses validator: {relative}"
    scoop = (REPO_ROOT / "dev/packaging/acquire_scoop.ps1").read_text(encoding="utf-8")
    assert scoop.count('dev.packaging.python_cohort", "verify", "--cohort-dir') == 2


def test_canonical_loader_detector_follows_import_and_assignment_aliases() -> None:
    assert _calls_canonical_loader(
        "from dev.packaging.python_cohort import load_python_cohort as validate\nsealed = validate\nsealed(path)\n"
    )
    assert not _calls_canonical_loader("def load_python_cohort(path): return path\nload_python_cohort(path)\n")
    assert _calls_forbidden_builder(
        "from dev.packaging.python_cohort import build_python_cohort as build\nagain = build\nagain(repo, out)\n"
    )
    assert _calls_forbidden_builder(
        "import dev.packaging.python_cohort as cohort\nrebuild = cohort.build_python_cohort\nrebuild(repo, out)\n"
    )
    assert _calls_forbidden_builder("subprocess.run(['uv', 'build', '--wheel'])\n")


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


def test_deferred_target_detector_rejects_missing_private_wrong_kind_and_unknown_roles() -> None:
    function = next(
        node
        for node in ast.parse(_COMMAND_SPEC_PROBE).body
        if isinstance(node, ast.FunctionDef) and node.name == "resolve"
    )
    namespace: dict[str, object] = {
        "importlib": SimpleNamespace(import_module=lambda _name: SimpleNamespace(public=lambda: None, scalar=1)),
        "OutputSchema": type("OutputSchema", (), {}),
        "OutputRootSchema": type("OutputRootSchema", (), {}),
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), "<probe-resolve>", "exec"), namespace)  # noqa: S102
    resolve = namespace["resolve"]

    def target(qualname: str) -> SimpleNamespace:
        return SimpleNamespace(module="planted", qualname=qualname, identity=f"planted:{qualname}")

    with pytest.raises(AttributeError):
        resolve(("handler", "target"), target("missing"))  # type: ignore[operator]
    with pytest.raises(AssertionError):
        resolve(("handler", "target"), target("_private"))  # type: ignore[operator]
    with pytest.raises(AssertionError):
        resolve(("handler", "target"), target("scalar"))  # type: ignore[operator]
    with pytest.raises(AssertionError, match="unrecognized"):
        resolve(("future_role",), target("public"))  # type: ignore[operator]


def test_installed_probe_origin_guard_defeats_competing_ambient_cadrumo(tmp_path: Path) -> None:
    ambient = tmp_path / "ambient"
    (ambient / "cadrumo").mkdir(parents=True)
    (ambient / "cadrumo" / "__init__.py").write_text("raise RuntimeError('ambient won')\n", encoding="utf-8")
    dependency_site = next(path for path in sys.path if path.endswith("site-packages"))
    environment = {
        **os.environ,
        "PYTHONPATH": "",
        "AEAT_INSTALL_SITE": str(REPO_ROOT / "src"),
        "AEAT_DEPENDENCY_SITE": os.pathsep.join((str(ambient), dependency_site)),
        "AEAT_COMMAND_SPEC_PROBE_MODE": "aeat config profile list",
    }
    completed = subprocess.run(  # noqa: S603 - fixed planted origin probe.
        [sys.executable, "-S", "-c", _COMMAND_SPEC_PROBE],
        cwd=REPO_ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert completed.returncode == 0, completed.stderr
    projection = json.loads(completed.stdout)
    assert all(str(REPO_ROOT / "src") in origin for _name, origin in projection["origins"])


def test_locale_values_and_both_root_artifact_member_sets_are_digest_bound(tmp_path: Path) -> None:
    assert _projection_digest([("key", "en", "value-a")]) != _projection_digest([("key", "en", "value-b")])
    wheel = tmp_path / "root.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        archive.writestr("cadrumo/__init__.py", "")
    sdist = tmp_path / "root.tar.gz"
    with tarfile.open(sdist, "w:gz") as archive:
        payload = b"{}"
        info = tarfile.TarInfo("cadrumo-1.0/src/cadrumo/entrypoints/cli/app_lazy_manifest.v1.json")
        info.size = len(payload)
        archive.addfile(info, io.BytesIO(payload))
    source = tmp_path / "source.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("pyproject.toml", "")
    projection = _artifact_command_projection(wheel, sdist, source)
    assert ("sdist", "src/cadrumo/entrypoints/cli/app_lazy_manifest.v1.json") in projection


@pytest.mark.parametrize("artifact_kind", ["wheel", "sdist", "source"])
def test_canonical_loader_derives_forbidden_absence_from_self_consistent_artifacts(
    tmp_path: Path, artifact_kind: str
) -> None:
    from ..python_cohort import load_python_cohort

    make_minimal_test_python_cohort(tmp_path, version="1.0.0")
    manifest_path = tmp_path / "python-cohort.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    artifact_key = {"wheel": "cadrumo", "sdist": "cadrumo-sdist", "source": "source-archive"}[artifact_kind]
    artifact = tmp_path / manifest["artifacts"][artifact_key]
    if artifact_kind in {"wheel", "source"}:
        forbidden = (
            "cadrumo/entrypoints/cli/app_lazy_manifest.v1.json"
            if artifact_kind == "wheel"
            else "dev/quality/generate_app_lazy_manifest.py"
        )
        with zipfile.ZipFile(artifact, "a") as archive:
            archive.writestr(forbidden, "{}")
    else:
        metadata = b"Name: cadrumo\nVersion: 1.0.0\n"
        with tarfile.open(artifact, "w:gz") as archive:
            for name, payload in (
                ("cadrumo-1.0.0/PKG-INFO", metadata),
                ("cadrumo-1.0.0/src/cadrumo/entrypoints/cli/app_lazy_manifest.v1.json", b"{}"),
            ):
                info = tarfile.TarInfo(name)
                info.size = len(payload)
                archive.addfile(info, io.BytesIO(payload))
    manifest["sha256"][artifact_key] = hashlib.sha256(artifact.read_bytes()).hexdigest()
    manifest["command_spec_attestation"] = make_test_command_spec_attestation(
        tmp_path, manifest["artifacts"], source_commit=manifest["source_commit"]
    )
    manifest["command_spec_attestation"]["forbidden_artifacts_absent"] = True
    envelope = dict(manifest["command_spec_attestation"])
    envelope.pop("envelope_sha256")
    manifest["command_spec_attestation"]["envelope_sha256"] = _projection_digest(envelope)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="forbidden command authority"):
        load_python_cohort(tmp_path)


def test_canonical_loader_rejects_valid_envelope_with_swapped_source_archive_digest(tmp_path: Path) -> None:
    from ..python_cohort import load_python_cohort

    make_minimal_test_python_cohort(tmp_path, version="1.0.0")
    manifest_path = tmp_path / "python-cohort.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    attestation = manifest["command_spec_attestation"]
    attestation["source_archive_sha256"] = "0" * 64
    envelope = dict(attestation)
    envelope.pop("envelope_sha256")
    attestation["envelope_sha256"] = _projection_digest(envelope)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(SystemExit, match="source_archive_sha256 does not bind"):
        load_python_cohort(tmp_path)


def test_attestation_is_release_output_only_and_never_production_authority() -> None:
    production_root = REPO_ROOT / "src"
    offenders = []
    for path in production_root.rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "command-spec-cohort" in source or "command_spec_attestation" in source:
            offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert not offenders
    assert not any(path.name == "python-cohort.json" for path in production_root.rglob("*.json"))
