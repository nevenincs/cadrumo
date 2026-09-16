"""Real-behaviour tests for non-interactive ``config profile edit``.

Each case reproduces a defect an operator hit driving the shipped CLI, and
asserts the invariant that defect broke. Evidence is read back through the
operator's own verbs -- ``view`` for facts, ``history`` for the evidence chain
-- rather than from internals.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from click.testing import Result

from .....application.user_profile.language_resolver import resolve_active_profile_output_language
from .isolated_storage_fixture import (
    COMPLETE_NATURAL_PERSON_FLAGS,
    profile_cli,
    profile_event_count,
    profile_facts,
    profile_view_document,
)
from .isolated_storage_fixture import live_cli_profile as live_cli_profile

pytestmark = [pytest.mark.integration, pytest.mark.hex_entrypoint, pytest.mark.usefixtures("live_cli_profile")]

_VALUES_UPDATED = "profile.values.updated"


def _edit(*flags: str) -> Result:
    return profile_cli("edit", "--quiet", *flags)


def _status(result: Result) -> str:
    assert result.exit_code == 0, result.output
    return str(json.loads(result.stdout)["result"]["status"])


def test_an_incomplete_profile_accepts_one_field_at_a_time() -> None:
    """A profile is born incomplete and must be fillable one flag per command.

    Reproduction: on a freshly created profile, ``edit --quiet --notes hola``
    and even ``edit --quiet --tax-id 12345678Z`` were refused, the first as an
    invalid ``--tax-id``. The patch path validated the whole answers model and
    the filing baseline, both of which judge a COMPLETE record, so the only
    edit that could succeed was one supplying every required field at once.
    ``complete-setup`` is what judges completeness, and it still must.
    """
    assert _status(_edit("--notes", "hola")) == "updated"
    assert _status(_edit("--tax-id", "12345678Z")) == "updated"

    facts = profile_facts()
    assert "identity.notes" in facts
    assert "identity.tax_id" in facts

    assert profile_cli("complete-setup").exit_code != 0, "an incomplete record must still be refused promotion"
    result = profile_view_document()["result"]
    assert isinstance(result, dict)
    assert result["setup_state"] == "incomplete"


def test_a_blank_optional_flag_clears_the_fact_and_records_one_change() -> None:
    """Naming a flag with an empty value is a request to clear that answer.

    Reproduction: ``edit --quiet --notes ""`` reported ``updated``, left the
    stored value in place, and still appended a value-change event -- the CLI
    could set an optional fact but never unset one, and said otherwise.
    """
    assert _status(_edit("--notes", "borrame")) == "updated"
    assert "identity.notes" in profile_facts()
    before = profile_event_count(_VALUES_UPDATED)

    assert _status(_edit("--notes", "")) == "updated"

    assert "identity.notes" not in profile_facts()
    assert profile_event_count(_VALUES_UPDATED) == before + 1


def test_an_edit_that_changes_nothing_writes_nothing() -> None:
    """Re-submitting the stored value must not grow the evidence chain.

    Reproduction: ``edit --quiet --name Ana`` against a profile already named
    Ana appended a value-change event and reported ``updated``, so the history
    recorded a revision for a write that changed nothing.
    """
    assert _status(_edit("--name", "Ana")) == "updated"
    before = profile_event_count(_VALUES_UPDATED)

    assert _status(_edit("--name", "Ana")) == "unchanged"

    assert profile_event_count(_VALUES_UPDATED) == before


def test_a_complete_profile_still_refuses_to_lose_a_required_answer() -> None:
    """Clearing is for optional answers; a required one stays guarded.

    Clearing was opened for blank optional flags, so this pins the other side:
    once the record is complete, ``edit --quiet --tax-id ""`` must refuse and
    leave the identifier in place.
    """
    assert _status(_edit(*COMPLETE_NATURAL_PERSON_FLAGS)) == "updated"
    assert profile_cli("complete-setup").exit_code == 0

    refused = _edit("--tax-id", "")

    assert refused.exit_code != 0
    assert "identity.tax_id" in profile_facts()


def test_a_blank_choice_flag_clears_the_language_preference_and_its_hint(tmp_path: Path) -> None:
    """A choice flag clears the same way a text flag does.

    Reproduction: ``edit --quiet --output-language ""`` was refused at parse
    time as an invalid choice, so a language preference could be set but
    never removed. Clearing it must also remove the non-secret hint that
    locked surfaces read, or they would keep speaking the old language.
    """
    hints = tmp_path / "cadrumo-storage" / "buckets"
    assert _status(_edit("--output-language", "ca")) == "updated"
    assert _resolved_language() == "ca"
    assert [hint.read_text(encoding="utf-8").strip() for hint in hints.glob("*/output-language.hint")] == ["ca"]

    assert _status(_edit("--output-language", "")) == "updated"

    assert "preferences.output_language" not in profile_facts()
    assert list(hints.glob("*/output-language.hint")) == []
    assert _resolved_language() is None


def _resolved_language() -> str | None:
    """The preference the renderer resolves for the live profile."""
    return resolve_active_profile_output_language()
