"""Clean-install language integration coverage for the setup wizard."""

from __future__ import annotations

import pytest

from cadrumo.application.wizard.models import WizardFlow
from cadrumo.application.wizard.tests.registry_setup_flow_support import registry_setup_flow as registry_setup_flow

from ....core.config import override_settings
from ....core.i18n.render import clear_output_language_cache, tr
from .clean_install_fixtures import clean_install as clean_install

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]


@pytest.mark.usefixtures("clean_install")
def test_wizard_prose_defaults_to_spanish(*, registry_setup_flow: WizardFlow) -> None:
    """A clean install renders the wizard prose in Spanish with no override."""
    title_key = str(registry_setup_flow.title)
    prompt_key = str(registry_setup_flow.sections[0].questions[0].prompt)
    with override_settings(cadrumo_output_language="es"):
        expected_title, expected_prompt = tr(title_key), tr(prompt_key)
    clear_output_language_cache()

    assert tr(title_key) == expected_title
    assert tr(prompt_key) == expected_prompt
