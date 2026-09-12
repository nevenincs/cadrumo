"""Clean-install language integration coverage for the setup wizard."""

from __future__ import annotations

import pytest

from ....application.wizard.catalogue import SETUP_FLOW
from ....core.config import override_settings
from ....core.i18n.render import clear_output_language_cache, tr
from .clean_install_fixtures import clean_install

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_TITLE_KEY = str(SETUP_FLOW.title)
_PROMPT_KEY = str(SETUP_FLOW.sections[0].questions[0].prompt)


@pytest.mark.usefixtures("clean_install")
def test_wizard_prose_defaults_to_spanish() -> None:
    """A clean install renders the wizard prose in Spanish with no override."""
    with override_settings(cadrumo_output_language="es"):
        expected_title, expected_prompt = tr(_TITLE_KEY), tr(_PROMPT_KEY)
    clear_output_language_cache()

    assert tr(_TITLE_KEY) == expected_title
    assert tr(_PROMPT_KEY) == expected_prompt
