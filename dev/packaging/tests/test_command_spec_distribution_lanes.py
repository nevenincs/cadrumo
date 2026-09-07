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
from ..python_cohort import _FORBIDDEN_COMMAND_ARTIFACT_NAMES
pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.serial]
_REPOSITORY = Path(__file__).resolve().parents[3]
_FORBIDDEN_NAMES = _FORBIDDEN_COMMAND_ARTIFACT_NAMES
_PROBE = '\nimport dataclasses\nimport importlib\nimport json\nimport os\nimport site\nimport sys\nfrom pathlib import Path\n\nsys.path.append(os.environ["AEAT_DEPENDENCY_SITE"])\nsite.addsitedir(os.environ["AEAT_INSTALL_SITE"])\n\nimport cadrumo\nfrom cadrumo.core.i18n import SUPPORTED_OUTPUT_LANGUAGES, lookup_translation_entry\nfrom cadrumo.core.json_contract import OutputRootSchema, OutputSchema\nfrom cadrumo.entrypoints import cli\nfrom cadrumo.entrypoints.cli.command_spec import DeferredTarget\nfrom cadrumo.entrypoints.cli.command_suggestions import walk_live_command_tree\nfrom cadrumo.entrypoints.cli.command_api import command_spec_nodes\n\ndef translation_keys(value):\n    from cadrumo.entrypoints.cli.command_spec import TranslationKey\n    if isinstance(value, TranslationKey):\n        return (value,)\n    if dataclasses.is_dataclass(value) and not isinstance(value, type):\n        return tuple(key for field in dataclasses.fields(value) for key in translation_keys(getattr(value, field.name)))\n    if isinstance(value, tuple):\n        return tuple(key for item in value for key in translation_keys(item))\n    return ()\n\ndef targets(value, path=()):\n    if isinstance(value, DeferredTarget):\n        return ((path, value),)\n    if dataclasses.is_dataclass(value) and not isinstance(value, type):\n        return tuple(\n            target\n            for field in dataclasses.fields(value)\n            for target in targets(getattr(value, field.name), (*path, field.name))\n        )\n    if isinstance(value, tuple):\n        return tuple(target for index, item in enumerate(value) for target in targets(item, (*path, str(index))))\n    return ()\n\ndef resolve(target):\n    value = importlib.import_module(target.module)\n    for part in target.qualname.split("."):\n        if part.startswith("_"):\n            raise AssertionError(target.identity)\n        value = getattr(value, part)\n    return value\n\ndef validate_target(path, target):\n    value = resolve(target)\n    if path[-2:] == ("result_schema", "target"):\n        if not isinstance(value, type) or not issubclass(value, OutputSchema | OutputRootSchema):\n            raise AssertionError(target.identity)\n    elif path[-1] in {"target", "factory", "parser", "completion", "callback"}:\n        if not callable(value):\n            raise AssertionError(target.identity)\n    elif path[-1] in {"annotation", "model"}:\n        if not isinstance(value, type):\n            raise AssertionError(target.identity)\n    elif path[-1] == "click_type":\n        if not callable(value) and not callable(getattr(value, "convert", None)):\n            raise AssertionError(target.identity)\n    else:\n        raise AssertionError(f"unrecognized deferred-target role {path}: {target.identity}")\n    return value\n\nnodes = command_spec_nodes()\nexpected_paths = {node.path for node in nodes}\nlive_paths = {node.path for node in walk_live_command_tree(cli.app)}\nall_targets = tuple(target for node in nodes for target in targets(node.spec))\nresolved = tuple(validate_target(path, target) for path, target in all_targets)\ntry:\n    validate_target(("planted_unknown_role",), DeferredTarget("builtins", "str"))\nexcept AssertionError:\n    unknown_role_refused = True\nelse:\n    unknown_role_refused = False\nmissing_locale_keys = [\n    (node.spec.key, key.value, locale)\n    for node in nodes\n    for key in translation_keys(node.spec)\n    for locale in SUPPORTED_OUTPUT_LANGUAGES\n    if not lookup_translation_entry(key.value, locale=locale)[0]\n]\ninstall_root = Path(os.environ["AEAT_INSTALL_SITE"]).resolve()\nfirst_party_origins = [\n    str(Path(module.__file__).resolve())\n    for name, module in sys.modules.items()\n    if (name == "cadrumo" or name.startswith("cadrumo.")) and getattr(module, "__file__", None)\n]\nprint(json.dumps({\n    "nodes": len(nodes),\n    "identities": sorted((node.spec.key, list(node.path)) for node in nodes),\n    "kinds": {kind: sum(node.spec.kind == kind for node in nodes) for kind in ("root", "group", "leaf")},\n    "live_exact": live_paths == expected_paths,\n    "targets": len(all_targets),\n    "targets_resolved": len(resolved) == len(all_targets),\n    "unknown_role_refused": unknown_role_refused,\n    "missing_locale_keys": missing_locale_keys,\n    "origins_inside": all(Path(origin).is_relative_to(install_root) for origin in first_party_origins),\n    "cadrumo_origin": str(Path(cadrumo.__file__).resolve()),\n    "dev_imports": sorted(name for name in sys.modules if name == "dev" or name.startswith("dev.")),\n}, sort_keys=True))\n'

def _run(command: list[str], *, cwd: Path) -> None:
    subprocess.run(command, cwd=cwd, check=True, capture_output=True, text=True)

def _tracked_checkout(tmp_path: Path) -> Path:
    archive = tmp_path / 'tracked.tar'
    checkout = tmp_path / 'checkout'
    git = shutil.which('git')
    assert git is not None
    _run([git, 'archive', '--format=tar', f'--output={archive}', 'HEAD'], cwd=_REPOSITORY)
    checkout.mkdir()
    with tarfile.open(archive) as bundle:
        bundle.extractall(checkout, filter='data')
    return checkout

def _is_spec_export_name(name: str) -> bool:
    return _dp_or('dev/packaging/tests/test_command_spec_distribution_lanes.py:156:or', lambda: name in {'COMMAND_SPEC', 'COMMAND_SPECS'}, lambda: name.endswith(('_COMMAND_SPEC', '_COMMAND_SPECS')))

def _authored_spec_modules(checkout: Path) -> set[str]:
    cli_root = checkout / 'src/cadrumo/entrypoints/cli'
    modules = {'cadrumo/entrypoints/cli/command_spec.py', 'cadrumo/entrypoints/cli/command_specs.py'}
    for path in cli_root.rglob('*.py'):
        tree = ast.parse(path.read_text(encoding='utf-8'))
        if any((isinstance(node, (ast.Assign, ast.AnnAssign)) and any((isinstance(target, ast.Name) and target.id.isupper() and _is_spec_export_name(target.id) for target in (node.targets if isinstance(node, ast.Assign) else [node.target]))) for node in tree.body)):
            modules.add('cadrumo/entrypoints/cli/' + path.relative_to(cli_root).as_posix())
    return modules

def _assert_archive(members: set[str], *, expected_modules: set[str], prefix: str='') -> None:
    normalized = {member.removeprefix(prefix) for member in members if member.startswith(prefix)}
    missing = sorted(expected_modules - normalized)
    assert not missing, f'archive is missing spec modules: {missing}'
    forbidden = sorted({Path(member).name for member in members} & _FORBIDDEN_NAMES)
    assert not forbidden, f'archive carries forbidden files: {forbidden}'
    development = sorted((member for member in members if 'dev/quality/' in member))
    assert not development, f'archive ships development-only paths: {development}'

def _install_and_probe(*, uv: str, artifact: Path, target: Path, checkout: Path) -> dict[str, object]:
    _run([uv, 'pip', 'install', '--target', str(target), '--no-deps', str(artifact)], cwd=checkout)
    environment = os.environ.copy()
    environment['PYTHONPATH'] = ''
    environment['AEAT_INSTALL_SITE'] = str(target)
    dependency_site = next((path for path in map(Path, sys.path) if path.name == 'site-packages' and path.is_dir()))
    environment['AEAT_DEPENDENCY_SITE'] = str(dependency_site)
    completed = subprocess.run([sys.executable, '-S', '-c', _PROBE], cwd=checkout.parent, env=environment, check=False, capture_output=True, text=True)
    assert completed.returncode == 0, completed.stderr
    return cast('dict[str, object]', json.loads(completed.stdout))

def _assert_probe(payload: dict[str, object]) -> None:
    assert isinstance(payload['nodes'], int) and payload['nodes'] > 0
    assert cast('dict[str, int]', payload['kinds'])['root'] > 0
    assert cast('dict[str, int]', payload['kinds'])['group'] > 0
    assert cast('dict[str, int]', payload['kinds'])['leaf'] > 0
    assert payload['live_exact'] is True
    assert isinstance(payload['targets'], int) and payload['targets'] > 0
    assert payload['targets_resolved'] is True
    assert payload['unknown_role_refused'] is True
    assert payload['missing_locale_keys'] == []
    assert payload['origins_inside'] is True
    assert payload['dev_imports'] == []

def _assert_same_identity_projection(payloads: list[dict[str, object]]) -> None:
    assert payloads, 'no lane payloads to compare, so identity parity would hold vacuously'
    expected = payloads[0]['identities']
    divergent = [index for index, payload in enumerate(payloads[1:], start=1) if payload['identities'] != expected]
    assert not divergent, f'lane identity projections differ at payload(s) {divergent}'

@pytest.mark.timeout(900)
def test_wheel_sdist_and_sdist_wheel_preserve_command_spec_authority(tmp_path: Path) -> None:
    uv = shutil.which('uv')
    assert uv is not None
    checkout = _tracked_checkout(tmp_path)
    expected_modules = _authored_spec_modules(checkout)
    assert _is_spec_export_name('COMMAND_SPEC')
    assert _is_spec_export_name('COMMAND_SPECS')
    with pytest.raises(AssertionError, match='missing spec modules'):
        _assert_archive(set(), expected_modules={'cadrumo/entrypoints/cli/_planted_command_specs.py'})
    with pytest.raises(AssertionError, match='identity projections differ'):
        _assert_same_identity_projection([{'identities': [['a', ['aeat', 'a']]]}, {'identities': [['b', ['aeat', 'b']]]}])
    artifacts = tmp_path / 'artifacts'
    artifacts.mkdir()
    _run([uv, 'build', '--wheel', '--sdist', '--out-dir', str(artifacts)], cwd=checkout)
    wheel = next(artifacts.glob('cadrumo-*.whl'))
    sdist = next(artifacts.glob('cadrumo-*.tar.gz'))
    with zipfile.ZipFile(wheel) as bundle:
        _assert_archive(set(bundle.namelist()), expected_modules=expected_modules)
    with tarfile.open(sdist, mode='r:gz') as bundle:
        names = {member.name for member in bundle.getmembers()}
        root = next(iter(names)).split('/', maxsplit=1)[0] + '/src/'
        _assert_archive(names, expected_modules=expected_modules, prefix=root)
    rebuilt = tmp_path / 'sdist-wheel'
    rebuilt.mkdir()
    _run([uv, 'build', '--wheel', '--out-dir', str(rebuilt), str(sdist)], cwd=checkout.parent)
    sdist_wheel = next(rebuilt.glob('cadrumo-*.whl'))
    with zipfile.ZipFile(sdist_wheel) as bundle:
        _assert_archive(set(bundle.namelist()), expected_modules=expected_modules)
    lane_payloads: list[dict[str, object]] = []
    for label, artifact in (('wheel', wheel), ('sdist', sdist), ('sdist-wheel', sdist_wheel)):
        payload = _install_and_probe(uv=uv, artifact=artifact, target=tmp_path / f'installed-{label}', checkout=checkout)
        _assert_probe(payload)
        lane_payloads.append(payload)
    assert len({cast(int, payload['nodes']) for payload in lane_payloads}) == 1
    assert len({json.dumps(payload['kinds'], sort_keys=True) for payload in lane_payloads}) == 1
    _assert_same_identity_projection(lane_payloads)