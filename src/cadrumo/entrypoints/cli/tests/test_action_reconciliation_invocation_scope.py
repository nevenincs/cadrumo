"""Real invocation-lifecycle proofs for operator-surface reconciliation reuse."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol

import click
import pytest
import typer
from click.testing import CliRunner as ClickCliRunner
from typer.testing import CliRunner as TyperCliRunner

from ....application.operator_surface.manifest import OperatorSurfaceReconciliation
from .. import current_operator_surface_reconciliation

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


class _InvocationResult(Protocol):
    @property
    def exit_code(self) -> int: ...

    @property
    def output(self) -> str: ...


def _assert_two_invocations_reuse_only_their_own_reconciliation(
    *,
    invoke: Callable[[], _InvocationResult],
    observed: list[OperatorSurfaceReconciliation],
) -> None:
    """Require root and leaf callbacks to share, then require a fresh next root."""
    first_result = invoke()
    second_result = invoke()

    assert first_result.exit_code == 0, first_result.output
    assert second_result.exit_code == 0, second_result.output
    assert len(observed) == 4
    first_root, first_leaf, second_root, second_leaf = observed
    assert first_leaf is first_root
    assert second_leaf is second_root
    assert second_root is not first_root
    assert second_root == first_root


def test_upstream_click_dispatch_reuses_one_reconciliation_per_invocation() -> None:
    observed: list[OperatorSurfaceReconciliation] = []

    @click.group()
    def surface() -> None:
        observed.append(current_operator_surface_reconciliation())

    @surface.command()
    def inspect() -> None:
        observed.append(current_operator_surface_reconciliation())

    runner = ClickCliRunner()
    _assert_two_invocations_reuse_only_their_own_reconciliation(
        invoke=lambda: runner.invoke(surface, ["inspect"]),
        observed=observed,
    )


def test_vendored_typer_dispatch_reuses_one_reconciliation_per_invocation() -> None:
    observed: list[OperatorSurfaceReconciliation] = []
    surface = typer.Typer()

    @surface.callback()
    def root() -> None:
        observed.append(current_operator_surface_reconciliation())

    @surface.command()
    def inspect() -> None:
        observed.append(current_operator_surface_reconciliation())

    runner = TyperCliRunner()
    _assert_two_invocations_reuse_only_their_own_reconciliation(
        invoke=lambda: runner.invoke(surface, ["inspect"]),
        observed=observed,
    )
