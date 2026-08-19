"""Real-behavior tests: every profile-readiness surface reads presence the same way.

Three surfaces decided whether a required field carried a value, and they
disagreed on the one input an operator can produce by accident. The
schema-driven completeness reader and the overview it feeds treated any
non-empty string as filled, while the profile-key authority the CLI status
gate consumes stripped before deciding. A required identity holding only
spaces was therefore simultaneously complete (service and overview) and
missing (CLI), which is a readiness fork rather than a display difference:
the surface that refuses is not the surface that persists.

These tests pin the whole cross-surface set against one canonical
predicate, so tightening or loosening presence has to move every reader at
once or fail here.
"""

from __future__ import annotations

import pytest

from ....domain.user_profile import ProfileSetupState, UserProfileFact, UserProfileRecord, load_user_profile_schema
from .._completeness import missing_required_field_paths, profile_value_is_present
from .._keys_validation import validate_profile_values
from .._overview import build_profile_overview

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
_TAX_ID_PATH = "identity.tax_id"

# Whitespace an operator can produce without seeing it: plain spaces, a tab,
# and a non-breaking-space-free newline. Each is a value the field-level
# parsers would reject, so none of them may read as a filled required field.
_BLANK_VALUES = ("   ", "\t", "\n", " \t\n ")


@pytest.mark.parametrize("blank", _BLANK_VALUES)
def test_canonical_predicate_refuses_whitespace_only(blank: str) -> None:
    assert profile_value_is_present(blank) is False


def test_canonical_predicate_accepts_a_value_with_surrounding_whitespace() -> None:
    assert profile_value_is_present("  12345678Z  ") is True


@pytest.mark.parametrize("blank", _BLANK_VALUES)
def test_completeness_reports_a_whitespace_only_required_field_missing(blank: str) -> None:
    missing = missing_required_field_paths(load_user_profile_schema(), {_TAX_ID_PATH: blank})

    assert _TAX_ID_PATH in missing


@pytest.mark.parametrize("blank", _BLANK_VALUES)
def test_overview_and_key_authority_agree_on_whitespace_only(blank: str) -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(UserProfileFact(path=_TAX_ID_PATH, value=blank),),
    )

    overview = build_profile_overview(record)
    field = next(view for section in overview.sections for view in section.fields if view.path == _TAX_ID_PATH)
    cli = validate_profile_values({_TAX_ID_PATH: blank})

    assert field.present is False
    assert _TAX_ID_PATH in overview.missing_required
    assert cli.valid is False
    assert _TAX_ID_PATH in cli.missing_required


def test_overview_and_key_authority_agree_on_a_real_value() -> None:
    record = UserProfileRecord(
        setup_state=ProfileSetupState.COMPLETE,
        profile_id=_PROFILE_ID,
        facts=(UserProfileFact(path=_TAX_ID_PATH, value="12345678Z"),),
    )

    overview = build_profile_overview(record)
    field = next(view for section in overview.sections for view in section.fields if view.path == _TAX_ID_PATH)

    assert field.present is True
    assert _TAX_ID_PATH not in overview.missing_required
    assert _TAX_ID_PATH in validate_profile_values({_TAX_ID_PATH: "12345678Z"}).present_required


def test_cleared_and_absent_values_are_equally_absent() -> None:
    schema = load_user_profile_schema()

    assert _TAX_ID_PATH in missing_required_field_paths(schema, {})
    assert _TAX_ID_PATH in missing_required_field_paths(schema, {_TAX_ID_PATH: ""})
    assert profile_value_is_present(None) is False
