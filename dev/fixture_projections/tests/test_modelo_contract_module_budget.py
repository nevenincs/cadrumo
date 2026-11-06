"""The Modelo wire-type producer refuses a contract module it cannot split within its line budget.

The producer is the script the ``modelo-wire-types`` family runs; its grouping
is exercised here directly, over planted definition sizes, so the refusal is the
one a generator run ends with.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import pytest

from ...paths import REPO_ROOT

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]

_PRODUCER = REPO_ROOT / "native" / "desktop" / "frontend" / "scripts" / "modelo_fixtures.py"


@pytest.fixture(scope="module")
def producer() -> ModuleType:
    spec = importlib.util.spec_from_file_location("modelo_fixtures_under_test", _PRODUCER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        del sys.modules[spec.name]
    return module


def _modules(producer: ModuleType, sizes: dict[str, tuple[int, str]]) -> list[tuple[str, ...]]:
    """Group planted definitions, each ``name: (lines, owning definition)``, into the work family's modules."""
    written = {name: producer.WrittenDefinition(lines, frozenset()) for name, (lines, _) in sizes.items()}
    owners = {name: frozenset({owner}) for name, (_, owner) in sizes.items()}
    maps = {"work": producer.WrittenDefinition(0, frozenset())}
    return [module.key for module in producer.contract_modules(sorted(sizes), owners, written, maps)]


def test_a_module_at_the_budget_is_written(producer: ModuleType) -> None:
    budget = producer._MODULE_LINE_BUDGET

    assert _modules(producer, {"Edge": (budget, "modelo.work.calculate")}) == [("modelo", "work")]


def test_a_module_over_the_budget_is_split_where_its_owners_allow(producer: ModuleType) -> None:
    budget = producer._MODULE_LINE_BUDGET
    sizes = {"Left": (budget, "modelo.work.calculate"), "Right": (budget, "modelo.work.verify")}

    assert _modules(producer, sizes) == [("modelo", "work"), ("modelo", "work", "calculate")]


def test_a_module_that_cannot_be_split_within_the_budget_is_refused(producer: ModuleType) -> None:
    budget = producer._MODULE_LINE_BUDGET

    with pytest.raises(SystemExit) as refused:
        _modules(producer, {"Big": (budget + 1, "modelo.work.calculate")})

    # A message as the exit code ends the process with status 1.
    assert f"take {budget + 1} lines and cannot be split further" in str(refused.value.code)
