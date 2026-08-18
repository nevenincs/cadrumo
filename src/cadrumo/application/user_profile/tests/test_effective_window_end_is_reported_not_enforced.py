"""A ``valid_to`` that ends nothing is reported to the operator.

The effective-window resolvers order facts on ``valid_from`` and take the
last one per path. ``valid_to`` is not consulted, because expiry is only
meaningful against an ``as_of`` the caller supplies: resolving it against
the clock would make one record project different values on different
days, and these projections feed filing inputs whose effective instant is
the period being filed.

That decision leaves an operator able to record an end date that changes
nothing. These cases pin the two halves together — the value really does
keep resolving past its declared end, and the validation surface really
does say so — because either half alone is misleading. A warning with no
underlying behaviour is noise, and the behaviour with no warning is the
silent no-op this reports.

The scope is pinned too: an end date some later fact supersedes is
accurate bookkeeping and must NOT warn, or correct records read as
suspect.

Everything below drives the real schema and the real validation service.
"""

from __future__ import annotations

from datetime import date

import pytest

from ....domain.user_profile import (
    ProfileSetupState,
    UserProfileFact,
    UserProfileRecord,
    load_user_profile_schema,
)
from .. import ProfileValidationService, record_to_path_values

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

EXPIRY_NOT_ENFORCED = "effective_window_end_not_enforced"
_PATH = "contact.postcode"
_PROFILE_ID = "00000000-0000-4000-8000-000000000000"


def _warned_paths(*facts: UserProfileFact) -> set[str | None]:
    report = ProfileValidationService(schema=load_user_profile_schema()).validate_facts(_PROFILE_ID, facts)
    return {issue.path for issue in report.issues if issue.code == EXPIRY_NOT_ENFORCED}


def _record(*facts: UserProfileFact) -> UserProfileRecord:
    return UserProfileRecord(setup_state=ProfileSetupState.COMPLETE, profile_id=_PROFILE_ID, facts=facts)


def test_a_closed_window_still_projects_its_value() -> None:
    """The behaviour the warning describes, asserted directly.

    Without this the warning could be reporting a restriction that is
    actually enforced somewhere, which would make it wrong rather than
    merely noisy.
    """

    expired = UserProfileFact(path=_PATH, value="28001", valid_from=date(2019, 1, 1), valid_to=date(2020, 12, 31))

    assert record_to_path_values(_record(expired))[_PATH] == "28001"


def test_the_effective_facts_own_end_date_is_reported() -> None:
    """Nothing supersedes it, so the declared end never takes effect."""

    expired = UserProfileFact(path=_PATH, value="28001", valid_from=date(2019, 1, 1), valid_to=date(2020, 12, 31))

    assert _PATH in _warned_paths(expired)


def test_an_end_date_a_later_fact_supersedes_is_not_reported() -> None:
    """Anti-noise scope: the later ``valid_from`` already ends the earlier fact.

    Declaration order is deliberately the reverse of window order, so a
    check that keyed on position rather than window would warn here.
    """

    superseded = UserProfileFact(path=_PATH, value="28001", valid_from=date(2019, 1, 1), valid_to=date(2020, 12, 31))
    current = UserProfileFact(path=_PATH, value="08032", valid_from=date(2021, 1, 1))

    assert _warned_paths(current, superseded) == set()
    assert record_to_path_values(_record(current, superseded))[_PATH] == "08032"


def test_a_fact_carrying_no_end_date_is_not_reported() -> None:
    """Anti-tautology guard: the check is not a blanket warning on every fact."""

    open_ended = UserProfileFact(path=_PATH, value="28001", valid_from=date(2019, 1, 1))

    assert _warned_paths(open_ended) == set()


def test_a_superseding_fact_that_itself_ends_is_reported() -> None:
    """The report follows the effective fact, not the count of facts at the path."""

    earlier = UserProfileFact(path=_PATH, value="28001", valid_from=date(2019, 1, 1))
    latest_but_ending = UserProfileFact(
        path=_PATH,
        value="08032",
        valid_from=date(2021, 1, 1),
        valid_to=date(2022, 12, 31),
    )

    assert _PATH in _warned_paths(earlier, latest_but_ending)


def test_the_message_names_the_declared_end_and_the_way_to_supersede_it() -> None:
    """The operator needs the date they gave and the action that works.

    Asserted as structure — the date token and the field name — rather
    than as prose, so rewording the sentence does not fail this.
    """

    expired = UserProfileFact(path=_PATH, value="28001", valid_from=date(2019, 1, 1), valid_to=date(2020, 12, 31))
    report = ProfileValidationService(schema=load_user_profile_schema()).validate_facts(_PROFILE_ID, (expired,))

    message = next(issue.message for issue in report.issues if issue.code == EXPIRY_NOT_ENFORCED)

    assert "2020-12-31" in message
    assert "valid_from" in message
