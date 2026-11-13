"""A declaration the workbench cannot read is said so on the screen, which stays open.

The workbench reads a real stored declaration through the production reader.
Only the failing dependency is replaced: the read raises the profile record
integrity error that a shared authority republished mid-run produces, first
before the declaration was ever shown and then on a re-read after it was shown
(its loading line is gone by then).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from textual.widgets import Static

from ......application.modelo.casilla_help import ModeloCasillaHelpCardV1
from ......application.modelo.workbench_read import ModeloWorkbenchFormReadV1
from ......application.user_profile.capsule_record import ProfileRecordIntegrityError
from ......core.casilla_id import CasillaId
from ......core.config import override_settings
from ......core.external_constants import OutputLanguage
from ......core.i18n.render import tr
from .....tests.modelo_operator_work_storage import SeededOperatorWork, seeded_operator_work
from ....components.host import ScreenHostApp
from ....tests.modelo_workbench_session import application_workbench
from ....tests.settling import settle, settle_until
from ..factory import InstalledModeloWorkbench, ModeloWorkbenchSourceV1
from ..screen import ModeloWorkbenchScreen

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_GENERATION_CROSSED = "profile record access crossed the pinned authority generation boundary"


@dataclass
class _RepublishedAuthority:
    """The real source until told that the shared authority was republished, then its integrity refusal."""

    real: ModeloWorkbenchSourceV1
    republished: bool = False

    def read_form(self, language: OutputLanguage) -> ModeloWorkbenchFormReadV1:
        if self.republished:
            raise ProfileRecordIntegrityError(_GENERATION_CROSSED)
        return self.real.read_form(language)

    def help_card(
        self,
        casilla_id: CasillaId,
        *,
        registry_revision_id: str,
        calculation_revision_id: str | None,
        language: OutputLanguage,
    ) -> ModeloCasillaHelpCardV1:
        return self.real.help_card(
            casilla_id,
            registry_revision_id=registry_revision_id,
            calculation_revision_id=calculation_revision_id,
            language=language,
        )


@pytest.fixture
def republishing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> Iterator[tuple[InstalledModeloWorkbench, _RepublishedAuthority]]:
    with seeded_operator_work(tmp_path) as work:
        installed = _installed(work)
        source = _RepublishedAuthority(installed._source)
        monkeypatch.setattr(installed, "_source", source)
        yield installed, source


def _installed(work: SeededOperatorWork) -> InstalledModeloWorkbench:
    return application_workbench(work.work_unit, operation=work.operation)


def _text(screen: ModeloWorkbenchScreen, selector: str) -> str:
    return str(screen.query_one(selector, Static).render())


@pytest.mark.asyncio
async def test_a_declaration_that_cannot_be_read_at_first_says_so_where_it_was_loading(
    republishing: tuple[InstalledModeloWorkbench, _RepublishedAuthority],
) -> None:
    installed, source = republishing
    source.republished = True
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(installed, actions=installed)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await settle_until(
                pilot,
                lambda: _text(screen, "#wb-loading") == tr("workspace.modelo.read_failed", locale="en"),
                "the unreadable declaration to be said so",
            )
            await settle(pilot)
            assert screen.is_attached
            assert screen.form is None


@pytest.mark.asyncio
async def test_a_re_read_that_fails_after_the_form_was_shown_keeps_the_form_and_says_so_on_the_notice_line(
    republishing: tuple[InstalledModeloWorkbench, _RepublishedAuthority],
) -> None:
    installed, source = republishing
    with override_settings(cadrumo_output_language="en"):
        screen = ModeloWorkbenchScreen(installed, actions=installed)
        app = ScreenHostApp(screen)
        async with app.run_test(size=(120, 40)) as pilot:
            await settle_until(pilot, lambda: screen.form is not None, "the workbench to read its declaration")
            shown = screen.form
            assert not screen.query("#wb-loading"), "the loading line is gone once the form is shown"

            source.republished = True
            assert await screen._read() is False
            await settle(pilot)

            assert _text(screen, "#wb-notice") == tr("workspace.modelo.read_failed", locale="en")
            assert screen.form is shown
            assert screen.is_attached

            # A calculation's follow-up read says the read failed rather than reporting on the form held before.
            await screen._read_after(screen._load, frozenset(), "modelo.work.calculate")
            await settle(pilot)
            assert _text(screen, "#wb-notice") == tr("workspace.modelo.read_failed", locale="en")
