"""The overview nudge for a profile with no AEAT-confirmed filing evidence.

The predicate is official-source membership, not observation emptiness, and that
choice is what this module tests. A profile whose only observations are
locally filed or operator-entered has exactly the same gap as one with no
observations at all — it holds nothing AEAT ever confirmed — so testing for an
empty list would leave precisely that taxpayer unprompted.
"""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from ....core.json_contract import NoticeSeverity
from .. import NO_AEAT_HISTORY_NOTICE_CODE, no_aeat_history_notice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


@dataclass(frozen=True)
class _Observation:
    """The one attribute the predicate reads, in the shape the repository returns."""

    source_kind: str


def test_the_notice_fires_when_no_observation_exists_at_all() -> None:
    notice = no_aeat_history_notice(())
    assert notice is not None
    assert notice.severity is NoticeSeverity.INFO
    assert notice.code == NO_AEAT_HISTORY_NOTICE_CODE
    assert notice.action is None


def test_the_notice_is_absent_once_one_official_observation_exists() -> None:
    assert no_aeat_history_notice((_Observation(source_kind="aeat_sede_justificante"),)) is None


def test_every_official_source_kind_silences_the_notice() -> None:
    from ...calculations import ObservationSourceKind

    official = [kind for kind in ObservationSourceKind if kind.is_official_aeat]
    assert official, "no official kinds; this test would pass vacuously"
    for kind in official:
        assert no_aeat_history_notice((_Observation(source_kind=kind.value),)) is None, kind


def test_a_profile_holding_only_non_official_observations_is_still_prompted() -> None:
    """The load-bearing case, and the one an emptiness check would miss.

    A locally filed or operator-entered observation is not evidence AEAT confirmed
    anything, so the taxpayer still has the gap this notice exists to close.
    """
    from ...calculations import ObservationSourceKind

    non_official = [kind for kind in ObservationSourceKind if not kind.is_official_aeat]
    assert non_official, "no non-official kinds; this test would pass vacuously"
    for kind in non_official:
        notice = no_aeat_history_notice((_Observation(source_kind=kind.value),))
        assert notice is not None, kind
        assert notice.code == NO_AEAT_HISTORY_NOTICE_CODE


def test_one_official_observation_among_many_non_official_ones_silences_it() -> None:
    from ...calculations import ObservationSourceKind

    observations = (
        _Observation(source_kind=ObservationSourceKind.APP_FILING.value),
        _Observation(source_kind=ObservationSourceKind.OPERATOR_MANUAL.value),
        _Observation(source_kind=ObservationSourceKind.AEAT_CSV_REGISTER.value),
    )
    assert no_aeat_history_notice(observations) is None


def test_an_unrecognised_source_kind_does_not_silence_the_notice() -> None:
    # Fails closed: an unknown token is not an official AEAT source, so the
    # operator still gets the nudge rather than being silently told they are done.
    assert no_aeat_history_notice((_Observation(source_kind="something_new"),)) is not None


def test_the_notice_reports_how_many_observations_it_looked_at() -> None:
    notice = no_aeat_history_notice((_Observation(source_kind="app_filing"),) * 3)
    assert notice is not None
    assert notice.context is not None
    assert notice.context["observation_count"] == "3"


def test_the_message_resolves_to_real_copy_rather_than_its_locale_key() -> None:
    notice = no_aeat_history_notice(())
    assert notice is not None
    assert notice.message
    assert "overview.no_aeat_history" not in notice.message
