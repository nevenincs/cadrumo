"""CLI surface tests for `aeat app live portals {list, show}`."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from aeat.domain.portals import PORTAL_REGISTRY
from aeat.entrypoints.cli._app_live import portals_app

pytestmark = [pytest.mark.unit, pytest.mark.domain_application]


@pytest.fixture
def cli_runner() -> CliRunner:
    return CliRunner()


def test_portals_list_emits_every_registered_entry(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(portals_app, ["list"])
    assert result.exit_code == 0, result.output
    assert f"count\t{len(PORTAL_REGISTRY)}" in result.output


def test_portals_list_refuses_mutually_exclusive_filters(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(portals_app, ["list", "--category", "censal", "--modelo", "303"])
    assert result.exit_code != 0


def test_portals_list_refuses_unknown_category(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(portals_app, ["list", "--category", "not-a-category"])
    assert result.exit_code != 0


def test_portals_show_emits_one_entry(cli_runner: CliRunner) -> None:
    portal = next(iter(PORTAL_REGISTRY.values()))
    result = cli_runner.invoke(portals_app, ["view", portal.portal.value])
    assert result.exit_code == 0, result.output
    assert f"portal\t{portal.portal.value}" in result.output


def test_portals_show_refuses_unknown_portal(cli_runner: CliRunner) -> None:
    result = cli_runner.invoke(portals_app, ["view", "NOT_A_PORTAL_ID"])
    assert result.exit_code != 0
