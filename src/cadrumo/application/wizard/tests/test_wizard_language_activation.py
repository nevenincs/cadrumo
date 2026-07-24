"""Wiring tests for the mid-walk output-language activation.

The interactive setup flow asks for the output language on its first page.
Committing that answer must re-activate the language so the remaining pages
render in the chosen language (the operator's language-first flow), unless an
explicit ``--output-language`` flag or the ``CADRUMO_OUTPUT_LANGUAGE``
environment already pins the language for the whole run.

The full-screen rendering half (the frontend fires the hook and re-renders the
next page) is proven by the adapter's Pilot suite. These tests prove the
wiring half: the command builds and threads the activator, the activator
switches the language for the remainder of the run, precedence suppresses it,
and a non-language commit never activates. Expectations are resolved through the
i18n API at test time, never hardcoded prose.
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterator, Sequence
from pathlib import Path

import pytest
import typer

from ....core.config import override_settings
from ....core.flows import FlowMode
from ....core.i18n import OUTPUT_LANGUAGE_ENV_VAR, clear_output_language_cache, output_language, tr
from ....tests.secure_sql import isolated_profile_storage_root
from ...flows import FlowDefinition, FlowState
from .._catalogue import SETUP_FLOW
from .._commands import _build_mid_walk_language_activation, build_wizard_command
from ._support import scripted_run_over_setup_definition
from .test_setup_runtime import _scripted_answers_for_individual_declaration

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

# A locale key whose value differs between English and the default (Spanish),
# so a switch is observable as a changed rendering rather than a no-op.
_SAMPLE_COPY_KEY = "wizard.setup.flags.output-language.help"


@pytest.fixture
def _isolated_backend(tmp_path: Path) -> Iterator[Path]:
    with isolated_profile_storage_root(tmp_path=tmp_path) as storage_root:
        yield storage_root


@pytest.fixture
def _clean_language_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Guarantee no ambient language pin so the activator is built."""
    monkeypatch.delenv(OUTPUT_LANGUAGE_ENV_VAR, raising=False)
    clear_output_language_cache()
    yield
    clear_output_language_cache()


def test_activator_switches_language_and_next_copy_resolves_in_it(_clean_language_env: None) -> None:
    """Committing the output-language answer re-renders subsequent copy in it."""
    with contextlib.ExitStack() as stack:
        activate = _build_mid_walk_language_activation({}, stack)
        assert activate is not None
        baseline = output_language()
        assert baseline != "en"  # the default is Spanish, so switching to English is observable

        switched = activate("output-language", "en")

        assert switched is True
        assert output_language() == "en"
        # The no-flash property: the next page's copy now resolves in English,
        # with no intermediate default-locale resolution.
        assert tr(_SAMPLE_COPY_KEY) == tr(_SAMPLE_COPY_KEY, locale="en")


def test_explicit_output_language_flag_suppresses_the_activator() -> None:
    """An explicit ``--output-language`` value keeps the existing chain in charge."""
    with contextlib.ExitStack() as stack:
        assert _build_mid_walk_language_activation({"output_language": "en"}, stack) is None


def test_pinned_output_language_setting_suppresses_the_activator() -> None:
    """A pinned ``CADRUMO_OUTPUT_LANGUAGE`` (settings) suppresses the mid-walk switch."""
    with override_settings(cadrumo_output_language="en"), contextlib.ExitStack() as stack:
        assert _build_mid_walk_language_activation({}, stack) is None


def test_activator_ignores_non_language_pages(_clean_language_env: None) -> None:
    """A non-language commit never activates and never enters an override.

    The committed value may be a secret page's raw answer; the activator must
    ignore it entirely for any page other than ``output-language``.
    """
    with contextlib.ExitStack() as stack:
        activate = _build_mid_walk_language_activation({}, stack)
        assert activate is not None
        baseline = output_language()

        assert activate("spouse-tax-id", "44444444A") is False
        assert output_language() == baseline

        # An unrecognised language token on the language page is also inert.
        assert activate("output-language", "klingon") is False
        assert output_language() == baseline


def _capturing_runner(tokens: Sequence[str], recorder: dict[str, object]):
    """A runner that records the threaded activator and simulates the mid-walk hook."""

    def _runner(
        definition: FlowDefinition,
        *,
        mode: FlowMode,
        registered_values: object = None,
        on_language_activated: object = None,
        checkpoint_store: object = None,
    ) -> FlowState:
        del registered_values, checkpoint_store
        recorder["activator"] = on_language_activated
        if callable(on_language_activated):
            recorder["switched"] = on_language_activated("output-language", "en")
            recorder["language_after"] = output_language()
            recorder["non_language"] = on_language_activated("spouse-tax-id", "44444444A")
        state, _projection = scripted_run_over_setup_definition(definition, tokens, mode=mode)
        return state

    return _runner


def test_interactive_command_threads_a_live_activator_when_unpinned(
    _isolated_backend: Path,
    _clean_language_env: None,
) -> None:
    """The interactive command threads a working activator into the frontend runner."""
    tokens = list(_scripted_answers_for_individual_declaration())
    recorder: dict[str, object] = {}
    command = build_wizard_command(SETUP_FLOW, mode="create", interactive_flow_runner=_capturing_runner(tokens, recorder))
    app = typer.Typer()
    app.command()(command)

    typer.main.get_command(app).main(args=["operator"], standalone_mode=False)

    assert recorder["activator"] is not None
    assert recorder["switched"] is True
    assert recorder["language_after"] == "en"
    assert recorder["non_language"] is False


def test_interactive_command_omits_the_activator_when_language_is_flagged(
    _isolated_backend: Path,
) -> None:
    """An explicit ``--output-language`` flag means no mid-walk activator is wired."""
    tokens = list(_scripted_answers_for_individual_declaration())
    recorder: dict[str, object] = {}
    command = build_wizard_command(SETUP_FLOW, mode="create", interactive_flow_runner=_capturing_runner(tokens, recorder))
    app = typer.Typer()
    app.command()(command)

    typer.main.get_command(app).main(args=["operator", "--output-language", "en"], standalone_mode=False)

    assert recorder["activator"] is None
