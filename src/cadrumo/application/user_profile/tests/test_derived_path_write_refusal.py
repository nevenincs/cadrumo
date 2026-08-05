"""The write door refuses a value at an engine-derived path, and only a value.

Two properties, and the second is why this module exists separately from the
end-to-end override proof.

The refusal itself: a path the schema declares derived is computed from source
facts the operator edits elsewhere, so a value written straight at it would
suppress the computation. That was demonstrated on the real calculate path
before this rule existed and is pinned there.

The exemption: a CLEAR is admitted. The validator judges the whole MERGED fact
set on every edit rather than the incoming delta, so a fact stored at a derived
path before this rule existed is re-judged on every later edit to any other
field. Refusing a clear as well would leave no way to remove it -- the profile
could not be edited, cleared, or promoted at all, with no in-band remedy. A
closing audit measured that and this module pins the fix.

The exemption gives nothing back to the defect. The injectors compute always
and overwrite whatever the fact index holds, so a stored value at a derived
path is already inert for the calculation; the rule exists to stop a value
being written, and a clear writes none.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from ....domain.user_profile import UserProfileFact, load_user_profile_schema
from .._validation import DERIVED_FIELD_ISSUE_CODE, ProfileValidationService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE_ID = "3f2a1b4c-5d6e-4f70-8a9b-0c1d2e3f4a5b"
_DERIVED_PATH = "renta_family.descendientes_minimos_aggregate_2024"
_OPERATOR_PATH = "renta_family.cotizaciones_ss_madre_2024"


def _service() -> ProfileValidationService:
    return ProfileValidationService(schema=load_user_profile_schema())


def _refusals(*facts: UserProfileFact) -> list[str]:
    report = _service().validate_facts(_PROFILE_ID, facts)
    refused: list[str] = []
    for issue in report.issues:
        if issue.code != DERIVED_FIELD_ISSUE_CODE:
            continue
        # `path` is optional on the issue model; a derived-field refusal that
        # named nothing would be unactionable, so pin it rather than filter it.
        assert issue.path is not None, f"derived-field refusal carried no path: {issue}"
        refused.append(issue.path)
    return refused


def test_a_value_written_at_a_derived_path_is_refused() -> None:
    """The rule's whole purpose: the law's figure cannot be displaced by a typed one."""
    assert _refusals(UserProfileFact(path=_DERIVED_PATH, value=Decimal("999"))) == [_DERIVED_PATH]


def test_the_refusal_names_the_surface_that_edits_the_real_facts() -> None:
    """An instructive refusal, not a bare rejection.

    The operator is being told they may not write here; without naming where the
    value actually comes from, the refusal leaves them with no next action.
    """
    report = _service().validate_facts(
        _PROFILE_ID,
        (UserProfileFact(path=_DERIVED_PATH, value=Decimal("999")),),
    )
    message = next(issue.message for issue in report.issues if issue.code == DERIVED_FIELD_ISSUE_CODE)
    assert "descendiente" in message


def test_clearing_a_derived_path_is_admitted() -> None:
    """The remedy. Without it a stale fact cannot be removed by any door.

    This is the exemption's reason for existing, and inverting it would restore
    the state the closing audit measured: a profile bricked by a fact nobody can
    reach.
    """
    assert _refusals(UserProfileFact(path=_DERIVED_PATH, value=None)) == []


def test_a_stale_valued_fact_still_blocks_an_unrelated_edit() -> None:
    """The hazard the exemption does NOT pretend to solve, pinned so it stays visible.

    The merged set is judged whole, so a stale VALUED fact refuses an edit the
    operator did not make. The recovery path is to clear it first, which the
    test above admits. Asserting this rather than leaving it undocumented is the
    difference between an accepted consequence and an unnoticed one.
    """
    assert _refusals(
        UserProfileFact(path=_DERIVED_PATH, value=Decimal("999")),
        UserProfileFact(path="identity.name", value="Ana"),
    ) == [_DERIVED_PATH]


def test_a_kept_operator_field_in_the_same_section_is_untouched() -> None:
    """Anti-vacuity: the refusal must discriminate, not blanket the section.

    Two year-suffixed fields in this same section are genuine operator input and
    were deliberately not declared derived. If the pattern namespace ever widened
    to swallow them, every assertion above would still pass while a legitimate
    entry surface had been closed.
    """
    assert _refusals(UserProfileFact(path=_OPERATOR_PATH, value=Decimal("900"))) == []
