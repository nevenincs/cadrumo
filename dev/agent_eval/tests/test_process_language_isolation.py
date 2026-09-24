"""Evaluation tests leave the process's output language as they found them.

These tests share one pytest process with the product suites, which assert the
Spanish default. Two things could carry a language out of here and into those
suites: a CLI invocation whose ``--language`` flag outlives the invocation, and a
fixture that pins a language beyond the module that asked for it. The second is
not hypothetical: naming the secure-SQL fixture module in ``pytest_plugins``
registered it for the whole session, and its autouse English pin then applied
to every test collected afterwards, in any directory.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import pytest

from cadrumo.core.config import load_settings, override_settings, settings_override
from cadrumo.core.external_constants import DEFAULT_OUTPUT_LANGUAGE, OUTPUT_LANGUAGE_ENV_VAR, OutputLanguage
from cadrumo.core.i18n.render import normalise_supported_language, output_language
from cadrumo.entrypoints.cli.tests.cli_runner import invoke_cached_cli

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint]

_STATUS_ARGV = ("config", "profile", "status")


@dataclass(frozen=True)
class _LanguageState:
    """Every process-wide input the output-language resolver reads."""

    environment: str | None
    override_active: bool
    settings_language: OutputLanguage | None
    settings_language_explicit: bool
    resolved: str


def _language_state() -> _LanguageState:
    settings = load_settings()
    return _LanguageState(
        environment=os.environ.get(OUTPUT_LANGUAGE_ENV_VAR),
        override_active=settings_override.get() is not None,
        settings_language=settings.cadrumo_output_language,
        settings_language_explicit="cadrumo_output_language" in settings.model_fields_set,
        resolved=str(output_language()),
    )


def _ambient_language() -> str:
    """The language this process resolves when nothing in the test pinned one."""
    return str(normalise_supported_language(os.environ.get(OUTPUT_LANGUAGE_ENV_VAR)) or DEFAULT_OUTPUT_LANGUAGE)


def _flag_language(resolved: str) -> OutputLanguage:
    """English, unless English is already resolved, so the flag is observable."""
    return next(language for language in (OutputLanguage.EN, *OutputLanguage) if language != resolved)


def test_no_fixture_from_another_module_pins_the_output_language() -> None:
    """This module asks for no language fixture, so it must resolve the ambient language.

    A fixture module registered session-wide by another evaluation module would
    reach this test too; its English pin is exactly what the product suites saw.
    """
    assert _language_state().resolved == _ambient_language()


def test_a_language_flagged_cli_invocation_leaves_process_language_unchanged() -> None:
    """``--language`` localises its own invocation and nothing after it."""
    before = _language_state()
    flag_language = _flag_language(before.resolved)

    baseline = invoke_cached_cli(list(_STATUS_ARGV))
    flagged = invoke_cached_cli(["--language", flag_language.value, *_STATUS_ARGV])
    after = _language_state()
    repeated = invoke_cached_cli(list(_STATUS_ARGV))

    assert baseline.exit_code == 0, baseline.output
    assert flagged.exit_code == 0, flagged.output
    assert repeated.exit_code == 0, repeated.output
    # The flag must be seen to act, or an unchanged state proves nothing.
    assert flagged.output != baseline.output
    assert after == before
    assert repeated.output == baseline.output


def test_the_language_snapshot_detects_a_pinned_language() -> None:
    """The state comparison above can fail: a pinned language changes the snapshot."""
    before = _language_state()
    flag_language = _flag_language(before.resolved)

    with override_settings(cadrumo_output_language=flag_language):
        pinned = _language_state()

    assert pinned != before
    assert pinned.resolved == flag_language.value
    assert _language_state() == before
