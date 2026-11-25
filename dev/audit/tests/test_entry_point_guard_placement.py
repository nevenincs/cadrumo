"""A ``python -m`` runner must define everything before its ``__main__`` guard runs.

``raise SystemExit(main())`` in the middle of a module executes before any
definition below it exists, so the runner works when imported and dies with a
``NameError`` under ``python -m``. Nothing else exercises that path, so the
population is derived from the filesystem and checked structurally.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from dev.paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_AUDIT_ROOT = REPO_ROOT / "dev" / "audit"
_MIN_POPULATION = 20


def _is_main_guard(node: ast.stmt) -> bool:
    if not isinstance(node, ast.If) or not isinstance(node.test, ast.Compare):
        return False
    test = node.test
    operands = [test.left, *test.comparators]
    names = [o.id for o in operands if isinstance(o, ast.Name)]
    literals = [o.value for o in operands if isinstance(o, ast.Constant)]
    return names == ["__name__"] and literals == ["__main__"] and len(test.ops) == 1 and isinstance(test.ops[0], ast.Eq)


def definitions_after_main_guard(source: str) -> list[str]:
    """Name each module-level definition or binding that follows a ``__main__`` guard."""
    body = ast.parse(source).body
    for index, node in enumerate(body):
        if _is_main_guard(node):
            return [_describe(later) for later in body[index + 1 :] if _is_definition(later)]
    return []


def _is_definition(node: ast.stmt) -> bool:
    return isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef | ast.Assign | ast.AnnAssign)


def _describe(node: ast.stmt) -> str:
    name = getattr(node, "name", None)
    return f"{name or type(node).__name__} (line {node.lineno})"


def _audit_sources() -> list[Path]:
    return sorted(path for path in _AUDIT_ROOT.rglob("*.py") if "tests" not in path.relative_to(_AUDIT_ROOT).parts)


def test_the_population_is_derived_from_the_filesystem_and_not_empty() -> None:
    assert len(_audit_sources()) >= _MIN_POPULATION


def test_no_audit_module_defines_anything_after_its_main_guard() -> None:
    offenders = {
        path.relative_to(REPO_ROOT).as_posix(): later
        for path in _audit_sources()
        if (later := definitions_after_main_guard(path.read_text(encoding="utf-8")))
    }

    assert offenders == {}


def test_the_check_catches_a_planted_definition_after_the_guard() -> None:
    planted = (
        "def main() -> int:\n    return helper()\n\n\n"
        'if __name__ == "__main__":\n    raise SystemExit(main())\n\n\n'
        "def helper() -> int:\n    return 0\n"
    )

    assert definitions_after_main_guard(planted) == ["helper (line 9)"]


def test_the_check_accepts_a_guard_placed_last_and_a_module_without_one() -> None:
    last = 'def main() -> int:\n    return 0\n\n\nif __name__ == "__main__":\n    raise SystemExit(main())\n'

    assert definitions_after_main_guard(last) == []
    assert definitions_after_main_guard("def main() -> int:\n    return 0\n") == []
