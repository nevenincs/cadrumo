"""The two discovery signals, and the asymmetry between them.

The whole point of this surface is that a zero-row outcome means different
things depending on which signal nominated the pair. So these tests do not just
check that a union contains the right pairs; they check that the union
REMEMBERS which signal contributed each one, and that the anomaly predicate
follows the profile signal and never the register one.

Everything here is a pure derivation over declared profile data and an
already-parsed option set. No live session, no fixture of AEAT's HTML, and no
authenticated probe: that is a property of the design rather than a limitation
of the tests, because the load-bearing signal is by construction computable from
data the taxpayer themselves declared.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from ....adapters.outbound.aeat.sede import (
    FiledDeclarationAvailability,
    FiledDeclarationAvailabilityReport,
)
from ....core import FiledHistoryDiscoverySignal, RegisterScopingSignal
from ....domain.deadlines import TaxpayerProfile
from .._filed_data_capture import (
    ExpectedFiledDeclarationGrid,
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryReport,
    classify_register_scoping_signal,
    expected_filed_declaration_grid,
    filed_history_discovery_report,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TODAY = date(2026, 8, 7)


def _confidently_excluded(profile: TaxpayerProfile) -> set[str]:
    """Return the modelos the profile positively answers "no" for."""
    from ....application.overview import build_obligation_coverage

    return set(build_obligation_coverage(profile, (), today=_TODAY).confidently_excluded)


def _autonomo(**overrides: object) -> TaxpayerProfile:
    """A natural person with economic activity, IVA general, activity from 2024."""
    from ....domain.deadlines import (
        EntityType,
        IrpfEstimationRegime,
        IrpfIncomeCategory,
        IVARegime,
    )

    fields: dict[str, object] = {
        "tax_id": "X1234567L",
        "entity_type": EntityType.NATURAL_PERSON,
        "irpf_income_categories": frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        "irpf_estimation_regime": IrpfEstimationRegime.DIRECTA_NORMAL,
        "iva_regime": IVARegime.GENERAL,
        "activity_start_date": date(2024, 3, 1),
    }
    fields.update(overrides)
    return TaxpayerProfile(**fields)  # type: ignore[arg-type]


# ---------------------------------------------------------------- the year axis


def test_the_year_span_runs_from_the_declared_activity_start_to_today() -> None:
    grid = expected_filed_declaration_grid(_autonomo(), today=_TODAY)
    assert grid.ejercicios == (2026, 2025, 2024)
    assert grid.activity_start_declared is True


def test_a_declared_activity_end_caps_the_span() -> None:
    # A taxpayer who ceased activity in 2025 is not expected to have filed for
    # 2026, and flagging 2026 as expected-but-not-found would be a false anomaly.
    grid = expected_filed_declaration_grid(
        _autonomo(activity_end_date=date(2025, 6, 30)),
        today=_TODAY,
    )
    assert grid.ejercicios == (2025, 2024)
    assert grid.activity_end_declared is True


def test_an_activity_end_after_today_does_not_extend_the_span_into_the_future() -> None:
    grid = expected_filed_declaration_grid(
        _autonomo(activity_end_date=date(2030, 1, 1)),
        today=_TODAY,
    )
    assert grid.ejercicios == (2026, 2025, 2024)


def test_an_activity_starting_this_year_yields_exactly_this_year() -> None:
    grid = expected_filed_declaration_grid(_autonomo(activity_start_date=date(2026, 1, 15)), today=_TODAY)
    assert grid.ejercicios == (2026,)


def test_no_declared_activity_start_says_cannot_say_rather_than_nothing_expected() -> None:
    # The distinction is load-bearing. An empty span with the flag CLEAR is
    # "the profile never declared when activity began", which a consumer must
    # surface; reading it as "nothing expected" would silently leave only the
    # signal whose informativeness is unconfirmed.
    grid = expected_filed_declaration_grid(_autonomo(activity_start_date=None), today=_TODAY)
    assert grid.ejercicios == ()
    assert grid.pairs == ()
    assert grid.activity_start_declared is False


# -------------------------------------------------------------- the modelo axis


def test_the_modelo_axis_comes_from_the_profiles_own_applicability() -> None:
    grid = expected_filed_declaration_grid(_autonomo(), today=_TODAY)
    assert grid.modelos
    # An autónomo under estimación directa with IVA general is expected to touch
    # the IRPF annual return and the IVA autoliquidación.
    assert "100" in grid.modelos
    assert "303" in grid.modelos


def test_a_modelo_the_profile_positively_excludes_is_absent() -> None:
    # A natural person is not a sociedad, so the corporate-tax return must not be
    # nominated: the profile answers "no" for it, and an expectation the profile
    # never made would produce a false expected-but-not-found finding.
    grid = expected_filed_declaration_grid(_autonomo(), today=_TODAY)
    assert "200" not in grid.modelos


def test_every_nominated_modelo_is_one_the_registry_actually_models() -> None:
    # This is the invariant behind dropping the registry-unmodeled advisories: a
    # modelo with no registry definition has no declared fact producing its
    # verdict, so nominating it would invent an expectation the taxpayer never
    # made and then report the inevitable zero rows as an anomaly.
    #
    # Asserted as a containment property rather than against
    # UNMODELED_OBLIGATIONS, which is EMPTY at present -- an intersection test
    # against it would pass vacuously and keep passing if the filter were deleted.
    from ....application.modelo import registry_modelo_codes

    grid = expected_filed_declaration_grid(_autonomo(), today=_TODAY)
    registry_codes = set(registry_modelo_codes())
    assert registry_codes
    assert set(grid.modelos) <= registry_codes


def test_an_out_of_scope_modelo_is_absent() -> None:
    from ....core import OUT_OF_SCOPE_OBLIGATIONS

    grid = expected_filed_declaration_grid(_autonomo(), today=_TODAY)
    out_of_scope = {str(code) for code in OUT_OF_SCOPE_OBLIGATIONS}
    assert out_of_scope
    assert not set(grid.modelos) & out_of_scope


def test_the_modelo_axis_differs_between_two_different_profiles() -> None:
    # The signal is worthless unless it is genuinely taxpayer-specific, so this
    # asserts the derivation actually responds to declared facts rather than
    # returning one universal list under a taxpayer-specific name.
    from ....domain.deadlines import EntityType, IVARegime

    natural = expected_filed_declaration_grid(_autonomo(), today=_TODAY)
    company = expected_filed_declaration_grid(
        TaxpayerProfile(
            tax_id="B12345674",
            entity_type=EntityType.LEGAL_ENTITY,
            irpf_income_categories=frozenset(),
            iva_regime=IVARegime.GENERAL,
            activity_start_date=date(2024, 3, 1),
        ),
        today=_TODAY,
    )
    assert set(natural.modelos) != set(company.modelos)


# ------------------------------------------------------------------- the union


def _availability(*items: tuple[str, tuple[int, ...]]) -> FiledDeclarationAvailabilityReport:
    return FiledDeclarationAvailabilityReport(
        items=tuple(FiledDeclarationAvailability(modelo=modelo, ejercicios=years) for modelo, years in items),
        discovered_at=datetime(2026, 8, 7, 10, 0, tzinfo=UTC),
    )


def _report_for(
    *,
    modelos: tuple[str, ...],
    ejercicios: tuple[int, ...],
    offered: tuple[tuple[str, tuple[int, ...]], ...],
) -> FiledHistoryDiscoveryReport:
    return filed_history_discovery_report(
        expected=ExpectedFiledDeclarationGrid(
            modelos=modelos,
            ejercicios=ejercicios,
            activity_start_declared=True,
        ),
        availability=_availability(*offered),
    )


def test_a_pair_in_both_signals_carries_both_tags() -> None:
    report = _report_for(modelos=("303",), ejercicios=(2025,), offered=(("303", (2025,)),))
    (pair,) = report.pairs
    assert pair.signals == (
        FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,
        FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,
    )


def test_a_profile_only_pair_carries_only_the_profile_tag() -> None:
    report = _report_for(modelos=("303",), ejercicios=(2025,), offered=(("100", (2025,)),))
    profile_only = next(pair for pair in report.pairs if pair.modelo == "303")
    assert profile_only.signals == (FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,)


def test_a_register_only_pair_carries_only_the_register_tag() -> None:
    report = _report_for(modelos=("303",), ejercicios=(2025,), offered=(("100", (2025,)),))
    register_only = next(pair for pair in report.pairs if pair.modelo == "100")
    assert register_only.signals == (FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,)


def test_the_register_signal_only_ever_widens_the_grid() -> None:
    expected = ExpectedFiledDeclarationGrid(
        modelos=("303",),
        ejercicios=(2025, 2024),
        activity_start_declared=True,
    )
    without = filed_history_discovery_report(expected=expected, availability=None)
    with_register = filed_history_discovery_report(
        expected=expected,
        availability=_availability(("100", (2023,))),
    )
    assert set(without.walk_pairs) <= set(with_register.walk_pairs)
    # And every profile pair keeps its standing after the union.
    assert {(pair.modelo, pair.ejercicio) for pair in with_register.profile_expected_pairs} == set(without.walk_pairs)


def test_the_register_signal_can_never_remove_a_profile_pair() -> None:
    # An option list that offers NOTHING must not shrink the walked grid, because
    # an absent option cannot be distinguished from a list that never lists it.
    report = filed_history_discovery_report(
        expected=ExpectedFiledDeclarationGrid(
            modelos=("303",),
            ejercicios=(2025,),
            activity_start_declared=True,
        ),
        availability=_availability(),
    )
    assert report.walk_pairs == (("303", 2025),)
    assert report.pairs[0].expected_by_profile is True


def test_walk_order_reaches_recent_filings_first() -> None:
    report = _report_for(
        modelos=("100", "303"),
        ejercicios=(2024, 2026, 2025),
        offered=(),
    )
    assert report.walk_pairs == (
        ("100", 2026),
        ("100", 2025),
        ("100", 2024),
        ("303", 2026),
        ("303", 2025),
        ("303", 2024),
    )


# --------------------------------------------------------------- the asymmetry


def test_zero_rows_is_an_anomaly_only_for_a_profile_nominated_pair() -> None:
    report = _report_for(modelos=("303",), ejercicios=(2025,), offered=(("100", (2025,)),))
    by_modelo = {pair.modelo: pair for pair in report.pairs}
    assert by_modelo["303"].zero_rows_is_an_anomaly is True
    assert by_modelo["100"].zero_rows_is_an_anomaly is False


def test_a_pair_in_both_signals_is_still_an_anomaly_when_empty() -> None:
    # Being ALSO offered by the register must not downgrade a profile
    # expectation; the union is additive in coverage, not in standing.
    report = _report_for(modelos=("303",), ejercicios=(2025,), offered=(("303", (2025,)),))
    assert report.pairs[0].zero_rows_is_an_anomaly is True


def test_the_two_pair_partitions_are_total_and_disjoint() -> None:
    report = _report_for(
        modelos=("303",),
        ejercicios=(2025,),
        offered=(("100", (2025, 2024)), ("303", (2025,))),
    )
    expected_pairs = set(report.profile_expected_pairs)
    register_only = set(report.register_options_only_pairs)
    assert not expected_pairs & register_only
    assert expected_pairs | register_only == set(report.pairs)


def test_a_register_only_report_carries_no_taxpayer_specific_denominator() -> None:
    report = filed_history_discovery_report(
        expected=ExpectedFiledDeclarationGrid(),
        availability=_availability(("303", (2025,))),
    )
    assert report.walk_pairs == (("303", 2025),)
    assert report.carries_a_taxpayer_specific_denominator is False
    assert report.profile_year_span_determined is False
    assert report.register_options_read is True


def test_a_profile_report_carries_a_taxpayer_specific_denominator() -> None:
    report = filed_history_discovery_report(
        expected=ExpectedFiledDeclarationGrid(
            modelos=("303",),
            ejercicios=(2025,),
            activity_start_declared=True,
        ),
        availability=None,
    )
    assert report.carries_a_taxpayer_specific_denominator is True
    assert report.profile_year_span_determined is True
    assert report.register_options_read is False


# ----------------------------------------------------------------- model guards


def test_a_pair_nominated_by_nothing_is_refused() -> None:
    with pytest.raises(ValidationError, match="signals"):
        FiledHistoryDiscoveryPair(modelo="303", ejercicio=2025, signals=())


def test_signal_order_is_canonicalised_so_equal_nominations_compare_equal() -> None:
    forward = FiledHistoryDiscoveryPair(
        modelo="303",
        ejercicio=2025,
        signals=(
            FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,
            FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,
        ),
    )
    reversed_with_duplicate = FiledHistoryDiscoveryPair(
        modelo="303",
        ejercicio=2025,
        signals=(
            FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,
            FiledHistoryDiscoverySignal.PROFILE_APPLICABILITY,
            FiledHistoryDiscoverySignal.AEAT_REGISTER_OPTIONS,
        ),
    )
    assert forward == reversed_with_duplicate


def test_the_report_survives_a_strict_json_roundtrip() -> None:
    saved = _report_for(
        modelos=("303",),
        ejercicios=(2025, 2024),
        offered=(("100", (2023,)),),
    )
    loaded = FiledHistoryDiscoveryReport.model_validate_json(saved.model_dump_json())
    assert loaded == saved


def test_the_report_refuses_a_payload_whose_pair_lost_its_signals() -> None:
    corrupted = json.loads(_report_for(modelos=("303",), ejercicios=(2025,), offered=()).model_dump_json())
    del corrupted["pairs"][0]["signals"]
    with pytest.raises(ValidationError, match="signals"):
        FiledHistoryDiscoveryReport.model_validate_json(json.dumps(corrupted))


def test_the_report_refuses_an_unknown_signal_token() -> None:
    corrupted = json.loads(_report_for(modelos=("303",), ejercicios=(2025,), offered=()).model_dump_json())
    corrupted["pairs"][0]["signals"] = ["operator_guess"]
    with pytest.raises(ValidationError, match="signals"):
        FiledHistoryDiscoveryReport.model_validate_json(json.dumps(corrupted))


# --------------------------------------------------- the offline scoping reading


def test_an_offered_modelo_the_profile_excludes_reads_as_likely_universal() -> None:
    """The positive observation: the register offers something this filer cannot file.

    A natural person's profile positively answers "no" for the corporate-tax
    return, so a list scoped to that NIF would not offer it. Offering it anyway is
    what a catalogue rendered regardless of taxpayer looks like -- and this is the
    reading that matters, because it is the one under which measuring coverage
    against the offered set alone would be meaningless.
    """
    profile = _autonomo()
    excluded = _confidently_excluded(profile)
    assert excluded, "the profile excludes nothing, so this fixture cannot show an excluded modelo being offered"

    reading = classify_register_scoping_signal(
        profile,
        _availability((next(iter(sorted(excluded))), (2025,))),
        today=_TODAY,
    )
    assert reading is RegisterScopingSignal.LIKELY_UNIVERSAL


def test_an_offered_set_avoiding_every_excluded_modelo_reads_as_likely_nif_scoped() -> None:
    """Consistent with a NIF-scoped list -- and only consistent with it.

    The absence of an excluded modelo is ALSO what a universal catalogue produces
    for a taxpayer whose profile happens to exclude nothing the register lists,
    which is why the member stays a hedge and why this test asserts the hedge
    rather than a resolved answer.
    """
    profile = _autonomo()
    excluded = _confidently_excluded(profile)
    offered = "303"
    assert offered not in excluded, "the fixture modelo is excluded, so this arm is testing the other branch"

    reading = classify_register_scoping_signal(profile, _availability((offered, (2025,))), today=_TODAY)
    assert reading is RegisterScopingSignal.LIKELY_NIF_SCOPED


def test_an_empty_offered_set_reads_as_inconclusive() -> None:
    """No offered modelos means the comparison discriminates nothing.

    Reported as inconclusive rather than as a weak version of either reading: the
    available evidence says nothing either way, and collapsing that into
    "probably scoped" would manufacture confidence from an absent measurement.
    """
    reading = classify_register_scoping_signal(_autonomo(), _availability(), today=_TODAY)
    assert reading is RegisterScopingSignal.INCONCLUSIVE


def test_no_reading_can_express_a_resolved_answer() -> None:
    """The enum cannot say "universal" or "nif_scoped" outright, by construction.

    The plan row requires that no test assert a resolved boolean. This goes
    further and pins that a resolved value is not even representable, so a future
    consumer cannot store a heuristic reading and later cite it as though a live
    probe had confirmed it.
    """
    values = {signal.value for signal in RegisterScopingSignal}
    assert values == {"likely_universal", "likely_nif_scoped", "inconclusive"}
    assert "universal" not in values
    assert "nif_scoped" not in values
    assert all(signal.value.startswith(("likely_", "inconclusive")) for signal in RegisterScopingSignal)


def test_the_reading_does_not_change_the_walked_grid() -> None:
    """The classification is advisory: it can neither widen nor narrow the walk.

    Asserted because an advisory that quietly gated coverage would be the worst of
    both -- an unconfirmed signal deciding what gets queried.
    """
    profile = _autonomo()
    excluded = next(iter(sorted(_confidently_excluded(profile))))
    universal_looking = _availability((excluded, (2025,)))
    scoped_looking = _availability(("303", (2025,)))

    expected = ExpectedFiledDeclarationGrid(
        modelos=("303",),
        ejercicios=(2025,),
        activity_start_declared=True,
    )
    assert classify_register_scoping_signal(profile, universal_looking, today=_TODAY) is (
        RegisterScopingSignal.LIKELY_UNIVERSAL
    )
    assert classify_register_scoping_signal(profile, scoped_looking, today=_TODAY) is (
        RegisterScopingSignal.LIKELY_NIF_SCOPED
    )
    # Both offered sets are unioned in identically regardless of the reading.
    for availability in (universal_looking, scoped_looking):
        report = filed_history_discovery_report(expected=expected, availability=availability)
        assert set(expected.pairs) <= set(report.walk_pairs)
        assert set(availability.offered_pairs) <= set(report.walk_pairs)
