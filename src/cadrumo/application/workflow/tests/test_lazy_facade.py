"""Import and public-surface contracts for the workflow facade."""

from __future__ import annotations

import json
import subprocess
import sys

import pytest

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]


def _isolated_modules(expression: str) -> list[str]:
    result = subprocess.run(  # noqa: S603 - fixed interpreter and test-owned expression
        [sys.executable, "-c", expression],
        check=True,
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout)


def test_importing_workflow_facade_loads_no_owning_submodule() -> None:
    loaded = _isolated_modules(
        "import json, sys; import cadrumo.application.workflow; "
        "print(json.dumps(sorted(name for name in sys.modules "
        "if name.startswith('cadrumo.application.workflow.'))))"
    )

    assert loaded == []


def test_lazy_map_has_exact_public_name_parity() -> None:
    import cadrumo.application.workflow as workflow

    assert set(workflow._LAZY_EXPORTS) == set(workflow.__all__)
    assert set(workflow.__all__).issubset(dir(workflow))


def test_each_public_name_resolves_from_its_declared_owner() -> None:
    import cadrumo.application.workflow as workflow

    for name, module_path in workflow._LAZY_EXPORTS.items():
        value = getattr(workflow, name)
        owner = workflow._LAZY_MODULE_LOADERS[module_path]()
        assert value is getattr(owner, name)
