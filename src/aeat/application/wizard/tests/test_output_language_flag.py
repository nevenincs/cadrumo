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

from collections.abc import Iterator
from pathlib import Path

import click
import pytest

from ....core.config import override_settings
from ....core.external_constants import OUTPUT_LANGUAGE_ENV_VAR
from ....core.i18n import SUPPORTED_OUTPUT_LANGUAGES, clear_output_language_cache, tr
from ....tests.env_scope import scoped_env_var
from ....tests.secure_sql import isolated_sessionless_storage_root
from .._catalogue import SETUP_FLOW
from .._commands import _SETUP_OPTION_INFOS

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


def test_wizard_prose_renders_english_under_english_override() -> None:
    """The wizard title and first prompt render in English under an English override."""
    with override_settings(aeat_output_language="en"):
        assert tr(_TITLE_KEY) == "Setup wizard"
        assert tr(_PROMPT_KEY) == "Entity type"


def test_wizard_prose_renders_spanish_under_spanish_override() -> None:
    """The wizard title and first prompt render in Spanish under a Spanish override."""
    with override_settings(aeat_output_language="es"):
        assert tr(_TITLE_KEY) == "Asistente de configuración"
        assert tr(_PROMPT_KEY) == "Tipo de entidad"


@pytest.fixture
def _clean_install(tmp_path: Path) -> Iterator[None]:
    """Model a clean install: no active profile, no forced-language env var.

    The test/CI shell exports ``AEAT_OUTPUT_LANGUAGE=en``; a clean install
    carries neither that env var nor an active profile, so both are stripped
    to exercise the Spanish settings default.
    """
    with scoped_env_var(OUTPUT_LANGUAGE_ENV_VAR, None), isolated_sessionless_storage_root(tmp_path=tmp_path):
        clear_output_language_cache()
        try:
            yield
        finally:
            clear_output_language_cache()


@pytest.mark.usefixtures("_clean_install")
def test_wizard_prose_defaults_to_spanish() -> None:
    """A clean install renders the wizard prose in Spanish with no override."""
    assert tr(_TITLE_KEY) == "Asistente de configuración"
    assert tr(_PROMPT_KEY) == "Tipo de entidad"
