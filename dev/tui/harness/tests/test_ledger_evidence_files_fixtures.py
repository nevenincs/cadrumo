"""Every evidence-tool review state reaches the screen it declares, without geometry findings."""

from __future__ import annotations

import pytest

from cadrumo.core.config import override_settings
from cadrumo.entrypoints.tui.tests.frame import geometry_band

from ..ledger_evidence_files_fixtures import (
    EvidenceFilesFixtureState,
    build_evidence_files_fixture,
    evidence_files_fixture_interfaces,
)

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.parametrize("state", tuple(EvidenceFilesFixtureState))
@pytest.mark.asyncio
async def test_each_review_state_settles_on_its_declared_screen(state: EvidenceFilesFixtureState) -> None:
    with override_settings(cadrumo_output_language="en"):
        app = build_evidence_files_fixture(state)
        async with app.run_test(size=(120, 40)) as pilot:
            for _ in range(5):
                await pilot.pause()
                await app.workers.wait_for_complete()
            screen = app.screen
            painted = f"{type(screen).__module__}.{type(screen).__qualname__}"
            assert (painted,) == evidence_files_fixture_interfaces(state)
            assert geometry_band(app, 120) == []
