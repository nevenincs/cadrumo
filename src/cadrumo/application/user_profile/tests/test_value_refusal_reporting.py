"""A refused value must arrive with the reason it was refused.

The per-type value rules used to be split: numeric and boolean lived in the
domain, while the enum and date rules lived inside the validation service,
and the ``email`` declaration -- the one content format the schema names for
itself -- was checked by nothing at all. A surface wanting to refuse a bad
value where the operator typed it therefore had nowhere to ask for most of
them, and would have had to restate the layout itself — a second opinion that
drifts from the door it is meant to anticipate.

They are now one authority, and this pins both ends of that: the validation
service must keep reporting exactly the issue codes it always did, and the
message it drops into the raised error must name what went wrong rather than
only that something did.
"""

from __future__ import annotations

import pytest

from cadrumo.application.user_profile.validation import (
    _ISSUE_CODE_BY_REFUSAL_KIND,
    BOOLEAN_VALUE_ISSUE_CODE,
    DATE_VALUE_ISSUE_CODE,
    EMAIL_VALUE_ISSUE_CODE,
    ENUM_VALUE_ISSUE_CODE,
    NUMERIC_VALUE_ISSUE_CODE,
    ProfileValidationService,
)

from ....core.errors import BaseSeverity
from ....core.setup_answers import PROFILE_OUTPUT_LANGUAGE_PATH
from ....domain.user_profile.errors import ProfileSchemaValidationError
from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.schema import ProfileValueRefusalKind
from ....domain.user_profile.values import UserProfileFact

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "00000000-0000-4000-8000-000000000000"


def _issues_for(path: str, value: object):
    schema = load_user_profile_schema()
    service = ProfileValidationService(schema=schema)
    report = service.validate_facts(_PROFILE_ID, (UserProfileFact(path=path, value=value),))
    return [issue for issue in report.issues if issue.severity is BaseSeverity.ERROR and issue.path == path]


def test_every_refusal_kind_has_an_issue_code() -> None:
    """A kind with no code would raise a KeyError the moment a value tripped it.

    The mapping is the join between the one rule that judges a value and the
    vocabulary the issue report speaks, so a kind added to the rule without
    an entry here turns a refusal that should have been reported into a
    crash on a taxpayer's own edit.
    """
    missing = [kind for kind in ProfileValueRefusalKind if kind not in _ISSUE_CODE_BY_REFUSAL_KIND]
    assert not missing, f"refusal kinds with no issue code: {missing}"


@pytest.mark.parametrize(
    ("path", "value", "expected_code"),
    [
        ("auth.fecha_validez", "15/03/1978", DATE_VALUE_ISSUE_CODE),
        (PROFILE_OUTPUT_LANGUAGE_PATH, "klingon", ENUM_VALUE_ISSUE_CODE),
        ("attribution_entity_socios.0.share_pct", "999", NUMERIC_VALUE_ISSUE_CODE),
        ("capabilities.llm_vision", "on", BOOLEAN_VALUE_ISSUE_CODE),
        ("identity.email", "banana", EMAIL_VALUE_ISSUE_CODE),
        ("identity.email", "no domain@example", EMAIL_VALUE_ISSUE_CODE),
        ("identity.email", "@example.com", EMAIL_VALUE_ISSUE_CODE),
    ],
)
def test_the_reported_code_is_unchanged_per_type(path: str, value: str, expected_code: str) -> None:
    """Routing the rules through one authority must not rename their faults.

    The codes are the report's contract; consumers branch on them. Moving
    where the verdict is FORMED is only safe if what is REPORTED stays the
    same, so each type is checked rather than assumed.
    """
    codes = [issue.code for issue in _issues_for(path, value)]
    assert expected_code in codes, f"{value!r} at {path} reported {codes}"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        ("auth.fecha_validez", "1978-03-15"),
        (PROFILE_OUTPUT_LANGUAGE_PATH, "en"),
        ("attribution_entity_socios.0.share_pct", "50"),
        ("capabilities.llm_vision", "true"),
        ("identity.name", "Ada Lovelace"),
        # The permissive half of the address rule, which is the half that
        # decides whether the field stays usable. Plus-addressing, a
        # multi-label domain, and a dotted local part are all ordinary
        # addresses real taxpayers hold, and a stricter grammar would make
        # the field uneditable for exactly those people.
        ("identity.email", "op@example.test"),
        ("identity.email", "ada.lovelace+aeat@correo.example.es"),
    ],
)
def test_an_acceptable_value_reports_no_value_fault(path: str, value: str) -> None:
    """The control: the rules must refuse bad values, not all values.

    Without this, a rule wired to refuse everything would satisfy every
    assertion above while making each field uneditable — which is the
    failure the whole change exists to remove.
    """
    value_codes = {
        DATE_VALUE_ISSUE_CODE,
        ENUM_VALUE_ISSUE_CODE,
        NUMERIC_VALUE_ISSUE_CODE,
        BOOLEAN_VALUE_ISSUE_CODE,
        EMAIL_VALUE_ISSUE_CODE,
    }
    faults = [issue for issue in _issues_for(path, value) if issue.code in value_codes]
    assert not faults, f"{value!r} at {path} was refused: {[issue.message for issue in faults]}"


def test_the_write_door_refusal_carries_the_issue_set_as_context() -> None:
    """The line is for reading; the context is for consumers that render all of it."""
    error = ProfileSchemaValidationError(
        "profile facts failed schema validation",
        context={"issue_codes": (BOOLEAN_VALUE_ISSUE_CODE,), "issue_paths": ("capabilities.llm_vision",)},
    )
    context = error.context
    assert context is not None
    assert context["issue_codes"] == (BOOLEAN_VALUE_ISSUE_CODE,)
