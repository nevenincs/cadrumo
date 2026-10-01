"""The editor explains a calculated zero through the production reader and encrypted storage."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal
from typing import Any, cast

import pytest
from textual.widgets import Button, Input, Static

from ......adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ......application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ......application.modelo.declarations_workspace import DeclarationsWorkspaceDeclarationRefV1
from ......application.modelo.work_form_models import address_key
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from .....tests.modelo_operator_work_storage import SEEDED_AT, seeded_operator_work
from ....components.host import ScreenHostApp
from ...lifecycle import ModeloWorkspaceLifecycleDoor
from ..editor import CasillaEditorPanel, CasillaEditorScreen
from ..installed import InstalledModeloWorkbench, WorkbenchRepositories
from ..screen import ModeloWorkbenchScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.fixture(scope="module")
def calculated(tmp_path_factory: pytest.TempPathFactory) -> Iterator[InstalledModeloWorkbench]:
    with seeded_operator_work(tmp_path_factory.mktemp("formula-values")) as work:
        unit = work.work_unit
        calculate_modelo_revision_from_bucket_aggregation_with_diagnostics(
            work.work_unit_id,
            ports=work.ports,
            casilla_inputs={"06": Decimal("100")},
            clock=SEEDED_AT,
        )

        def door(calculation_revision_id: str | None, verification_report_id: str | None):
            return ModeloWorkspaceLifecycleDoor(
                services=cast(Any, object()),
                work_unit_id=unit.work_unit_id,
                calculation_revision_id=calculation_revision_id,
                verification_report_id=verification_report_id,
                edit_admission=work.admit,
                edit_renewal=work.renew,
            )

        yield InstalledModeloWorkbench(
            bucket_id=unit.bucket_id,
            declaration=DeclarationsWorkspaceDeclarationRefV1(
                work_unit_id=unit.work_unit_id,
                modelo=unit.modelo,
                filing_year=unit.filing_year,
                period=unit.period,
                state=unit.state,
                has_current_calculation=True,
                has_current_filing=False,
            ),
            operation=work.operation,
            repositories=WorkbenchRepositories(
                work_units=work.ports.work_unit_repository,
                calculations=work.ports.calculation_repository,
                verifications=VerificationReportCatalogueRepository(bucket_id=unit.bucket_id),
            ),
            door=door,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.parametrize("size", [(80, 24), (120, 40)], ids=["dialog", "docked"])
@pytest.mark.parametrize("theme", ["cadrumo-dark", "cadrumo-light"])
async def test_the_zero_floor_and_its_saved_income_are_explained_in_both_editor_hosts(
    calculated: InstalledModeloWorkbench,
    language: OutputLanguage,
    size: tuple[int, int],
    theme: str,
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(calculated, actions=calculated)
        app = ScreenHostApp(screen)
        async with app.run_test(size=size) as pilot:
            app.theme = theme
            for _ in range(200):
                await pilot.pause()
                if screen.form is not None:
                    break
            assert screen.form is not None
            await pilot.press("g", "0", "4", "enter")
            await pilot.pause()
            await pilot.press("enter")
            for _ in range(200):
                await pilot.pause()
                panels = list(app.screen.query(CasillaEditorPanel))
                if panels and panels[0].query("#editor-calculation-text"):
                    break
            assert panels
            panel = panels[0]
            explanation = str(panel.query_one("#editor-calculation-text", Static).render())
            card = calculated.help_card("04", language)
            assert card.formula is not None and card.formula.values_text is not None
            assert explanation == f"{card.formula.text}\n{card.formula.values_text}"
            assert isinstance(app.screen, CasillaEditorScreen) is (size[1] < 30)
            assert "[03]" in explanation and "0" in explanation and "€" in explanation
            assert "20 %" in explanation and "=" in explanation
            assert not panel.query(Input), "a calculated box is explained without a writable input"
            label = panel.query_one("#editor-calculation .editor-block-label", Static)
            assert str(label.render()) == tr("tui.modelo.workbench.editor.block.calculation")
            back = panel.query_one("#editor-cancel", Button)
            assert back.region.y >= 0 and back.region.bottom <= size[1]
            identities = {str(screen.form.work_unit_id), str(screen.form.calculation_revision_id)}
            for field in screen.form.fields():
                kind, identity = address_key(field.address)
                if kind == "binding" or not identity.isdigit():
                    identities.add(identity)
                identities.update(str(binding.binding_id) for binding in field.bindings)
            assert not any(identity in explanation for identity in identities if len(identity) > 3)
