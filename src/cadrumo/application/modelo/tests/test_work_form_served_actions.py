"""Every action an issue line serves reads the same on any surface: no command, option or placeholder to fill.

The check view's lines are shown by every frontend, so the sentence that says what to do names no `aeat`
command, no `--option` and no `<placeholder>`. The command line words a step with its command from the
catalogue, apart from these lines.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

from ....core.external_constants import SUPPORTED_OUTPUT_LANGUAGES, OutputLanguage
from ....core.i18n.render import tr
from ....domain.calculations.registry.authority import PinnedAuthorityOperation, bundled_indexed_authority
from ..work_form_findings import FINDING_KIND_ACTION_LOCALE_KEYS, FINDING_MESSAGE_ACTION_LOCALE_KEYS
from ..work_form_issue_lines import form_issue_lines
from .test_work_form_gate_agreement import _checked_form, _every_note, _Note, _revision, _work_unit

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_COMMAND_FORMS = ("aeat ", "--", "<", "`")
"""The lowercase command is told from the agency, whose name is written in capitals."""


@pytest.fixture(autouse=True)
def _pinned_authority() -> Iterator[None]:
    with bundled_indexed_authority().operation():
        yield


def _names_a_command(text: str) -> bool:
    return any(form in text for form in _COMMAND_FORMS)


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("note", _every_note(), ids=lambda note: note.reason)
def test_the_action_of_every_note_line_names_no_command(
    operation: PinnedAuthorityOperation, note: _Note, language: str
) -> None:
    unit = _work_unit(operation)
    form = _checked_form(operation, _revision(operation, unit, note.issue()))

    lines = [line for line in form_issue_lines(form, OutputLanguage(language)) if line.from_calculation]

    for line in lines:
        assert not _names_a_command(line.action), (note.reason, line.action)


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
def test_the_action_of_every_finding_names_no_command(language: str) -> None:
    keys = {*FINDING_MESSAGE_ACTION_LOCALE_KEYS.values(), *FINDING_KIND_ACTION_LOCALE_KEYS.values()}

    assert keys
    for key in sorted(keys):
        assert not _names_a_command(tr(key, locale=language)), key


@pytest.mark.parametrize("language", SUPPORTED_OUTPUT_LANGUAGES)
@pytest.mark.parametrize("reason", ["credit_source_disagreement", "precedence_tier_divergence"])
def test_a_disagreement_line_says_to_accept_the_value_in_use_and_say_why(
    operation: PinnedAuthorityOperation, reason: str, language: str
) -> None:
    unit = _work_unit(operation)
    form = _checked_form(operation, _revision(operation, unit, _Note(reason).issue()))

    (line,) = [line for line in form_issue_lines(form, OutputLanguage(language)) if line.finding_id is not None]

    assert line.finding_id is not None
    served = tr("application.modelo.work_form.served_action." + reason, locale=language)
    assert served in line.action
    assert line.finding_id not in line.action
    assert tr("application.modelo.calc_diagnostic." + reason + ".what_to_do", locale=language) not in line.action
