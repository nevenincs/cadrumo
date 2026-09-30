"""A language switch changes what the workbench writes, never what it addresses.

The form builder is proven to localize labels and headings; this asserts the
invariant where the filer meets it, on the mounted workbench, across all FOUR
shipped languages. Catalan and Hungarian are exactly where a missing catalogue
entry shows up, and a fallback is not a failure here: a label may resolve to
the official Spanish wording and say so. What a language may NOT change is
which boxes are shown, in what order, with what value and state, or which
controls exist and in what keyboard order.

THE COMPARISON IS AGAINST ONE SEEDED STORAGE, not four. Reading four languages
from four separately seeded profiles would differ in bucket identity and
creation instants, so any difference found could not be attributed to
language -- which is the only thing this module is about.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from textual.widget import Widget

from ....application.modelo.work_form_models import ModeloFormTextDisclosure, ModeloWorkForm, address_key
from ....core.config import override_settings
from ....core.external_constants import OutputLanguage
from ....tests.terminal_sizes import TERMINAL_ORDINARY
from ..components.host import ScreenHostApp
from ..modelo.workbench.installed import InstalledModeloWorkbench
from ..modelo.workbench.screen import ModeloWorkbenchScreen
from .modelo_workbench_session import real_workbench

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_LANGUAGES = tuple(OutputLanguage)


@pytest.fixture(scope="module")
def workbench(tmp_path_factory: pytest.TempPathFactory) -> Iterator[InstalledModeloWorkbench]:
    """One seeded declaration, read in every shipped language."""
    root = tmp_path_factory.mktemp("localized")
    with real_workbench(root) as installed:
        yield installed


@pytest.fixture(scope="module")
def forms_by_language(workbench: InstalledModeloWorkbench) -> dict[OutputLanguage, ModeloWorkForm]:
    """The same declaration's form, read once per shipped language."""
    return {language: workbench.load(language).form for language in _LANGUAGES}


def test_every_shipped_language_reads_the_same_declaration(
    forms_by_language: dict[OutputLanguage, ModeloWorkForm],
) -> None:
    """Boxes, their order, values, states and what may be done about them are language-free."""
    shapes = {
        language: tuple(
            (address_key(field.address), field.box, field.value, field.origin, field.editability)
            for field in form.fields()
        )
        for language, form in forms_by_language.items()
    }
    assert len(set(shapes.values())) == 1, "a language changed which boxes are shown or how they stand"
    assert next(iter(shapes.values())), "the declaration read no boxes, so the comparison proves nothing"


def test_the_words_actually_change_across_the_shipped_catalogues(
    forms_by_language: dict[OutputLanguage, ModeloWorkForm],
) -> None:
    """The control: invariance is cheap when nothing varies, so the labels must differ by language."""
    labels = {
        language: tuple(field.label.text for field in form.fields()) for language, form in forms_by_language.items()
    }
    assert labels[OutputLanguage.ES] != labels[OutputLanguage.EN], "Spanish and English read identically"
    assert labels[OutputLanguage.ES] != labels[OutputLanguage.HU], "Spanish and Hungarian read identically"


def test_each_form_says_which_language_served_each_label(
    forms_by_language: dict[OutputLanguage, ModeloWorkForm],
) -> None:
    """A form records the language asked for, and a label that fell back to Spanish says so."""
    assert {language: form.language for language, form in forms_by_language.items()} == {
        language: language for language in _LANGUAGES
    }
    spanish = forms_by_language[OutputLanguage.ES]
    assert all(field.label.disclosure is not ModeloFormTextDisclosure.SPANISH_FALLBACK for field in spanish.fields()), (
        "a Spanish read cannot fall back to Spanish"
    )


@pytest.mark.asyncio
async def test_the_workbench_mounts_the_same_controls_in_every_language(workbench: InstalledModeloWorkbench) -> None:
    """Translation may change the words in a control, never which controls exist or their keyboard order."""
    chains: dict[OutputLanguage, tuple[str | None, ...]] = {}
    mounted: dict[OutputLanguage, tuple[str, ...]] = {}
    for language in _LANGUAGES:
        with override_settings(cadrumo_output_language=language.value):
            screen = ModeloWorkbenchScreen(workbench, actions=workbench)
            app = ScreenHostApp(screen)
            async with app.run_test(size=TERMINAL_ORDINARY) as pilot:
                for _ in range(200):
                    await pilot.pause()
                    if screen.form is not None:
                        break
                assert screen.form is not None
                chains[language] = tuple(widget.id for widget in app.screen.focus_chain)
                mounted[language] = tuple(
                    sorted(widget.id for widget in app.screen.query(Widget) if widget.id is not None)
                )
                app.exit(None)

    assert len(set(chains.values())) == 1, "a language offers a different keyboard order: " + "; ".join(
        f"{language.value}={chain}" for language, chain in chains.items()
    )
    assert len(set(mounted.values())) == 1, "a language mounts a different control set"
