"""Comprehension imports retain finite lexical sources and reject open inputs."""

from __future__ import annotations

import ast

import pytest

from dev.quality.import_target_evaluation import TargetEvaluationContext

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


@pytest.mark.parametrize(
    ("source", "expected"),
    (
        (
            "MODULES = ('package.one', 'package.two')\nresult = {name: import_module(name) for name in MODULES}\n",
            frozenset({"package.one", "package.two"}),
        ),
        (
            "name = ('package.one', 'package.two')\nresult = [import_module(name) for name in name]\n",
            frozenset({"package.one", "package.two"}),
        ),
        (
            "result = [import_module(inner) for outer in (('package.one',),) for inner in outer]\n",
            frozenset({"package.one"}),
        ),
        (
            "name = 'package.outer'\nresult = [name for name in ('package.inner',)]\nimport_module(name)\n",
            frozenset({"package.outer"}),
        ),
        (
            "def load(modules):\n    return {name: import_module(name) for name in modules}\n",
            None,
        ),
        (
            "def load(modules):\n    return [import_module(name) for name in ('package.one',) for name in modules]\n",
            None,
        ),
        (
            "result = [(lambda name: import_module(name))('package.unknown') for name in ('package.one',)]\n",
            None,
        ),
    ),
)
def test_comprehension_import_uses_its_visible_iterable(source: str, expected: frozenset[str] | None) -> None:
    tree = ast.parse(source)
    context = TargetEvaluationContext(tree, "package.consumer")
    call = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "import_module"
    )
    assert context.values_for(call.args[0], call.lineno) == expected
