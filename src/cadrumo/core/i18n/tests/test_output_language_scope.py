"""Verify the test-suite's language pin survives an installed settings override.

``output_language_scope`` and ``activate_output_language`` pin the output
language by writing ``CADRUMO_OUTPUT_LANGUAGE``. That is the right mechanism --
it needs no ContextVar Token, so a switch fired from inside a Textual
message-pump callback works across the asyncio-Context boundary where
``override_settings`` cannot.

What the env write alone does NOT survive is an ``override_settings`` block,
because ``load_settings()`` returns the override in preference to anything the
environment says. ``cadrumo/conftest.py`` opens one for the whole session, so
the pin was inert in every test that used it: the language silently resolved to
the configured default and any assertion about a non-default language was
really asserting about Spanish.

These are the gates for that. They are worth their own module because the
failure is invisible from the call site -- the helper reports nothing, the
block runs, and only the resolved language is wrong.
"""

from __future__ import annotations

import pytest

from ....tests.env_scope import activate_output_language, output_language_scope
from ...config import override_settings
from ...external_constants import OutputLanguage
from ..render import output_language

pytestmark = [pytest.mark.unit, pytest.mark.hex_core]


def test_the_language_pin_wins_over_an_installed_settings_override() -> None:
    """The scope pins the language even while an override is active.

    The override names a DIFFERENT language explicitly, which is the sharpest
    form of the conflict: the pin has to beat a deliberate operator choice, not
    merely a default that flowed through.
    """
    with override_settings(cadrumo_output_language=OutputLanguage.ES):
        assert output_language() == "es"
        with output_language_scope(OutputLanguage.EN):
            assert output_language() == "en"


def test_a_mid_block_switch_wins_over_an_installed_settings_override() -> None:
    """The mid-block stimulus reaches the override too, not just the env.

    This is the half the message-pump callers depend on: the switch happens
    inside the block rather than at its edge, so it cannot be expressed as a
    scope and has no Token to reset.
    """
    with override_settings(cadrumo_output_language=OutputLanguage.ES), output_language_scope(OutputLanguage.EN):
        assert output_language() == "en"
        activate_output_language(OutputLanguage.ES)
        assert output_language() == "es"


def test_the_override_gets_its_own_language_back_when_the_scope_exits() -> None:
    """Restoration is the other half: a pin that leaks is a pin that lies.

    Both directions matter. An override that explicitly chose a language must
    get that exact language back, and an override that never mentioned one must
    not come back carrying an explicit choice it never made -- otherwise
    "unset" and "chose the default" stop being distinguishable for every
    subsequent test in the session.
    """
    with override_settings(cadrumo_output_language=OutputLanguage.ES) as explicit:
        with output_language_scope(OutputLanguage.EN):
            activate_output_language(OutputLanguage.EN)
        assert output_language() == "es"
        assert "cadrumo_output_language" in explicit.model_fields_set

    with override_settings(cadrumo_strict_security=False) as unset:
        assert "cadrumo_output_language" not in unset.model_fields_set
        with output_language_scope(OutputLanguage.EN):
            assert output_language() == "en"
        assert "cadrumo_output_language" not in unset.model_fields_set
