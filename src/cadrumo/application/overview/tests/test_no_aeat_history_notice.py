"""The overview nudge for a profile with no AEAT-confirmed filing evidence.

The predicate is official-source membership, not observation emptiness, and that
choice is what this module tests. A profile whose only observations are
locally filed or operator-entered has exactly the same gap as one with no
observations at all — it holds nothing AEAT ever confirmed — so testing for an
empty list would leave precisely that taxpayer unprompted.
"""

from __future__ import annotations

import pytest

from ....core.json_contract import NoticeSeverity, ResolvedNoticeAction
from ....domain.calculations.registry.applicability_routes import TaxRoute
from ...calculations.observations_repository import ObservationSourceKind
from ..calendar_evidence import NO_AEAT_HISTORY_NOTICE_CODE, no_aeat_history_notice

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]


def test_the_notice_fires_when_no_observation_exists_at_all() -> None:
    notice = no_aeat_history_notice(())
    assert notice is not None
    assert notice.severity is NoticeSeverity.INFO
    assert notice.code == NO_AEAT_HISTORY_NOTICE_CODE
    assert isinstance(notice.action, ResolvedNoticeAction)
    assert notice.action.action.action_id == "operator.live.filed.pull_all"
    assert notice.action.action.target_command_key == "app.live.filed.pull_all"


def test_the_notice_is_absent_once_one_official_observation_exists() -> None:
    assert no_aeat_history_notice((ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,)) is None


def test_every_official_source_kind_silences_the_notice() -> None:
    official = [kind for kind in ObservationSourceKind if kind.is_official_aeat]
    assert official, "no official kinds; this test would pass vacuously"
    for kind in official:
        assert no_aeat_history_notice((kind,)) is None, kind


def test_a_profile_holding_only_non_official_observations_is_still_prompted() -> None:
    """The load-bearing case, and the one an emptiness check would miss.

    A locally filed or operator-entered observation is not evidence AEAT confirmed
    anything, so the taxpayer still has the gap this notice exists to close.
    """
    non_official = [kind for kind in ObservationSourceKind if not kind.is_official_aeat]
    assert non_official, "no non-official kinds; this test would pass vacuously"
    for kind in non_official:
        notice = no_aeat_history_notice((kind,))
        assert notice is not None, kind
        assert notice.code == NO_AEAT_HISTORY_NOTICE_CODE


def test_one_official_observation_among_many_non_official_ones_silences_it() -> None:
    source_kinds = (
        ObservationSourceKind.APP_FILING,
        ObservationSourceKind.OPERATOR_MANUAL,
        ObservationSourceKind.AEAT_CSV_REGISTER,
    )
    assert no_aeat_history_notice(source_kinds) is None


def test_a_capture_provenance_token_cannot_be_read_as_evidence_authority() -> None:
    """The axis this signature exists to keep out, refused where it enters.

    ``aggregate_pull`` is what the aggregation observation envelopes record in
    their own identically-spelled ``source_kind`` field. It is capture
    provenance, not evidence authority, and the previous duck-typed signature
    would have accepted it silently and graded it non-official by accident. The
    enum refuses it as a value that has no meaning on this axis at all.
    """
    with pytest.raises(ValueError):
        ObservationSourceKind("aggregate_pull")


def test_the_notice_reports_how_many_observations_it_looked_at() -> None:
    notice = no_aeat_history_notice((ObservationSourceKind.APP_FILING,) * 3)
    assert notice is not None
    assert notice.context is not None
    assert notice.context["observation_count"] == "3"


def test_the_message_resolves_to_real_copy_rather_than_its_locale_key() -> None:
    notice = no_aeat_history_notice(())
    assert notice is not None
    assert notice.message
    assert "overview.no_aeat_history" not in notice.message


def test_every_other_route_still_recommends_the_whole_history_sweep() -> None:
    """The Sociedades carve-out is narrow: every other route keeps today's suggestion."""
    for route in TaxRoute:
        if route is TaxRoute.IMPUESTO_SOCIEDADES:
            continue
        notice = no_aeat_history_notice((), tax_route=route)
        assert notice is not None, route
        assert isinstance(notice.action, ResolvedNoticeAction), route
        assert notice.action.action.action_id == "operator.live.filed.pull_all", route


def test_a_sociedades_filer_carries_no_action_the_sweep_cannot_fulfil() -> None:
    """The whole-history sweep structurally cannot fetch Modelo 200/202.

    The bulk filed-data capture planner diverts a Sociedades filer's own
    direct-tax modelos into typed unsupported rows, so recommending the sweep
    verb here would recommend a verb that can never fetch what the notice is
    about. This route carries no action at all rather than a misleading one.
    """
    notice = no_aeat_history_notice((), tax_route=TaxRoute.IMPUESTO_SOCIEDADES)
    assert notice is not None
    assert notice.severity is NoticeSeverity.INFO
    assert notice.code == NO_AEAT_HISTORY_NOTICE_CODE
    assert notice.action is None


def test_a_sociedades_filer_still_silences_on_an_official_observation() -> None:
    """The tax-route carve-out narrows the SUGGESTION, never the PREDICATE."""
    assert (
        no_aeat_history_notice(
            (ObservationSourceKind.AEAT_SEDE_JUSTIFICANTE,),
            tax_route=TaxRoute.IMPUESTO_SOCIEDADES,
        )
        is None
    )


def test_the_sociedades_message_resolves_to_real_copy_distinct_from_the_default() -> None:
    """The Sociedades message is its OWN real, translated copy, not the generic one echoed."""
    generic = no_aeat_history_notice(())
    sociedades = no_aeat_history_notice((), tax_route=TaxRoute.IMPUESTO_SOCIEDADES)
    assert generic is not None
    assert sociedades is not None
    assert sociedades.message
    assert "overview.no_aeat_history_sociedades" not in sociedades.message
    assert sociedades.message != generic.message
