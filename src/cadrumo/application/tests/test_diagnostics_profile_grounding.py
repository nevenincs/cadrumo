"""Diagnostics names missing profile fields, not bare counts or raw paths.

The profile readiness diagnostic reports fields the active profile has not
answered. Its summary must name them, and a field reaching the row through the
wizard-report fallback must be labelled the same way as one reaching it through
the record probe, rather than surfacing as a raw dotted path.
"""

from __future__ import annotations

import pytest

from ...domain.user_profile.loader import load_user_profile_schema
from ..diagnostics import _grounded_profile_key_summary
from ..user_profile.preflight import build_profile_preflight_requirement

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

#: A schema-declared path the wizard report can carry in its missing tuples.
_KNOWN_PATH = "identity.tax_id"


def test_the_known_path_has_a_label_that_differs_from_the_path() -> None:
    """Anchor the fixture: the assertions below are vacuous if they are equal."""
    requirement = build_profile_preflight_requirement(
        _KNOWN_PATH,
        schema=load_user_profile_schema(),
    )

    assert requirement.label != _KNOWN_PATH


def test_a_known_profile_path_is_rendered_with_its_operator_label() -> None:
    """The fallback branch names the field, not only its dotted path."""
    rendered = _grounded_profile_key_summary(_KNOWN_PATH)

    expected_label = build_profile_preflight_requirement(
        _KNOWN_PATH,
        schema=load_user_profile_schema(),
    ).label
    assert rendered.startswith(f"{_KNOWN_PATH} ")
    assert expected_label in rendered


def test_the_rendered_form_keeps_the_path_first_so_deduplication_still_works() -> None:
    """The enrolment de-duplication compares the segment before the separator.

    Were the label placed first, an enrolment key already named by a required
    finding would stop matching and would be reported twice.
    """
    rendered = _grounded_profile_key_summary(_KNOWN_PATH)

    assert rendered.split(" — ", 1)[0] == _KNOWN_PATH


def test_an_unresolvable_key_is_returned_unchanged_rather_than_guessed() -> None:
    """A key naming no schema field must not acquire an invented label."""
    unknown = "no_such_section.no_such_field"

    assert _grounded_profile_key_summary(unknown) == unknown
