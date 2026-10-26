"""Setup wording read from the real locale catalogues in every supported language."""

from __future__ import annotations

import re

import pytest

from cadrumo_client.contracts.failure_categories import DependencyFailureCategory

from ...core.external_constants import SUPPORTED_OUTPUT_LANGUAGES
from ...core.i18n.render import lookup_translation
from ..dependency_contracts import (
    DependencyBlockedReason,
    DependencyCheckMode,
    DependencyItemKind,
    DependencyNote,
    DependencyRecoveryAction,
    DependencyStaleReason,
    DependencyState,
    DependencyStatusRow,
)
from ..dependency_registry import BROWSER_DECLARATION, LOCAL_AI_DECLARATION, dependency_item_declarations
from ..dependency_wording import (
    DEPENDENCY_WORDING_ROOT,
    dependency_action_key,
    dependency_desktop_pointer,
    dependency_failure_key,
    dependency_held_sentence,
    dependency_name_key,
    dependency_note_key,
    dependency_retry_sentence,
    dependency_row_wording,
    dependency_space_sentence,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_INTERNAL = re.compile(r"(?i)\b(runtime|provision\w*|playwright|headless|digest|ollama|chromium|api)\b|_")


def _all_keys() -> tuple[str, ...]:
    """Every key the wording renders; a key spelled differently here fails the lookup below."""
    root = DEPENDENCY_WORDING_ROOT
    return (
        *(f"{root}.state.{state.value}" for state in DependencyState),
        *(f"{root}.stale.{reason.value}" for reason in DependencyStaleReason),
        *(f"{root}.blocked.{reason.value}" for reason in DependencyBlockedReason),
        *(dependency_failure_key(category) for category in DependencyFailureCategory),
        *(dependency_action_key(action) for action in DependencyRecoveryAction),
        *(dependency_note_key(note) for note in DependencyNote),
        f"{root}.in_desktop",
        f"{root}.retry",
        f"{root}.space_needed",
        *(dependency_name_key(d) for d in dependency_item_declarations()),
    )


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_every_sentence_and_label_is_authored_plainly_in_every_language(locale: str) -> None:
    for key in _all_keys():
        text = lookup_translation(key, locale=locale)
        assert text is not None and text.strip(), f"{key} has no {locale} text"
        assert text != key
        assert not _INTERNAL.search(re.sub(r"%\{\w+\}", "", text)), f"{key} in {locale} uses an internal term: {text!r}"


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_placeholders_survive_translation(locale: str) -> None:
    assert "7" in dependency_retry_sentence(attempt=3, delay_s=7, locale=locale)
    assert "3" in dependency_retry_sentence(attempt=3, delay_s=7, locale=locale)
    sentence = dependency_space_sentence(required="5.2 GB", free="1.1 GB", locale=locale)
    assert "5.2 GB" in sentence and "1.1 GB" in sentence


def test_a_row_renders_its_name_reason_and_one_button() -> None:
    failed = DependencyStatusRow(
        item_id="browser",
        kind=DependencyItemKind.BROWSER,
        mode=DependencyCheckMode.FULL,
        state=DependencyState.FAILED,
        failure_category=DependencyFailureCategory.DISK_FULL,
        recovery=DependencyRecoveryAction.TRY_AGAIN,
        recovery_action_id="operator.provision.browser",
    )
    wording = dependency_row_wording(failed, BROWSER_DECLARATION, locale="en")
    assert wording.name == "Browser for the tax agency website"
    assert wording.sentence == "There is not enough free disk space."
    assert wording.action == "Try again"
    assert wording.note is None
    spanish = dependency_row_wording(failed, BROWSER_DECLARATION, locale="es")
    assert spanish.action == "Volver a intentarlo"
    with pytest.raises(ValueError):
        dependency_row_wording(failed, LOCAL_AI_DECLARATION, locale="en")

    ready = DependencyStatusRow(
        item_id="local_ai",
        kind=DependencyItemKind.LOCAL_AI,
        mode=DependencyCheckMode.FULL,
        state=DependencyState.READY,
        note=DependencyNote.DOWNLOADED_NOT_LOADED,
    )
    declaration = next(d for d in dependency_item_declarations() if d.item_id == ready.item_id)
    rendered = dependency_row_wording(ready, declaration, locale="en")
    assert (rendered.name, rendered.sentence, rendered.note, rendered.action) == (
        "Local AI",
        "Ready.",
        "Downloaded, not loaded yet.",
        None,
    )


def _desktop_row() -> DependencyStatusRow:
    """The row the role reports for a local AI only the desktop sets up."""
    return DependencyStatusRow(
        item_id="local_ai",
        kind=DependencyItemKind.LOCAL_AI,
        mode=DependencyCheckMode.QUICK,
        state=DependencyState.ABSENT,
        recovery=DependencyRecoveryAction.SET_UP_IN_DESKTOP,
        recovery_action_id="operator.provision.local_ai",
    )


def test_a_row_that_only_the_desktop_sets_up_points_to_the_desktop_and_names_no_command() -> None:
    row = _desktop_row()
    wording = dependency_row_wording(row, LOCAL_AI_DECLARATION, locale="en")

    assert wording.action == "Set up in the Cadrumo desktop app"
    assert dependency_desktop_pointer(locale="en") == "Set it up in the Cadrumo desktop app."
    assert dependency_held_sentence(row, LOCAL_AI_DECLARATION, locale="en") == (
        "Local AI: Not set up yet. Set it up in the Cadrumo desktop app."
    )


@pytest.mark.parametrize("locale", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_desktop_pointer_is_worded_in_every_language_and_only_where_the_desktop_sets_up(locale: str) -> None:
    held = dependency_held_sentence(_desktop_row(), LOCAL_AI_DECLARATION, locale=locale)

    assert held.endswith(dependency_desktop_pointer(locale=locale))
    assert "aeat" not in held
    absent = DependencyStatusRow(
        item_id="browser",
        kind=DependencyItemKind.BROWSER,
        mode=DependencyCheckMode.QUICK,
        state=DependencyState.ABSENT,
        recovery=DependencyRecoveryAction.SET_UP,
        recovery_action_id="operator.provision.browser",
    )
    assert dependency_desktop_pointer(locale=locale) not in dependency_held_sentence(
        absent, BROWSER_DECLARATION, locale=locale
    )
