"""Anthropic optional-extra failures preserve the core typed boundary.

The absent state is an installed-product property, not an import-hook
simulation.  This module builds the committed command/data cohort, installs its
core wheel with no optional extras into a fresh stdlib virtual environment, and
then imports the real LLM client and provider loader from that environment.
"""
from __future__ import annotations
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path
import pytest
from cadrumo.core.optional_extras import ANTHROPIC_EXTRA
from .._smoke_common import build_companion_wheels, build_wheel, create_pip_venv, head_extract, install_targets_with_pip, isolated_product_env, venv_python_path
pytestmark = [pytest.mark.integration, pytest.mark.hex_outbound_adapter, pytest.mark.serial]
_REPO_ROOT = Path(__file__).resolve().parents[3]

@pytest.fixture(autouse=True)
def _repository_root_resolved() -> None:
    """Fail this module's tests if the depth arithmetic retargeted.

    Checked per test rather than at import. Collection must stay side-effect
    free, and a guard that raises during collection reports a broken module
    rather than a named gate that lost its root, which is harder to act on.
    """
    assert (_REPO_ROOT / 'pyproject.toml').is_file(), f'packaging gate lost the repository root: {_REPO_ROOT}'
_MARKER = 'ANTHROPIC_BOUNDARIES:'

@pytest.fixture(scope='module')
def installed_core_environment(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path]:
    """Build one complete core-only product cohort for the real absence proof."""
    uv = shutil.which('uv')
    assert uv is not None, 'uv is required to build the installed core cohort'
    work_dir = tmp_path_factory.mktemp('anthropic-optional-extra-boundary')
    build_root = head_extract(_REPO_ROOT, work_dir)
    root_wheel = build_wheel(_REPO_ROOT, work_dir, uv, build_root=build_root)
    data_wheels = build_companion_wheels(work_dir, uv, build_root=build_root)
    venv = create_pip_venv(work_dir, f'{sys.version_info.major}.{sys.version_info.minor}')
    install_targets_with_pip(work_dir, (str(root_wheel.resolve()), *(str(wheel.resolve()) for wheel in data_wheels)), venv)
    return (work_dir, venv_python_path(venv))

def _isolated_environment(work_dir: Path) -> dict[str, str]:
    """Keep the child outside the checkout and its host product configuration."""
    environment = isolated_product_env(work_dir / 'product-state')
    _dp_pop('dev/packaging/tests/test_anthropic_optional_extra_boundary.py:77:pop', environment, 'PYTHONPATH', None)
    return environment

@pytest.mark.timeout(900)
def test_client_and_provider_loader_preserve_the_registered_extra_facts(installed_core_environment: tuple[Path, Path]) -> None:
    """Both installed lazy-import boundaries propagate one machine-readable refusal."""
    work_dir, python = installed_core_environment
    code = textwrap.dedent(f'\n        import json\n        from pathlib import Path\n\n        import cadrumo\n        from cadrumo.core.optional_extras import MissingOptionalExtraError\n        from cadrumo.core.config import load_settings\n        from cadrumo.llm.client import LLMClient\n        from cadrumo.llm.models import LLMProvider\n        from cadrumo.llm.providers.anthropic import _load_anthropic_sdk\n\n        client = LLMClient(settings=load_settings())\n        boundaries = (\n            lambda: client._build_adapter(LLMProvider.ANTHROPIC),\n            _load_anthropic_sdk,\n        )\n        outcomes = []\n        for boundary in boundaries:\n            try:\n                boundary()\n            except MissingOptionalExtraError as error:\n                outcomes.append(error.extra.model_dump(mode="json"))\n        print(\n            {_MARKER!r}\n            + json.dumps(\n                {{"cadrumo_file": str(Path(cadrumo.__file__).resolve()), "outcomes": outcomes}},\n                sort_keys=True,\n            )\n        )\n        ')
    completed = subprocess.run([str(python), '-c', code], cwd=work_dir, env=_isolated_environment(work_dir), capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=120, check=False)
    assert completed.returncode == 0, completed.stderr
    line = _dp_next('dev/packaging/tests/test_anthropic_optional_extra_boundary.py:132:next', (row for row in completed.stdout.splitlines() if row.startswith(_MARKER)), None)
    assert line is not None, completed.stdout
    report = json.loads(line.removeprefix(_MARKER))
    assert Path(report['cadrumo_file']).is_relative_to(python.parents[1])
    assert report['outcomes'] == [ANTHROPIC_EXTRA.model_dump(mode='json')] * 2