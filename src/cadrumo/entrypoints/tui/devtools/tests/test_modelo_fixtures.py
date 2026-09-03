"""Visual-review guarantees for the storage-free production Modelo fixtures."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from textual.scroll_view import ScrollView

from ..modelo_fixtures import MODELO_FIXTURES, ModeloFixtureScenario, resolve_modelo_fixture

pytestmark = [pytest.mark.unit, pytest.mark.hex_entrypoint]

_MODULE = Path(__file__).resolve().parents[1] / "modelo_fixtures.py"
_WIDTHS = (80, 100, 120)


def test_metadata_covers_every_inventoried_modelo_interface_and_state_floor() -> None:
    interfaces = {interface for spec in MODELO_FIXTURES for interface in spec.interfaces}
    assert interfaces == {
        "cadrumo.entrypoints.tui.modelo.edit.screen.ModeloEditScreen",
        "cadrumo.entrypoints.tui.modelo.view.filing.ModeloWorkspaceFilingScreen",
        "cadrumo.entrypoints.tui.modelo.view.inputs.ModeloWorkspaceInputsScreen",
        "cadrumo.entrypoints.tui.modelo.view.overview.ModeloWorkspaceOverviewScreen",
        "cadrumo.entrypoints.tui.modelo.view.provenance.ModeloWorkspaceProvenanceScreen",
        "cadrumo.entrypoints.tui.modelo.view.results.ModeloWorkspaceResultsScreen",
        "cadrumo.entrypoints.tui.modelo.view.verification.ModeloWorkspaceVerificationScreen",
        "cadrumo.entrypoints.tui.modelo.view.work_review.ModeloWorkReviewApp",
        "cadrumo.entrypoints.tui.modelo.view.work_review.ModeloWorkReviewScreen",
        "cadrumo.entrypoints.tui.modelo.view.work_select.ModeloWorkSelectApp",
        "cadrumo.entrypoints.tui.modelo.view.work_select.ModeloWorkSelectScreen",
    }
    assert {spec.scenario for spec in MODELO_FIXTURES} == set(ModeloFixtureScenario)
    assert len({spec.fixture_id for spec in MODELO_FIXTURES}) == len(MODELO_FIXTURES)
    assert all(resolve_modelo_fixture(spec.fixture_id) is spec for spec in MODELO_FIXTURES)


def test_fixture_module_has_no_storage_network_random_or_test_fixture_dependency() -> None:
    tree = ast.parse(_MODULE.read_text(encoding="utf-8"), filename=str(_MODULE))
    imports = {
        node.module or ""
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    } | {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert not any(
        token in imported
        for imported in imports
        for token in ("adapters", "repositories", "network", "random", ".tests")
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("width", _WIDTHS)
@pytest.mark.parametrize("spec", MODELO_FIXTURES, ids=lambda spec: spec.fixture_id)
async def test_every_fixture_mounts_at_supported_width_without_horizontal_overflow_or_sensitive_copy(
    spec,
    width: int,
) -> None:
    app = spec.build()
    async with app.run_test(size=(width, 30)) as pilot:
        await pilot.pause()
        screenshot = app.export_screenshot()
        assert type(app.screen).__module__.startswith("cadrumo.entrypoints.tui.modelo")
        overflowing = {
            widget.id or type(widget).__name__: widget.max_scroll_x
            for widget in app.screen.query(ScrollView)
            if widget.max_scroll_x
        }
        assert overflowing == {}
        lowered = screenshot.casefold()
        assert "00000000t" not in lowered
        assert "secret" not in lowered
        assert "passphrase" not in lowered
        assert "00000000-0000-4000-8000-000000000001" not in lowered


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "spec",
    tuple(next(item for item in MODELO_FIXTURES if item.surface_id == surface) for surface in {
        item.surface_id for item in MODELO_FIXTURES
    }),
    ids=lambda spec: spec.surface_id,
)
async def test_rebuilding_a_surface_produces_the_same_rendered_frame(spec) -> None:
    frames: list[str] = []
    for _attempt in range(2):
        app = spec.build()
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            frames.append(app.export_screenshot())
    assert frames[0] == frames[1]


def test_unknown_fixture_refuses_and_names_the_stable_inventory() -> None:
    with pytest.raises(KeyError, match="accepted") as refusal:
        resolve_modelo_fixture("modelo-missing--ready")
    assert MODELO_FIXTURES[0].fixture_id in str(refusal.value)
