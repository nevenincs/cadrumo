"""The Modelo wire-type producer sizes its modules within the repository's bound, and refuses what it cannot.

The producer is the script the ``modelo-wire-types`` family runs; its grouping
is exercised here directly, over planted definition sizes, so the refusal is the
one a generator run ends with.
"""

from __future__ import annotations

import importlib.util
import sys
from types import ModuleType

import pytest

from dev.quality.typescript_module_size import MAX_PHYSICAL_LINES

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


def _modules(producer: ModuleType, sizes: dict[str, tuple[int, str]]) -> list[tuple[tuple[str, ...], list[str]]]:
    """Group planted definitions, each ``name: (lines, owning definition)``, into modules."""
    written = {name: producer.WrittenDefinition(lines, frozenset()) for name, (lines, _) in sizes.items()}
    owners = {name: frozenset({owner}) for name, (_, owner) in sizes.items()}
    return [(module.key, module.names) for module in producer.contract_modules(sorted(sizes), owners, written)]


def test_the_budget_leaves_the_formatter_room_under_the_repository_bound(producer: ModuleType) -> None:
    assert producer.MAX_PHYSICAL_LINES is MAX_PHYSICAL_LINES
    assert 0 < producer._MODULE_LINE_BUDGET < MAX_PHYSICAL_LINES


def test_a_module_at_the_budget_is_written(producer: ModuleType) -> None:
    budget = producer._MODULE_LINE_BUDGET

    assert _modules(producer, {"Edge": (budget, "modelo.work.calculate")}) == [(("modelo", "work"), ["Edge"])]


def test_a_module_over_the_budget_is_split_where_its_owners_allow(producer: ModuleType) -> None:
    budget = producer._MODULE_LINE_BUDGET
    sizes = {"Left": (budget, "modelo.work.calculate"), "Right": (budget, "modelo.work.verify")}

    assert _modules(producer, sizes) == [
        (("modelo", "work"), ["Right"]),
        (("modelo", "work", "calculate"), ["Left"]),
    ]


def test_a_same_owner_group_over_the_budget_is_cut_into_consecutive_parts(producer: ModuleType) -> None:
    budget = producer._MODULE_LINE_BUDGET
    # Ten definitions one owner reaches, each a quarter of the budget: no owner tells them apart.
    sizes = {f"Part{index:02d}": (budget // 4, "modelo.work.calculate") for index in range(10)}
    names = sorted(sizes)

    grouped = _modules(producer, sizes)

    assert grouped == [
        (("modelo", "work"), names[:4]),
        (("modelo", "work+part2"), names[4:8]),
        (("modelo", "work+part3"), names[8:]),
    ]
    assert _modules(producer, sizes) == grouped


def test_a_single_definition_over_the_budget_is_refused(producer: ModuleType) -> None:
    budget = producer._MODULE_LINE_BUDGET

    with pytest.raises(SystemExit) as refused:
        _modules(producer, {"Big": (budget + 1, "modelo.work.calculate")})

    # A message as the exit code ends the process with status 1.
    assert str(refused.value.code) == f"the Big type takes {budget + 1} lines alone and cannot be split further"
