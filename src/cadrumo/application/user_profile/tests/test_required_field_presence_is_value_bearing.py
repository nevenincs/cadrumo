"""A schema-required field must carry a VALUE, not merely carry a fact.

A cleared field is a fact whose ``value`` is ``None``. While the completeness
check keyed presence on the fact existing, clearing a required field did not
merely evade the check — it SATISFIED it, because the cleared fact counted as
present. Adding a cleared fact therefore silenced the very issue that the
field's absence raises, which is the opposite of what a required field means.

These tests pin the three states apart (set, cleared, absent) and pin the
divergence from the old rule directly, so a revert cannot leave them green.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ....domain.user_profile.loader import load_user_profile_schema
from ....domain.user_profile.values import ProfileSetupState, UserProfileFact, UserProfileRecord
from ..overview import build_profile_overview
from ..validation import ProfileValidationService

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

REQUIRED_FIELD_MISSING = "required_field_missing"
TAX_ID = "identity.tax_id"
IVA_REGIME = "iva.regime"
_PROFILE_ID = "00000000-0000-4000-8000-000000000000"
_SCHEMA = load_user_profile_schema()
_STAMP = datetime(2026, 1, 1, tzinfo=UTC)


def _service() -> ProfileValidationService:
    return ProfileValidationService(schema=load_user_profile_schema())


def _missing(*facts: UserProfileFact) -> set[str | None]:
    report = _service().validate_facts(_PROFILE_ID, facts)
    return {issue.path for issue in report.issues if issue.code == REQUIRED_FIELD_MISSING}


def test_a_required_field_carrying_a_value_is_present() -> None:
    assert TAX_ID not in _missing(UserProfileFact(path=TAX_ID, value="12345678Z"))


def test_a_cleared_required_field_is_missing() -> None:
    """The defect: a value=None fact used to count as the field being present."""
    assert TAX_ID in _missing(UserProfileFact(path=TAX_ID, value=None))


def test_an_absent_required_field_is_missing() -> None:
    assert TAX_ID in _missing()


def test_clearing_and_never_setting_are_indistinguishable_to_the_check() -> None:
    """Whichever way the value came to be absent, the field is not satisfied.

    Stated as an equality rather than two memberships so a future change
    cannot fix one arm and leave the other reporting differently.
    """
    assert _missing(UserProfileFact(path=TAX_ID, value=None)) == _missing()


def test_a_cleared_fact_cannot_silence_the_issue_its_absence_raises() -> None:
    """The sharpest form of the defect, on the other singleton required field.

    ``iva.regime`` is reported missing when no fact exists for it. Adding a
    CLEARED fact for it used to make that report disappear — a requirement
    affirmatively satisfied with nothing.
    """
    baseline = _missing(UserProfileFact(path=TAX_ID, value="12345678Z"))
    assert IVA_REGIME in baseline

    with_cleared = _missing(
        UserProfileFact(path=TAX_ID, value="12345678Z"),
        UserProfileFact(path=IVA_REGIME, value=None),
    )
    assert IVA_REGIME in with_cleared


def test_the_check_does_not_merely_echo_which_paths_carry_a_fact() -> None:
    """Anti-tautology: pin the divergence from the superseded predicate.

    The old rule was ``{key(fact.path) for fact in facts}`` — fact-bearing
    rather than value-bearing. Recomputing it here as a control proves the
    service is not simply reporting fact presence: under the old rule the
    cleared path IS present, and the service must still call it missing.
    Reverting the production predicate makes this assertion fail, which is
    what stops the suite going green on the defect again.
    """
    facts = (UserProfileFact(path=TAX_ID, value=None),)

    superseded_present = {fact.path for fact in facts}
    assert TAX_ID in superseded_present, "control: the old rule counts a cleared fact as present"

    assert TAX_ID in _missing(*facts), "the check must not agree with the old rule"


@pytest.mark.parametrize("value", [None, ""])
def test_the_enforcing_check_agrees_with_the_overview_the_operator_is_shown(value: str | None) -> None:
    """The two surfaces must not disagree about what "present" means.

    The overview computes ``missing_required`` from the same record with
    its own predicate. While the two disagreed, the operator could be
    shown a field marked missing that the write door considered
    satisfied. This pins them together for both ways a value can be
    empty, so a later change to either one cannot re-open the gap
    silently.
    """
    facts = (UserProfileFact(path=TAX_ID, value=value),)
    record = UserProfileRecord(
        schema_id=_SCHEMA.id,
        schema_version=_SCHEMA.version,
        profile_id=_PROFILE_ID,
        setup_state=ProfileSetupState.COMPLETE,
        facts=facts,
        created_at=_STAMP,
        updated_at=_STAMP,
    )
    overview = build_profile_overview(record)

    assert TAX_ID in overview.missing_required
    assert TAX_ID in _missing(*facts)
