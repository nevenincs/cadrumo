"""The builtin value contracts have exactly one definition each.

``ValueContract(DeferredTarget("builtins", "str"))`` and its ``int`` and
``bool`` siblings are immutable and carry no per-module state, so a module-local
copy is a duplicate definition rather than a convenience. Nineteen modules each
declared their own under names like ``_STR``, ``_INT``, ``_BOOL``,
``_TEXT_VALUE`` and ``_FLAG_VALUE`` before they were centralised.

The hazard is not tidiness. Duplicated definitions drift: a change to how a
builtin contract is constructed -- a parser, a completion, a click type -- has to
be made in every copy, and the copy nobody updated keeps producing the old
value while still looking correct at its call site.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..command_spec import (
    FLAG_VALUE,
    PATH_VALUE,
    TEXT_VALUE,
    WHOLE_NUMBER_VALUE,
    DeferredTarget,
    ValueContract,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_CLI_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
#: The declared value types that have a canonical contract. `Path` is here for
#: the same reason the builtins are: the contract is immutable and identical
#: wherever it is constructed.
_CANONICAL_TARGETS: Final[frozenset[tuple[str, str]]] = frozenset(
    {("builtins", "str"), ("builtins", "int"), ("builtins", "bool"), ("pathlib", "Path")}
)


def _defines_builtin_value_contract(path: Path) -> list[str]:
    """Return module-level names bound to a builtin ``ValueContract`` literal."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    found: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target, value = node.targets[0], node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            target, value = node.target, node.value
        else:
            continue
        if not isinstance(target, ast.Name):
            continue
        rendered = ast.unparse(value)
        if any(f"ValueContract(DeferredTarget('{m}', '{q}'))" == rendered for m, q in _CANONICAL_TARGETS):
            found.append(target.id)
    return found


def test_the_canonical_contracts_are_what_they_claim() -> None:
    """Pin the values, so the gate below cannot pass over a renamed concept."""
    assert ValueContract(DeferredTarget("builtins", "str")) == TEXT_VALUE
    assert ValueContract(DeferredTarget("builtins", "int")) == WHOLE_NUMBER_VALUE
    assert ValueContract(DeferredTarget("builtins", "bool")) == FLAG_VALUE
    assert ValueContract(DeferredTarget("pathlib", "Path")) == PATH_VALUE


def test_the_three_canonical_contracts_stay_distinguishable() -> None:
    """Three contracts collapsing onto one would make every gate here vacuous."""
    assert len({TEXT_VALUE, WHOLE_NUMBER_VALUE, FLAG_VALUE, PATH_VALUE}) == 4


def test_no_cli_module_declares_its_own_builtin_value_contract() -> None:
    """`command_spec` is the only module that may construct these.

    A module-local copy is a duplicate definition, which the architecture
    boundaries forbid, and it is how the drift described in this module's
    docstring gets in.
    """
    modules = [path for path in _CLI_ROOT.rglob("*.py") if "tests" not in path.parts and path.name != "command_spec.py"]

    assert len(modules) > 50, (
        f"only {len(modules)} CLI modules were enumerated; the scan collapsed, so an empty "
        "result below would mean 'nothing was searched' rather than 'no duplicates exist'"
    )

    offenders = {
        path.relative_to(_CLI_ROOT).as_posix(): names
        for path in modules
        if (names := _defines_builtin_value_contract(path))
    }

    assert offenders == {}, (
        "module(s) declare their own builtin ValueContract instead of importing the "
        f"canonical one from command_spec: {offenders}"
    )
