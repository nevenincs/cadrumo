"""The onboarding run's advisories, and the distinctions they must not collapse.

Three separate confusions are gated here, each of which would put a false
statement in front of an operator:

* A REFUSED pair reported as an empty one. The register walker refuses a page
  whose grid declares more records than it rendered, so a refused pair also
  reports zero rows; reading that zero as "nothing filed" is the silent
  under-report this feature exists to remove.
* An expected-but-not-found warning raised from the register's offered option
  list. That list's scoping to the authenticated NIF is unconfirmed, so an alert
  derived from it could be pure noise — and an advisory only earns trust if every
  firing is a real finding.
* Several filings for one period reported as a problem. A complementaria is
  lawful, so it is INFO; a warning would put a red flag on legal behaviour.

The run model and its advisories are pure functions over an already-composed
run, so they are exercised without a live session.
"""

from __future__ import annotations

import pytest

from ....core.register_scoping_signal import RegisterScopingSignal
from ....core.filed_history_discovery_signal import FiledHistoryDiscoverySignal
from ....core.json_contract import NoticeSeverity
from ..filed_data_capture import (
    FiledHistoryOnboardingRun,
    FiledHistoryPairOutcome,
    FiledPeriodSelectionRow,
    expected_but_not_found_notice,
    found_more_than_expected_notices,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_PROFILE = (FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,)
_REGISTER = (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,)
_BOTH = (
    FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,
    FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,
)


def _pair(
    *,
    modelo: str = "303",
    ejercicio: int = 2025,
    signals: tuple[FiledHistoryDiscoverySignal, ...] = _PROFILE,
    row_count: int = 0,
    refused: bool = False,
) -> FiledHistoryPairOutcome:
    return FiledHistoryPairOutcome(
        modelo=modelo,
        ejercicio=ejercicio,
        signals=signals,
        row_count=row_count,
        captured_count=row_count,
        refused=refused,
        failure_type="SedeParseError" if refused else None,
        failure_message="refusing an under-reported filing history" if refused else None,
    )


# ------------------------------------------- refusal is never a legitimate empty


def test_a_refused_pair_is_not_a_genuine_empty() -> None:
    refused = _pair(refused=True)
    assert refused.row_count == 0
    assert refused.is_a_genuine_empty is False


def test_a_pair_that_answered_with_no_rows_is_a_genuine_empty() -> None:
    assert _pair(row_count=0, refused=False).is_a_genuine_empty is True


def test_the_run_partitions_refusals_away_from_empties() -> None:
    run = FiledHistoryOnboardingRun(
        pairs=(
            _pair(modelo="303", ejercicio=2025, refused=True),
            _pair(modelo="100", ejercicio=2024, row_count=0),
            _pair(modelo="130", ejercicio=2024, row_count=3),
        ),
    )
    assert {pair.modelo for pair in run.refused_pairs} == {"303"}
    assert {pair.modelo for pair in run.genuinely_empty_pairs} == {"100"}
    # The refused pair appears in neither the empty set nor the captured count.
    assert not set(run.refused_pairs) & set(run.genuinely_empty_pairs)


# --------------------------------------------- expected-but-not-found asymmetry


def test_the_warning_fires_for_a_profile_expected_pair_with_no_rows() -> None:
    notice = expected_but_not_found_notice(FiledHistoryOnboardingRun(pairs=(_pair(signals=_PROFILE),)))
    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING
    assert notice.code == "live.filed.pull_all.expected_but_not_found"
    # Machine-queryable context is the contract; the message is localised prose.
    assert notice.context is not None
    assert notice.context["missing_count"] == "1"
    assert notice.context["pairs"] == "303/2025"


def test_the_warning_never_fires_for_a_register_only_pair() -> None:
    # The register's option list may carry no information about this taxpayer, so
    # an alert derived from its emptiness could be pure noise.
    assert expected_but_not_found_notice(FiledHistoryOnboardingRun(pairs=(_pair(signals=_REGISTER),))) is None


def test_the_warning_still_fires_when_a_pair_carries_both_signals() -> None:
    # Being ALSO offered by the register must not downgrade a profile expectation.
    notice = expected_but_not_found_notice(FiledHistoryOnboardingRun(pairs=(_pair(signals=_BOTH),)))
    assert notice is not None
    assert notice.severity is NoticeSeverity.WARNING


def test_the_warning_never_fires_for_a_refused_pair() -> None:
    """A refusal is not an answer, so it is not a missing filing either.

    The pair did not report "no filings"; it failed to report at all. Naming it
    here would tell the operator a filing is missing when nothing established
    that, while its real failure row travels separately.
    """
    run = FiledHistoryOnboardingRun(pairs=(_pair(signals=_PROFILE, refused=True),))
    assert expected_but_not_found_notice(run) is None


def test_the_warning_stays_quiet_when_every_expected_pair_produced_rows() -> None:
    run = FiledHistoryOnboardingRun(pairs=(_pair(signals=_PROFILE, row_count=2),))
    assert expected_but_not_found_notice(run) is None


def test_the_warning_names_every_missing_pair_not_just_a_count() -> None:
    run = FiledHistoryOnboardingRun(
        pairs=(
            _pair(modelo="303", ejercicio=2025),
            _pair(modelo="130", ejercicio=2024),
            _pair(modelo="100", ejercicio=2023, signals=_REGISTER),
        ),
    )
    notice = expected_but_not_found_notice(run)
    assert notice is not None
    assert notice.context is not None
    named = notice.context["pairs"]
    assert "303/2025" in named
    assert "130/2024" in named
    # The register-only pair is absent from the named set.
    assert "100/2023" not in named
    assert notice.context["missing_count"] == "2"


# ------------------------------------------------- found-more-than-expected tier


def _selection_row(*, raw: int, selected: int = 1, period: str = "1T") -> FiledPeriodSelectionRow:
    return FiledPeriodSelectionRow(
        modelo="130",
        ejercicio=2026,
        period=period,
        raw_row_count=raw,
        selected_count=selected,
        winning_expediente_id="13020260420WXYZ9999QRST8888",
    )


def test_a_period_with_several_filings_is_reported_as_info_never_warning() -> None:
    """A complementaria is lawful, so this is information, not a problem.

    Pinned explicitly because the natural instinct is to warn on a duplicate, and
    warning here would put a red flag on behaviour AEAT itself permits.
    """
    notices = found_more_than_expected_notices(
        FiledHistoryOnboardingRun(selection_rows=(_selection_row(raw=3),)),
    )
    assert len(notices) == 1
    assert notices[0].severity is NoticeSeverity.INFO
    assert notices[0].severity is not NoticeSeverity.WARNING


def test_a_single_filing_period_raises_no_notice() -> None:
    assert found_more_than_expected_notices(FiledHistoryOnboardingRun(selection_rows=(_selection_row(raw=1),))) == ()


def test_the_notice_names_the_winner_and_the_superseded_count() -> None:
    (notice,) = found_more_than_expected_notices(
        FiledHistoryOnboardingRun(selection_rows=(_selection_row(raw=3),)),
    )
    assert notice.context is not None
    assert notice.context["raw_row_count"] == "3"
    assert notice.context["superseded_count"] == "2"
    assert notice.context["winning_expediente_id"] == "13020260420WXYZ9999QRST8888"
    assert notice.context["modelo"] == "130"


def test_one_notice_per_duplicated_period() -> None:
    notices = found_more_than_expected_notices(
        FiledHistoryOnboardingRun(
            selection_rows=(
                _selection_row(raw=2, period="1T"),
                _selection_row(raw=1, period="2T"),
                _selection_row(raw=4, period="3T"),
            ),
        ),
    )
    assert {notice.context["period"] for notice in notices if notice.context} == {"1T", "3T"}


def test_the_two_advisories_compose_rather_than_duplicate() -> None:
    """They answer different questions and can fire independently.

    The found-more notice says the register held more filings than were kept for a
    period; the divergence diff says a kept VALUE changed between two captures.
    Neither implies the other, so neither may be derived from the other.
    """
    run = FiledHistoryOnboardingRun(
        pairs=(_pair(modelo="130", ejercicio=2026, row_count=1),),
        selection_rows=(_selection_row(raw=2),),
    )
    found_more = found_more_than_expected_notices(run)
    not_found = expected_but_not_found_notice(run)
    assert len(found_more) == 1
    # The period produced rows, so the missing-filing warning is silent even
    # though the found-more notice fired: the two are independent.
    assert not_found is None
    assert found_more[0].code != "live.filed.pull_all.expected_but_not_found"


# ------------------------------------------------------- the denominator note


def test_the_note_differs_between_a_measured_run_and_an_unmeasurable_one() -> None:
    """The two cases must not render the same sentence.

    Asserted as a difference rather than on wording: the note is localised prose,
    so matching English text here would pass or fail on the ambient locale rather
    than on the behaviour. What matters is that a run with no taxpayer-specific
    denominator cannot produce the same statement as one that has one.
    """
    register_only = FiledHistoryOnboardingRun(pairs=(_pair(signals=_REGISTER),))
    with_profile = FiledHistoryOnboardingRun(pairs=(_pair(signals=_PROFILE),))
    assert register_only.denominator_note
    assert with_profile.denominator_note
    assert register_only.denominator_note != with_profile.denominator_note


def test_the_note_counts_profile_pairs_separately_from_register_only_pairs() -> None:
    # The counts are interpolated identifiers rather than translated words, so
    # they are the locale-independent part of the note.
    run = FiledHistoryOnboardingRun(
        pairs=(
            _pair(modelo="303", ejercicio=2025, signals=_PROFILE),
            _pair(modelo="100", ejercicio=2024, signals=_REGISTER),
            _pair(modelo="130", ejercicio=2024, signals=_REGISTER),
        ),
    )
    note = run.denominator_note
    assert "1" in note
    assert "2" in note


def test_the_run_carries_no_completeness_ratio_field() -> None:
    names = " ".join(FiledHistoryOnboardingRun.model_fields).casefold()
    for token in ("percent", "fraction", "ratio", "pct", "completeness"):
        assert token not in names
    for name, field in FiledHistoryOnboardingRun.model_fields.items():
        assert field.annotation is not float, f"{name} is a float; a ratio has no honest denominator here"


def test_the_run_defaults_to_an_inconclusive_scoping_reading() -> None:
    # Never a resolved answer, and never a default that implies one.
    assert FiledHistoryOnboardingRun().scoping_signal is RegisterScopingSignal.INCONCLUSIVE


def test_a_pair_nominated_by_nothing_is_refused() -> None:
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="signals"):
        FiledHistoryPairOutcome(modelo="303", ejercicio=2025, signals=())


# ------------------------- the run model's justificante unreached-evidence slot


def test_the_run_model_holds_one_advisory_per_unreached_reason_without_merging() -> None:
    """The taxonomy has members, and the run model keeps one advisory per member.

    Both halves are about the model, not about any operator. The reasons exist
    because a capture could extract casillas and report zero justificante evidence
    with no visible cause -- one log line and a ``None`` for every different
    failure -- so the advisory slot is only worth carrying if it can hold the
    distinction rather than collapsing it. That is what is asserted: the enum is
    non-empty, and a run constructed with one advisory per member reads back the
    full set with nothing merged.

    It proves NOTHING about anything reaching an operator: the advisories are
    written onto the model and read back off the same object, so deleting the
    transport that forwards them would leave this green. The forwarding itself is
    driven at the transport boundary by the CLI relay tests.

    The expected set is derived from the enum rather than hand-listed: a
    hand-listed tuple is exactly how a newly added reason goes uncarried and
    unnoticed.
    """
    from ....core.json_contract import Notice, NoticeSeverity
    from ..filed_observation_persistence import (
        FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
        FiledJustificanteUnreachedReason,
    )

    reasons = tuple(FiledJustificanteUnreachedReason)
    assert len(reasons) >= 6, "the reason taxonomy shrank; this test would under-cover the advisory slot"

    run = FiledHistoryOnboardingRun(
        pairs=(_pair(row_count=1),),
        evidence_notices=tuple(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
                message=f"artefact produced no evidence ({reason.value})",
                context={"reason": reason.value, "modelo": "130"},
            )
            for reason in reasons
        ),
    )

    carried = {
        notice.context["reason"]
        for notice in run.evidence_notices
        if notice.context and notice.code == FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE
    }
    assert carried == {reason.value for reason in reasons}
    # One advisory per reason: the model merged nothing on the way in.
    assert len(run.evidence_notices) == len(reasons)


def test_the_run_advisory_builder_uses_a_different_code_from_the_evidence_advisories() -> None:
    """The run's own advisory and the per-artefact ones share a channel, not an identity.

    The load-bearing half runs the real ``expected_but_not_found_notice`` builder;
    the evidence advisory it is compared against is written onto the model by this
    test, so the comparison is about the two CODES being distinguishable and not
    about either advisory travelling anywhere.
    """
    from ....core.json_contract import Notice, NoticeSeverity
    from ..filed_observation_persistence import FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE

    run = FiledHistoryOnboardingRun(
        pairs=(_pair(signals=_PROFILE, row_count=0),),
        evidence_notices=(
            Notice(
                severity=NoticeSeverity.WARNING,
                code=FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE,
                message="artefact produced no evidence (csv_mismatch)",
                context={"reason": "csv_mismatch"},
            ),
        ),
    )
    missing = expected_but_not_found_notice(run)
    assert missing is not None
    # Different codes, so a consumer can tell an unfiled period from an unusable
    # receipt -- two facts a single "evidence missing" notice would have merged.
    assert missing.code != FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE
    assert run.evidence_notices[0].code == FILED_JUSTIFICANTE_UNREACHED_NOTICE_CODE


def test_a_run_given_no_evidence_advisories_defaults_to_carrying_none() -> None:
    # The empty default matters: a truthy default would make every clean run look
    # like it had an unreached artefact. It says nothing about what a transport does.
    assert FiledHistoryOnboardingRun(pairs=(_pair(row_count=1),)).evidence_notices == ()
