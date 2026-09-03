"""Focused contract tests for the S395 production workbench fixtures."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest
from textual.app import App
from textual.widgets import DataTable

from ..frame import geometry_band, screen_text
from ..workbench_fixtures import WORKBENCH_FIXTURES, WorkbenchFixtureScenario

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_FORBIDDEN_IMPORT_PARTS = frozenset({"adapter", "network", "filesystem", "random", "storage", "clock"})
_PROTECTED_SENTINELS = (
    "12345678Z",
    "SECRET_PROFILE_NAME",
    "PRIVATE_DOCUMENT_TEXT",
    "https://sede.example.invalid/private",
    "CERTIFICATE_PRIVATE_ID",
)


def _hosted(app: App[Any]) -> object:
    """Return the public hosted screen when the fixture uses ScreenHostApp."""
    return getattr(app, "hosted_screen", app)


def _projection_snapshot(app: App[Any]) -> str:
    """Capture only public projection JSON, never runtime/private attributes."""
    screen = _hosted(app)
    projection = getattr(screen, "projection", None)
    if projection is None:
        controller = getattr(screen, "controller", None)
        projection = getattr(controller, "projection", None)
    if projection is None:
        return type(screen).__qualname__
    return f"{type(screen).__qualname__}:{projection.model_dump_json()}"


def _visible_tables(app: App[Any]) -> tuple[DataTable[Any], ...]:
    screen = app.screen
    return tuple(screen.query(DataTable))


def test_fixture_catalogue_has_stable_ids_metadata_and_closed_state_coverage() -> None:
    ids = tuple(spec.fixture_id for spec in WORKBENCH_FIXTURES)
    assert len(ids) == len(set(ids))
    assert ids == tuple(sorted(ids))
    assert all(
        spec.metadata == (("source", "application projection"), ("composition", "production screen"))
        for spec in WORKBENCH_FIXTURES
    )
    assert {spec.scenario for spec in WORKBENCH_FIXTURES} >= {
        WorkbenchFixtureScenario.READY,
        WorkbenchFixtureScenario.EMPTY,
        WorkbenchFixtureScenario.STALE,
        WorkbenchFixtureScenario.UNAVAILABLE,
        WorkbenchFixtureScenario.BLOCKED,
        WorkbenchFixtureScenario.REFUSAL,
        WorkbenchFixtureScenario.FAILURE,
    }
    surfaces = {spec.surface_id for spec in WORKBENCH_FIXTURES}
    assert {
        "home",
        "workbench-root",
        "declarations-calendar",
        "declarations-revisions",
        "declarations-filing-history",
        "declarations-modelo-launcher",
        "aeat-sync-overview",
        "aeat-sync-census",
        "aeat-sync-filed-declarations",
        "aeat-sync-notifications",
        "aeat-sync-evidence-comparison",
        "aeat-sync-reconciliation",
        "operation-modal",
    } <= surfaces


def test_fixture_builds_are_deterministic_and_redacted_by_public_screen_output() -> None:
    for spec in WORKBENCH_FIXTURES:
        first = spec.build()
        second = spec.build()
        assert _projection_snapshot(first) == _projection_snapshot(second), spec.fixture_id
        rendered = _projection_snapshot(first)
        assert all(secret not in rendered for secret in _PROTECTED_SENTINELS), spec.fixture_id


@pytest.mark.asyncio
@pytest.mark.parametrize("width", (80, 100, 120))
async def test_every_production_fixture_mounts_at_supported_width_without_geometry_defects(width: int) -> None:
    for spec in WORKBENCH_FIXTURES:
        app = spec.build()
        async with app.run_test(size=(width, 30)) as pilot:
            await pilot.pause()
            assert geometry_band(app, width) == [], spec.fixture_id
            assert all(table.max_scroll_x == 0 for table in _visible_tables(app)), spec.fixture_id
            assert all(len(table.columns) <= 8 for table in _visible_tables(app)), spec.fixture_id
            rendered = screen_text(app, width, 30)
            assert all(secret not in rendered for secret in _PROTECTED_SENTINELS), spec.fixture_id


def test_fixture_module_has_no_adapter_or_implicit_io_import_boundary() -> None:
    path = Path(__file__).parents[1] / "workbench_fixtures.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = [node.module or "" for node in tree.body if isinstance(node, ast.ImportFrom)] + [
        alias.name for node in tree.body if isinstance(node, ast.Import) for alias in node.names
    ]
    assert not any(any(part in module.casefold() for part in _FORBIDDEN_IMPORT_PARTS) for module in imports)
