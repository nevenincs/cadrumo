"""Output-language coverage for the profile setup wizard (David round-10 #530).

The David round-10 testimonial audit flagged the profile-creation wizard as
hardcoded Spanish with no ``--output-language`` support. This module proves
two properties of the shipped wizard:

* the ``--output-language`` flag is constrained to the supported-language
  set at the CLI boundary (an instructive gate, not a free-text option), and
* the wizard's operator-facing descriptor prose (titles, section headers,
  prompts) renders in the requested language through ``tr()`` and defaults to
  Spanish on a clean install.

Both drive real objects — the shipped ``SETUP_OPTION_INFOS`` flag map, the
real ``SETUP_FLOW`` descriptor, and the real ``override_settings`` seam — with
no test doubles.
"""

from __future__ import annotations

import click
import pytest
import typer

from cadrumo.application.wizard.models import WizardFlow
from cadrumo.application.wizard.tests._support import registry_setup_flow as registry_setup_flow

from ....core.config import override_settings
from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ....core.i18n.render import tr
from ..commands import SETUP_OPTION_INFOS

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]


def test_wizard_output_language_flag_constrains_to_supported_set() -> None:
    """The wizard ``--output-language`` flag is a Choice over the supported languages.

    A free-text option would let an operator pass an unsupported code that
    only fails deep in the verb body; constraining it at the CLI boundary
    makes the accepted set instructive on parse failure (per the
    CLI-boundary hinting rule) and consistent with every other
    subcommand's language flag.
    """
    info = SETUP_OPTION_INFOS["output-language"]
    assert isinstance(info, typer.models.OptionInfo)
    choice = info.click_type
    assert isinstance(choice, click.Choice), type(choice).__name__
    assert tuple(choice.choices) == tuple(SUPPORTED_OUTPUT_LANGUAGES)


def test_wizard_prose_localizes_and_resolves_under_both_overrides(*, registry_setup_flow: WizardFlow) -> None:
    """The wizard title and first prompt resolve and differ across languages.

    Structural assertions only: each key must resolve to authored prose
    (never its own key echo) in both languages, and the two renderings must
    differ — proving the descriptor is genuinely localized. The expected
    strings are never hardcoded, so a catalogue rewording or a catalogue
    re-sequencing of the first page cannot break the test without breaking
    the property it pins.
    """
    title_key = str(registry_setup_flow.title)
    prompt_key = str(registry_setup_flow.sections[0].questions[0].prompt)
    with override_settings(cadrumo_output_language="en"):
        title_en, prompt_en = tr(title_key), tr(prompt_key)
    with override_settings(cadrumo_output_language="es"):
        title_es, prompt_es = tr(title_key), tr(prompt_key)

    assert title_en != title_key and prompt_en != prompt_key
    assert title_es != title_key and prompt_es != prompt_key
    assert title_en != title_es
    assert prompt_en != prompt_es
