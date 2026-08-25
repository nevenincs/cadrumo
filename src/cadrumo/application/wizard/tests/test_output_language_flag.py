"""Output-language coverage for the profile setup wizard (David round-10 #530).

The David round-10 testimonial audit flagged the profile-creation wizard as
hardcoded Spanish with no ``--output-language`` support. This module proves
two properties of the shipped wizard:

* the ``--output-language`` flag is constrained to the supported-language
  set at the CLI boundary (an instructive gate, not a free-text option), and
* the wizard's operator-facing descriptor prose (titles, section headers,
  prompts) renders in the requested language through ``tr()`` and defaults to
  Spanish on a clean install.

Both drive real objects — the shipped ``_SETUP_OPTION_INFOS`` flag map, the
real ``SETUP_FLOW`` descriptor, and the real ``override_settings`` seam — with
no test doubles.
"""

from __future__ import annotations

import click
import pytest

from ....core.config import override_settings
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, clear_output_language_cache, tr
from ....tests.clean_install_fixtures import _clean_install
from ..catalogue import SETUP_FLOW
from ..commands import _SETUP_OPTION_INFOS

pytestmark = [pytest.mark.integration, pytest.mark.hex_application]

_TITLE_KEY = str(SETUP_FLOW.title)
_PROMPT_KEY = str(SETUP_FLOW.sections[0].questions[0].prompt)


def test_wizard_output_language_flag_constrains_to_supported_set() -> None:
    """The wizard ``--output-language`` flag is a Choice over the supported languages.

    A free-text option would let an operator pass an unsupported code that
    only fails deep in the verb body; constraining it at the CLI boundary
    makes the accepted set instructive on parse failure (per the
    CLI-boundary hinting rule) and consistent with every other
    subcommand's language flag.
    """
    info = _SETUP_OPTION_INFOS["output-language"]
    choice = info.click_type
    assert isinstance(choice, click.Choice), type(choice).__name__
    assert tuple(choice.choices) == tuple(SUPPORTED_OUTPUT_LANGUAGES)


def test_wizard_prose_localizes_and_resolves_under_both_overrides() -> None:
    """The wizard title and first prompt resolve and differ across languages.

    Structural assertions only: each key must resolve to authored prose
    (never its own key echo) in both languages, and the two renderings must
    differ — proving the descriptor is genuinely localized. The expected
    strings are never hardcoded, so a catalogue rewording or a catalogue
    re-sequencing of the first page cannot break the test without breaking
    the property it pins.
    """
    with override_settings(cadrumo_output_language="en"):
        title_en, prompt_en = tr(_TITLE_KEY), tr(_PROMPT_KEY)
    with override_settings(cadrumo_output_language="es"):
        title_es, prompt_es = tr(_TITLE_KEY), tr(_PROMPT_KEY)

    assert title_en != _TITLE_KEY and prompt_en != _PROMPT_KEY
    assert title_es != _TITLE_KEY and prompt_es != _PROMPT_KEY
    assert title_en != title_es
    assert prompt_en != prompt_es


__all__ = ["_clean_install"]


@pytest.mark.usefixtures("_clean_install")
def test_wizard_prose_defaults_to_spanish() -> None:
    """A clean install renders the wizard prose in Spanish with no override.

    The expected renderings are computed under an explicit Spanish override
    (key identity against the same catalogue), never hardcoded prose, so the
    assertion pins the DEFAULT-language mechanism rather than a wording.
    """
    with override_settings(cadrumo_output_language="es"):
        expected_title, expected_prompt = tr(_TITLE_KEY), tr(_PROMPT_KEY)
    clear_output_language_cache()

    assert tr(_TITLE_KEY) == expected_title
    assert tr(_PROMPT_KEY) == expected_prompt
