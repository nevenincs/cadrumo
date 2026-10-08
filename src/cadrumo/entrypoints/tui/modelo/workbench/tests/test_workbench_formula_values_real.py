"""The editor explains a calculated zero through the production reader and encrypted storage."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from rich.cells import cell_len
from textual.widgets import Button, Footer, Input, Static

from ......adapters.persistence.profile.modelos_verification_reports import VerificationReportCatalogueRepository
from ......application.modelo.calculation_actions import (
    calculate_modelo_revision_from_bucket_aggregation_with_diagnostics,
)
from ......application.modelo.work_form_models import address_key
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from ......domain.modelos.verification_report import (
    ModeloVerificationFinding,
    ModeloVerificationFindingKind,
    ModeloVerificationFindingSeverity,
    VerificationCompletenessStatus,
    VerificationReport,
    derive_verification_report_id,
)
from ......domain.modelos.verification_repository import upsert_verification_report
from .....tests.modelo_operator_work_storage import SEEDED_AT, seeded_operator_work
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import application_workbench
from ..editor import CasillaEditorPanel, CasillaEditorScreen
from ..header import blocking_count, deadline_view, fit_identity
from ..installed import InstalledModeloWorkbench
from ..issues import WorkbenchIssuesScreen
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
        # A controlled typed check outcome exercises the installed reader and
        # encrypted report storage; this fixture does not prove the verifier.
        head = work.require_head()
        findings = (
            ModeloVerificationFinding(
                kind=ModeloVerificationFindingKind.MISSING_REQUIRED_CASILLA,
                severity=ModeloVerificationFindingSeverity.BLOCKING,
                casilla_id="01",
                message_locale_key="application.modelo.verification.missing_required_casilla",
                legal_refs=head.observations[0].legal_refs,
            ),
        )
        status = VerificationCompletenessStatus.BLOCKED
        reports = VerificationReportCatalogueRepository(bucket_id=unit.bucket_id)
        catalogue = reports.load()
        report = VerificationReport(
            verification_report_id=derive_verification_report_id(
                calculation_revision_id=head.calculation_revision_id,
                completeness_status=status,
                findings=findings,
                verified_by="test:small-workbench",
            ),
            calculation_revision_id=head.calculation_revision_id,
            registry_snapshot_ref=head.registry_snapshot_ref,
            completeness_status=status,
            findings=findings,
            run_at=SEEDED_AT,
            verified_by="test:small-workbench",
            granted_verificado_completo=False,
        )
        reports.save(upsert_verification_report(catalogue, report))

        yield application_workbench(work.work_unit, operation=work.operation)


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


@pytest.mark.asyncio
@pytest.mark.parametrize("language", tuple(OutputLanguage))
@pytest.mark.parametrize("theme", ["cadrumo-dark", "cadrumo-light"])
async def test_blocked_small_workbench_keeps_help_reachable_and_the_hungarian_quarter_worded(
    calculated: InstalledModeloWorkbench, language: OutputLanguage, theme: str
) -> None:
    with override_settings(cadrumo_output_language=language.value):
        screen = ModeloWorkbenchScreen(calculated, actions=calculated)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(80, 24)) as pilot:
            app.theme = theme
            await pilot.pause()
            await app.workers.wait_for_complete()
            await pilot.pause()
            assert screen.form is not None
            assert screen.form.verification is VerificationCompletenessStatus.BLOCKED
            assert blocking_count(screen.form) > 0
            keys = [child for child in screen.query_one(Footer).query("FooterKey") if child.display]
            help_keys = [child for child in keys if tr("tui.modelo.workbench.key.help") in str(child.render())]
            assert help_keys, [str(child.render()) for child in keys]
            assert all(0 <= key.region.x < key.region.right <= 80 and key.region.bottom <= 24 for key in help_keys)
            assert any("f8" in str(key.render()).lower() for key in keys), [str(key.render()) for key in keys]
            if language is OutputLanguage.HU:
                identity = " ".join(str(widget.render()) for widget in screen.query("#wb-identity Static"))
                assert "I. negyedév" in identity
                assert "1T" not in identity
                # Also exercise the unavailable filing window on this real
                # declaration projection. Its caption must leave the worded
                # quarter visible instead of silently clipping the identity.
                undated = screen.form.model_copy(update={"deadline": None})
                deadline = deadline_view(undated, language, recorded=False, width=80)
                assert deadline is not None
                name = fit_identity(undated, language, deadline, 80)
                assert "I. negyedév" in name.text
                assert not name.stacked
                assert cell_len(name.text) + 3 + cell_len(deadline.text) <= 80
            await pilot.press("question_mark")
            await pilot.pause()
            band = screen.query_one("#wb-help", Static)
            assert band.has_class("-expanded") and band.visible
            await pilot.press("question_mark")
            await pilot.pause()
            legend = screen.query_one("#wb-legend-text", Static)
            assert screen.has_class("-legend") and legend.visible
            assert str(legend.render()).strip()
            await pilot.press("escape")
            await pilot.pause()
            assert not screen.has_class("-legend")
            await pilot.press("i")
            await pilot.pause()
            assert isinstance(app.screen, WorkbenchIssuesScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert app.screen is screen
