"""Every declared operation definition reaches the one production registry."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final

import pytest

from ..operation_composition import build_production_operation_registry

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_APPLICATION_ROOT: Final[Path] = Path(__file__).resolve().parents[2] / "application"
_ID_SUFFIX: Final[str] = "_OPERATION_DEFINITION_ID"

#: Below this the sweep has stopped finding the families it exists to cover.
_PLAUSIBLE_DECLARED_MINIMUM: Final[int] = 15


def _declared_definition_ids() -> dict[str, str]:
    """Return every operation id the application layer declares, by constant.

    Read from the source rather than by importing: a definition that is never
    composed is also one nothing imports, so an import-driven sweep would be
    blind to exactly the case this exists to catch.
    """
    declared: dict[str, str] = {}
    for path in sorted(_APPLICATION_ROOT.rglob("*.py")):
        if "tests" in path.parts:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Constant):
                continue
            if not isinstance(node.value.value, str):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith(_ID_SUFFIX):
                    declared[target.id] = node.value.value
    return declared


def test_every_declared_operation_definition_is_composed() -> None:
    """A definition nothing composes is capacity nothing can reach.

    The registry is the only door: a frontend submits through it and the
    journal records what it started. A definition outside it can be exported,
    tested and maintained while remaining unreachable, which is how six modelo
    lifecycle definitions sat dormant until a sweep like this one found them.
    """
    declared = _declared_definition_ids()
    composed = {definition.definition_id for definition in build_production_operation_registry().definitions}

    assert len(declared) >= _PLAUSIBLE_DECLARED_MINIMUM, (
        f"the declaration sweep found only {len(declared)} operation ids; it has stopped seeing the families"
    )
    dormant = sorted(f"{constant} ({value})" for constant, value in declared.items() if value not in composed)

    assert dormant == [], f"declared but never composed: {dormant}"
