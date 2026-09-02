"""Focused unit tests for the wizard translation-audit helpers.

The audit-wizard-translations / audit-cli-translations surface
exercises the helpers indirectly through three high-level tests in
`test_wizard_translations_resolve.py`. This module pins the helpers'
own contracts at the unit level so a regression in the key-walker's
derived-key rule, the regex grammar for CLI-key extraction, or the
locale-resolution dispatch does not silently let translation gaps
slip past the audit.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cadrumo.core.i18n import Translatable as tr
from dev.locales.wizard_translation_audit import (
    _FIXED_RUNTIME_KEYS,
    _resolves_in,
    _walk_keys,
    cli_keys_referenced_in_source,
)
from ..models import WizardChoice, WizardFlow, WizardQuestion, WizardSection, WizardWidget
from ._support import EmptyAnswersBase

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def _build_minimal_flow(*, with_help: bool = False, with_choice_description: bool = False) -> WizardFlow:
    """Construct a one-flow, one-section, one-question fixture flow.

    Every Translatable starts with ``wizard.test.`` so the flow's
    ``_validate_translatable_prefix`` model_validator passes.
    """
    question = WizardQuestion(
        id="example",
        widget=WizardWidget.SELECT,
        prompt=tr("wizard.test.example.prompt"),
        help=tr("wizard.test.example.help") if with_help else None,
        choices=(
            WizardChoice(
                value="yes",
                label=tr("wizard.test.example.choices.yes.label"),
                description=(tr("wizard.test.example.choices.yes.description") if with_choice_description else None),
            ),
        ),
        default="yes",
        answer_type=str,
    )
    section = WizardSection(
        id="main",
        title=tr("wizard.test.main.title"),
        questions=(question,),
    )
    return WizardFlow(
        id="test",
        title=tr("wizard.test.title"),
        description=tr("wizard.test.description"),
        sections=(section,),
        answers_model=EmptyAnswersBase,
    )


# ---------------------------------------------------------------------------
# _walk_keys
# ---------------------------------------------------------------------------


def test_walk_keys_returns_only_fixed_runtime_keys_for_empty_flows() -> None:
    """An empty flows iterable contributes only the fixed runtime-error keys."""
    keys = _walk_keys(())

    assert keys == _FIXED_RUNTIME_KEYS


def test_walk_keys_extracts_every_translatable_from_a_minimal_flow() -> None:
    """Every Translatable in the flow descriptor appears in the walked key set,
    plus the descriptor-derived flag-help and cli.config.help keys."""
    flow = _build_minimal_flow(with_help=True, with_choice_description=True)

    keys = _walk_keys((flow,))

    expected_keys = {
        "wizard.test.title",
        "wizard.test.description",
        "wizard.test.main.title",
        "wizard.test.example.prompt",
        "wizard.test.example.help",
        "wizard.test.example.choices.yes.label",
        "wizard.test.example.choices.yes.description",
        # Descriptor-derived flag help (one per question).
        "wizard.test.flags.example.help",
        # Descriptor-derived cli-config help (one per flow).
        "cli.config.test.help",
    }
    walked = set(keys)
    assert expected_keys.issubset(walked), expected_keys - walked
    # Fixed runtime keys are always included.
    for fixed_key in _FIXED_RUNTIME_KEYS:
        assert fixed_key in walked


def test_walk_keys_omits_optional_help_when_question_help_is_none() -> None:
    """A question with ``help=None`` does NOT contribute its (non-existent)
    help key to the walked set."""
    flow = _build_minimal_flow(with_help=False, with_choice_description=False)

    keys = _walk_keys((flow,))

    assert "wizard.test.example.help" not in keys


def test_walk_keys_omits_optional_choice_description_when_none() -> None:
    """A choice with ``description=None`` does NOT contribute its key."""
    flow = _build_minimal_flow(with_help=False, with_choice_description=False)

    keys = _walk_keys((flow,))

    assert "wizard.test.example.choices.yes.description" not in keys


def test_walk_keys_includes_derived_flag_help_for_every_question() -> None:
    """The derived ``wizard.{flow}.flags.{question}.help`` key is added
    per-question even when the question has no explicit help text."""
    flow = _build_minimal_flow(with_help=False)

    keys = _walk_keys((flow,))

    assert "wizard.test.flags.example.help" in keys


def test_walk_keys_includes_derived_cli_config_help_per_flow() -> None:
    """One ``cli.config.{flow}.help`` is appended per flow."""
    flow = _build_minimal_flow()

    keys = _walk_keys((flow,))

    assert "cli.config.test.help" in keys


# ---------------------------------------------------------------------------
# _resolves_in
# ---------------------------------------------------------------------------


def test_resolves_in_returns_false_for_a_key_that_does_not_exist() -> None:
    """An unknown key returns the raw key from ``tr`` (the python-i18n
    fallback), and ``_resolves_in`` must report False on that condition."""
    assert _resolves_in("en", "wizard.bogus.does.not.exist.anywhere") is False


def test_resolves_in_returns_true_for_a_real_key_in_every_locale() -> None:
    """Pick a representative key known to be present in every locale —
    the CLI app-help for the root namespace. Walks every project locale
    to ensure the helper does not just say True for English."""
    for locale in ("en", "es", "ca", "hu"):
        assert _resolves_in(locale, "cli.config.list.help") is True


# ---------------------------------------------------------------------------
# cli_keys_referenced_in_source
# ---------------------------------------------------------------------------


def test_cli_keys_referenced_in_source_returns_a_non_empty_sorted_tuple() -> None:
    """The extractor must surface a non-empty tuple of CLI keys, sorted
    lexicographically for deterministic audit output."""
    keys = cli_keys_referenced_in_source()

    assert keys
    assert isinstance(keys, tuple)
    assert list(keys) == sorted(keys)


def test_cli_keys_referenced_in_source_only_returns_cli_dot_prefixed_strings() -> None:
    """Every returned key matches the documented ``cli.<group>.<rest>`` shape."""
    keys = cli_keys_referenced_in_source()

    for key in keys:
        assert key.startswith("cli.")
        # At least one dot beyond the cli. prefix (i.e., a group + rest).
        assert key.count(".") >= 2


def test_cli_keys_referenced_in_source_extracts_representative_namespaces() -> None:
    """Spot-check that representative keys from distinct CLI namespaces
    are surfaced — guards against regressions in the regex grammar."""
    keys = set(cli_keys_referenced_in_source())

    assert "cli.config.list.help" in keys
    assert "cli.config.errors.no_active_profile" in keys


def test_cli_keys_referenced_in_source_omits_f_string_interpolated_keys() -> None:
    """The regex matches literal quoted strings only. An f-string key
    like ``f"cli.config.{flow.id}.help"`` is not captured (those are
    walked through the wizard descriptor catalogue instead)."""
    keys = set(cli_keys_referenced_in_source())

    # An f-string-interpolated key literal would contain `{` which the
    # regex's character class explicitly excludes; if any made it
    # through, this would surface here.
    for key in keys:
        assert "{" not in key
        assert "}" not in key


def test_cli_keys_referenced_in_source_root_resolves_under_entrypoints_cli() -> None:
    """Sanity-check that the helper's root path resolution lands on the
    real entrypoints/cli directory (the regex walks every .py under it)."""
    from dev.locales.wizard_translation_audit import _cli_entrypoints_root

    root = _cli_entrypoints_root()
    assert root.is_dir()
    assert root.name == "cli"
    assert (root / "__init__.py").is_file()
    assert isinstance(root, Path)
