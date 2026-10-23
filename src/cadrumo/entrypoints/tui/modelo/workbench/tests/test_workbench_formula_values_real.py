"""The editor explains a calculated zero through the production reader and encrypted storage."""

from __future__ import annotations

from collections.abc import Iterator
from decimal import Decimal

import pytest
from rich.cells import cell_len
from textual.errors import NoWidget
from textual.geometry import Region
from textual.pilot import Pilot
from textual.widgets import Button, Footer, Input, Static
from textual.widgets._footer import FooterKey

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
from ..factory import InstalledModeloWorkbench
from ..header import blocking_count, deadline_view, fit_identity
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


_FOOTER_BARRIER_LIMIT = 400
"""Bounds a footer that never settles; a loaded machine settles in a handful of pauses."""


def _footer_names_the_bindings(screen: ModeloWorkbenchScreen) -> bool:
    """Whether the footer holds one key per shown action, as it composes them from the screen's current bindings."""
    expected: dict[str, str] = {}
    for active in screen.active_bindings.values():
        if active.binding.show:
            expected.setdefault(active.binding.action, active.binding.key)
    shown = [key.key for key in screen.query_one(Footer).query(FooterKey) if not key.has_class("-command-palette")]
    # An empty footer has not been described yet; this page always names its keys.
    return bool(shown) and sorted(shown) == sorted(expected.values())


def _footer_placed(screen: ModeloWorkbenchScreen) -> bool:
    """Whether the screen's last layout placed every shown footer key; a key mounted since then has no place yet."""
    for key in screen.query_one(Footer).query(FooterKey):
        if key.display:
            try:
                screen.find_widget(key)
            except NoWidget:
                return False
    return True


def _footer_reading(screen: ModeloWorkbenchScreen) -> tuple[tuple[str, str, bool, Region], ...]:
    return tuple(
        (key.key, str(key.render()), key.display, key.region) for key in screen.query_one(Footer).query(FooterKey)
    )


async def _settled_footer_keys[ResultT](pilot: Pilot[ResultT], screen: ModeloWorkbenchScreen) -> list[FooterKey]:
    """The footer's shown keys once the read has finished and the footer has caught up with it, laid out.

    The footer answers a bindings change by queueing a rebuild for after the
    next refresh, and the rebuild removes every key before it mounts the new
    ones. A pause returns once the screen has handled what was queued when it
    began, so on a loaded machine the rebuild can still be queued, or be
    between its removal and its mount, when the pause returns; and a key
    it mounted has no place on screen until the next layout. The keys are
    read only once no worker is running, the footer names exactly the
    screen's shown bindings, the layout has placed each of them, and a pause
    has left every key where it was.
    """
    previous: tuple[tuple[str, str, bool, Region], ...] | None = None
    for _ in range(_FOOTER_BARRIER_LIMIT):
        await pilot.pause()
        reading = _footer_reading(screen)
        if (
            all(worker.is_finished for worker in pilot.app.workers)
            and _footer_names_the_bindings(screen)
            and _footer_placed(screen)
        ):
            if reading == previous:
                return [key for key in screen.query_one(Footer).query(FooterKey) if key.display]
            previous = reading
        else:
            previous = None
    raise AssertionError(
        f"the footer never settled; last showing {[str(key.render()) for key in screen.query(FooterKey)]}"
    )


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
            keys = await _settled_footer_keys(pilot, screen)
            assert screen.form is not None
            assert screen.form.verification is VerificationCompletenessStatus.BLOCKED
            assert blocking_count(screen.form) > 0
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
