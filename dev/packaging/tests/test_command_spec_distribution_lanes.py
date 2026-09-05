"""Installed-artifact gates for the production CommandSpec authority."""

from __future__ import annotations

import ast
import json
import os
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path
from typing import cast

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]

_REPOSITORY = Path(__file__).resolve().parents[3]
_FORBIDDEN_NAMES = {
    "app_lazy_manifest.v1.json",
    "command_registration_metadata.v1.json",
    "generate_app_lazy_manifest.py",
    "generate_command_registration_metadata.py",
}
_PROBE = r"""
import dataclasses
import importlib
import json
import os
import site
import sys
from pathlib import Path

sys.path.append(os.environ["AEAT_DEPENDENCY_SITE"])
site.addsitedir(os.environ["AEAT_INSTALL_SITE"])

import cadrumo
from cadrumo.core.i18n import SUPPORTED_OUTPUT_LANGUAGES, lookup_translation_entry
from cadrumo.core.json_contract import OutputRootSchema, OutputSchema
from cadrumo.entrypoints import cli
from cadrumo.entrypoints.cli.command_spec import DeferredTarget
from cadrumo.entrypoints.cli.command_suggestions import walk_live_command_tree
from cadrumo.entrypoints.cli.command_api import command_spec_nodes

def translation_keys(value):
    from cadrumo.entrypoints.cli.command_spec import TranslationKey
    if isinstance(value, TranslationKey):
        return (value,)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(key for field in dataclasses.fields(value) for key in translation_keys(getattr(value, field.name)))
    if isinstance(value, tuple):
        return tuple(key for item in value for key in translation_keys(item))
    return ()

def targets(value, path=()):
    if isinstance(value, DeferredTarget):
        return ((path, value),)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return tuple(
            target
            for field in dataclasses.fields(value)
            for target in targets(getattr(value, field.name), (*path, field.name))
        )
    if isinstance(value, tuple):
        return tuple(target for index, item in enumerate(value) for target in targets(item, (*path, str(index))))
    return ()

def resolve(target):
    value = importlib.import_module(target.module)
    for part in target.qualname.split("."):
        if part.startswith("_"):
            raise AssertionError(target.identity)
        value = getattr(value, part)
    return value

def validate_target(path, target):
    value = resolve(target)
    if path[-2:] == ("result_schema", "target"):
        if not isinstance(value, type) or not issubclass(value, OutputSchema | OutputRootSchema):
            raise AssertionError(target.identity)
    elif path[-1] in {"target", "factory", "parser", "completion", "callback"}:
        if not callable(value):
            raise AssertionError(target.identity)
    elif path[-1] in {"annotation", "model"}:
        if not isinstance(value, type):
            raise AssertionError(target.identity)
    elif path[-1] == "click_type":
        if not callable(value) and not callable(getattr(value, "convert", None)):
            raise AssertionError(target.identity)
    else:
        raise AssertionError(f"unrecognized deferred-target role {path}: {target.identity}")
    return value

nodes = command_spec_nodes()
expected_paths = {node.path for node in nodes}
live_paths = {node.path for node in walk_live_command_tree(cli.app)}
all_targets = tuple(target for node in nodes for target in targets(node.spec))
resolved = tuple(validate_target(path, target) for path, target in all_targets)
try:
    validate_target(("planted_unknown_role",), DeferredTarget("builtins", "str"))
except AssertionError:
    unknown_role_refused = True
else:
    unknown_role_refused = False
missing_locale_keys = [
    (node.spec.key, key.value, locale)
    for node in nodes
    for key in translation_keys(node.spec)
    for locale in SUPPORTED_OUTPUT_LANGUAGES
    if not lookup_translation_entry(key.value, locale=locale)[0]
]
install_root = Path(os.environ["AEAT_INSTALL_SITE"]).resolve()
first_party_origins = [
    str(Path(module.__file__).resolve())
    for name, module in sys.modules.items()
    if (name == "cadrumo" or name.startswith("cadrumo.")) and getattr(module, "__file__", None)
]
print(json.dumps({
    "nodes": len(nodes),
    "identities": sorted((node.spec.key, list(node.path)) for node in nodes),
    "kinds": {kind: sum(node.spec.kind == kind for node in nodes) for kind in ("root", "group", "leaf")},
    "live_exact": live_paths == expected_paths,
    "targets": len(all_targets),
    "targets_resolved": len(resolved) == len(all_targets),
    "unknown_role_refused": unknown_role_refused,
    "missing_locale_keys": missing_locale_keys,
    "origins_inside": all(Path(origin).is_relative_to(install_root) for origin in first_party_origins),
    "cadrumo_origin": str(Path(cadrumo.__file__).resolve()),
    "dev_imports": sorted(name for name in sys.modules if name == "dev" or name.startswith("dev.")),
}, sort_keys=True))
"""


def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)  # noqa: S603


def _tracked_checkout(tmp_path: Path) -> Path:
    archive = tmp_path / "tracked.tar"
    checkout = tmp_path / "checkout"
    git = shutil.which("git")
    assert git is not None
    _run([git, "archive", "--format=tar", f"--output={archive}", "HEAD"], cwd=_REPOSITORY)
    checkout.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(checkout, filter="data")
    return checkout


def _is_spec_export_name(name: str) -> bool:
    return name in {"COMMAND_SPEC", "COMMAND_SPECS"} or name.endswith(("_COMMAND_SPEC", "_COMMAND_SPECS"))


def _authored_spec_modules(checkout: Path) -> set[str]:
    cli_root = checkout / "src/cadrumo/entrypoints/cli"
    modules = {"cadrumo/entrypoints/cli/command_spec.py", "cadrumo/entrypoints/cli/command_specs.py"}
    for path in cli_root.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if any(
            isinstance(node, (ast.Assign, ast.AnnAssign))
            and any(
                isinstance(target, ast.Name) and target.id.isupper() and _is_spec_export_name(target.id)
                for target in (node.targets if isinstance(node, ast.Assign) else [node.target])
            )
            for node in tree.body
        ):
            modules.add("cadrumo/entrypoints/cli/" + path.relative_to(cli_root).as_posix())
    return modules


def _assert_archive(members: set[str], *, expected_modules: set[str], prefix: str = "") -> None:
    normalized = {member.removeprefix(prefix) for member in members if member.startswith(prefix)}
    # Each check names what it found. These run over real built wheels and
    # sdists, where a bare `assert` leaves the operator an AssertionError
    # with no indication of which module went missing or which forbidden
    # file shipped - and left the teeth probes below unable to show they
    # fired for the reason they plant.
    missing = sorted(expected_modules - normalized)
    assert not missing, f"archive is missing spec modules: {missing}"
    forbidden = sorted({Path(member).name for member in members} & _FORBIDDEN_NAMES)
    assert not forbidden, f"archive carries forbidden files: {forbidden}"
    development = sorted(member for member in members if "dev/quality/" in member)
    assert not development, f"archive ships development-only paths: {development}"


def _install_and_probe(*, uv: str, artifact: Path, target: Path, checkout: Path) -> dict[str, object]:
    _run([uv, "pip", "install", "--target", str(target), "--no-deps", str(artifact)], cwd=checkout)
    environment = os.environ.copy()
    environment["PYTHONPATH"] = ""
    environment["AEAT_INSTALL_SITE"] = str(target)
    dependency_site = next(path for path in map(Path, sys.path) if path.name == "site-packages" and path.is_dir())
    environment["AEAT_DEPENDENCY_SITE"] = str(dependency_site)
    completed = subprocess.run(  # noqa: S603
        [sys.executable, "-S", "-c", _PROBE],
        cwd=checkout.parent,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    return cast("dict[str, object]", json.loads(completed.stdout))


def _assert_probe(payload: dict[str, object]) -> None:
    assert isinstance(payload["nodes"], int) and payload["nodes"] > 0
    assert cast("dict[str, int]", payload["kinds"])["root"] > 0
    assert cast("dict[str, int]", payload["kinds"])["group"] > 0
    assert cast("dict[str, int]", payload["kinds"])["leaf"] > 0
    assert payload["live_exact"] is True
    assert isinstance(payload["targets"], int) and payload["targets"] > 0
    assert payload["targets_resolved"] is True
    assert payload["unknown_role_refused"] is True
    assert payload["missing_locale_keys"] == []
    assert payload["origins_inside"] is True
    assert payload["dev_imports"] == []


def _assert_same_identity_projection(payloads: list[dict[str, object]]) -> None:
    assert payloads, "no lane payloads to compare, so identity parity would hold vacuously"
    expected = payloads[0]["identities"]
    divergent = [index for index, payload in enumerate(payloads[1:], start=1) if payload["identities"] != expected]
    assert not divergent, f"lane identity projections differ at payload(s) {divergent}"


@pytest.mark.timeout(900)
def test_wheel_sdist_and_sdist_wheel_preserve_command_spec_authority(tmp_path: Path) -> None:
    uv = shutil.which("uv")
    assert uv is not None
    checkout = _tracked_checkout(tmp_path)
    expected_modules = _authored_spec_modules(checkout)
    assert _is_spec_export_name("COMMAND_SPEC")
    assert _is_spec_export_name("COMMAND_SPECS")
    with pytest.raises(AssertionError, match="missing spec modules"):
        _assert_archive(set(), expected_modules={"cadrumo/entrypoints/cli/_planted_command_specs.py"})
    with pytest.raises(AssertionError, match="identity projections differ"):
        _assert_same_identity_projection(
            [{"identities": [["a", ["aeat", "a"]]]}, {"identities": [["b", ["aeat", "b"]]]}]
        )
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    _run([uv, "build", "--wheel", "--sdist", "--out-dir", str(artifacts)], cwd=checkout)
    wheel = next(artifacts.glob("cadrumo-*.whl"))
    sdist = next(artifacts.glob("cadrumo-*.tar.gz"))

    with zipfile.ZipFile(wheel) as bundle:
        _assert_archive(set(bundle.namelist()), expected_modules=expected_modules)
    with tarfile.open(sdist, mode="r:gz") as bundle:
        names = {member.name for member in bundle.getmembers()}
        root = next(iter(names)).split("/", maxsplit=1)[0] + "/src/"
        _assert_archive(names, expected_modules=expected_modules, prefix=root)

    rebuilt = tmp_path / "sdist-wheel"
    rebuilt.mkdir()
    _run([uv, "build", "--wheel", "--out-dir", str(rebuilt), str(sdist)], cwd=checkout.parent)
    sdist_wheel = next(rebuilt.glob("cadrumo-*.whl"))
    with zipfile.ZipFile(sdist_wheel) as bundle:
        _assert_archive(set(bundle.namelist()), expected_modules=expected_modules)

    lane_payloads: list[dict[str, object]] = []
    for label, artifact in (("wheel", wheel), ("sdist", sdist), ("sdist-wheel", sdist_wheel)):
        payload = _install_and_probe(
            uv=uv,
            artifact=artifact,
            target=tmp_path / f"installed-{label}",
            checkout=checkout,
        )
        _assert_probe(payload)
        lane_payloads.append(payload)
    assert len({cast(int, payload["nodes"]) for payload in lane_payloads}) == 1
    assert len({json.dumps(payload["kinds"], sort_keys=True) for payload in lane_payloads}) == 1
    _assert_same_identity_projection(lane_payloads)
