"""The launcher is the one place a TUI session composes the operation platform."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Final, cast

import pytest

from ....application.operations.composition import OperationComposedServices
from ....application.operations.registry import OperationPublicContractSetV1
from ..launcher import TuiOperationCompositionV1, operation_services_scope

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_TUI_ROOT: Final[Path] = Path(__file__).resolve().parents[1]
_COMPOSITION_ROOT: Final[str] = "launcher.py"

#: Building any of these is composing the operation platform.
_COMPOSITION_SYMBOLS: Final[frozenset[str]] = frozenset(
    {"compose_operation_dependencies", "build_production_operation_registry", "compose_operation_services"}
)


def _tui_modules() -> tuple[Path, ...]:
    modules = tuple(sorted(path for path in _TUI_ROOT.rglob("*.py") if "tests" not in path.parts))
    if len(modules) < 20:
        pytest.fail(f"the TUI module sweep collapsed to {len(modules)} files")
    return modules


def test_only_the_launcher_composes_the_operation_platform() -> None:
    """A second composition root would give one session two inventories.

    The registry, journal, leases and supervisor are one graph per run. A
    screen that built its own would submit into a journal nothing else reads
    and hold leases nothing else settles, which is invisible until two of them
    disagree about the same operation.
    """
    offenders: dict[str, list[str]] = {}
    for path in _tui_modules():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        reached = sorted(
            {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
                for alias in node.names
                if alias.name in _COMPOSITION_SYMBOLS
            }
        )
        if reached and path.name != _COMPOSITION_ROOT:
            offenders[path.relative_to(_TUI_ROOT).as_posix()] = reached

    assert offenders == {}, f"the TUI composes the operation platform outside its launcher: {offenders}"


def test_the_launcher_actually_holds_the_composition() -> None:
    """Guard the sweep against passing because nobody composes anything."""
    launcher = (_TUI_ROOT / _COMPOSITION_ROOT).read_text(encoding="utf-8")

    assert "compose_operation_dependencies" in launcher
    assert "operation_services_scope" in launcher


@pytest.mark.asyncio
async def test_operation_scope_exposes_same_graph_contracts_and_settles_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The TUI receives contracts from its exact service graph, never a rebuilt registry."""
    contracts = cast(OperationPublicContractSetV1, object())

    class _Services:
        public_contracts = contracts

        def __init__(self) -> None:
            self.shutdown_calls = 0

        async def shutdown(self) -> None:
            self.shutdown_calls += 1

    services = _Services()
    monkeypatch.setattr(
        "cadrumo.entrypoints.operation_composition.compose_operation_dependencies",
        lambda: cast(OperationComposedServices, services),
    )

    async with operation_services_scope() as composition:
        assert composition.services is services
        assert composition.public_contracts is contracts
        assert services.shutdown_calls == 0

    assert services.shutdown_calls == 1


def test_operation_composition_refuses_a_detached_public_contract_set() -> None:
    """A stale or fabricated set cannot be paired with otherwise live services."""
    composed = cast(OperationPublicContractSetV1, object())
    detached = cast(OperationPublicContractSetV1, object())

    class _Services:
        public_contracts = composed

    services = cast(OperationComposedServices, _Services())

    with pytest.raises(ValueError, match="exact composed service contracts"):
        TuiOperationCompositionV1(services=services, public_contracts=detached)
