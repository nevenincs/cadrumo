"""Canonical-definition ownership proofs for every public flow module."""

from __future__ import annotations

import ast
from pathlib import Path
from types import ModuleType

import pytest

from .. import (
    capability,
    checkpoint,
    copy,
    definition,
    engine,
    errors,
    line_frontend,
    resume,
    review,
    scripted,
    validators,
    wizard_projection,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PUBLIC_DEFINING_MODULES: tuple[ModuleType, ...] = (
    capability,
    checkpoint,
    copy,
    definition,
    engine,
    errors,
    line_frontend,
    resume,
    review,
    scripted,
    validators,
    wizard_projection,
)


def _imported_names(module: ModuleType) -> frozenset[str]:
    source_path = Path(module.__file__ or "")
    tree = ast.parse(source_path.read_text(encoding="utf-8"), filename=str(source_path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.asname or alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(alias.asname or alias.name for alias in node.names)
    return frozenset(names)


@pytest.mark.parametrize("module", _PUBLIC_DEFINING_MODULES, ids=lambda module: module.__name__)
def test_every_public_flow_export_is_owned_by_its_defining_module(module: ModuleType) -> None:
    """Reject missing, duplicate, anonymous, imported, and foreign exports."""
    exported = tuple(module.__all__)
    assert exported
    assert len(exported) == len(set(exported))
    assert [name for name in exported if name not in vars(module)] == []
    assert sorted(set(exported) & _imported_names(module)) == []
    foreign = {
        name: getattr(getattr(module, name), "__module__", None)
        for name in exported
        if getattr(getattr(module, name), "__module__", None) not in (None, module.__name__)
    }
    assert foreign == {}
