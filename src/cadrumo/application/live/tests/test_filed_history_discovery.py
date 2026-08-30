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
import re
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import ValidationError

from ....adapters.outbound.aeat.sede.schema import FiledDeclarationAvailability, FiledDeclarationAvailabilityReport
from ....core import FiledHistoryDiscoverySignal, Period, RegisterScopingSignal
from ....core.casilla_id import validated_casilla_id
from ....domain.deadlines.models import TaxpayerProfile
from ..filed_data_capture import (
    ExpectedFiledDeclarationGrid,
    FiledHistoryDiscoveryPair,
    FiledHistoryDiscoveryReport,
    casillas_a_recapture_would_change,
    classify_register_scoping_signal,
    expected_filed_declaration_grid,
    filed_history_discovery_report,
    filed_period_selection_rows,
    recapture_divergence_notices,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_application]

_TODAY = date(2026, 8, 7)
_ACTIVITY_START = date(2024, 3, 1)


def _confidently_excluded(profile: TaxpayerProfile) -> set[str]:
    """Return the modelos the profile positively answers "no" for."""
    from ....application.overview.coverage import build_obligation_coverage

    return set(build_obligation_coverage(profile, (), today=_TODAY).confidently_excluded)


def _autonomo(
    *,
    activity_start_date: date | None = _ACTIVITY_START,
    activity_end_date: date | None = None,
) -> TaxpayerProfile:
    """A natural person with economic activity, IVA general, activity from 2024.

    The two activity dates are the only axes these tests vary, so they are named
    parameters rather than a ``**overrides`` bag: the bag erased every field to
    ``object`` on the way into the model, which is what a supplied date being
    silently the wrong type would have hidden.
    """
    from ....domain.deadlines.models import EntityType, IVARegime, IrpfEstimationRegime, IrpfIncomeCategory

    return TaxpayerProfile(
        tax_id="X1234567L",
        entity_type=EntityType.NATURAL_PERSON,
        irpf_income_categories=frozenset({IrpfIncomeCategory.ACTIVIDAD_ECONOMICA}),
        irpf_estimation_regime=IrpfEstimationRegime.DIRECTA_NORMAL,
        iva_regime=IVARegime.GENERAL,
        activity_start_date=activity_start_date,
        activity_end_date=activity_end_date,
    )


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
    from ...modelo.registry_discovery import registry_modelo_codes

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
    from ....domain.deadlines.models import EntityType, IVARegime

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


# ------------------------------------------- raw register rows versus selection


def _declaration_row(*, modelo: str, year: int, period: str, expediente_id: str, presented_at: datetime):
    from ....adapters.outbound.aeat.sede.declarations_schema import Declaracion

    return Declaracion(
        modelo=modelo,
        ejercicio=year,
        period=Period.from_year_and_code(year, period),
        expediente_id=expediente_id,
        estado="ALTA",
        tipo_solicitud=None,
        observaciones=None,
        presented_at=presented_at,
        justificante_link_text="Ver",
        archive_link_text="Ver",
        declaration_copy_link_text=None,
    )


def _filed_130_observation_for_tests():
    import hashlib

    from pydantic import AnyHttpUrl

    from ....adapters.outbound.aeat.sede.schema import FiledDeclaracionArtefact, FiledDeclaracionObservation, ObservedCasillaValue
    from ....core import CasillaValueKind
    from ....core.config import Settings

    body = b"130-2026-1T-submitted-file"
    external = Settings.external_constants().aeat
    url = f"{external.domains.www6}{external.sede_paths.declarations_listing}"
    presented_at = datetime(2026, 4, 20, 10, 0, tzinfo=UTC)
    return FiledDeclaracionObservation(
        modelo="130",
        ejercicio=2026,
        period=Period.from_year_and_code(2026, "1T"),
        expediente_id="13020260420WXYZ9999QRST8888",
        status="ALTA",
        presented_at=presented_at,
        authenticated_identity="12345678Z",
        artefacts=(
            FiledDeclaracionArtefact(
                kind="submitted_file",
                source_url=AnyHttpUrl(url),
                content_type="application/octet-stream",
                byte_count=len(body),
                sha256=hashlib.sha256(body).hexdigest(),
                captured_at=presented_at,
            ),
        ),
        casillas=(
            ObservedCasillaValue(
                casilla_id=validated_casilla_id("03"),
                value="1500.00",
                value_kind=CasillaValueKind.NUMERIC,
                source_artefact_kind="submitted_file",
                source_locator="submitted-file:03",
                confidence=1.0,
            ),
        ),
        extraction_coverage={"submitted_file": 1.0},
    )


def test_a_period_with_two_register_rows_reports_two_raw_and_one_selected() -> None:
    """The collapse the sweep performs becomes visible instead of silent.

    Two filings for one period -- an original and its amendment -- collapse to one
    persisted observation. That is correct, but unreported it means an operator
    seeing one observation cannot tell whether AEAT held one filing or four.
    """
    rows = filed_period_selection_rows(
        {
            ("130", 2026): (
                _declaration_row(
                    modelo="130",
                    year=2026,
                    period="1T",
                    expediente_id="13020260410ABCD1234EFGH5678",
                    presented_at=datetime(2026, 4, 10, tzinfo=UTC),
                ),
                _declaration_row(
                    modelo="130",
                    year=2026,
                    period="1T",
                    expediente_id="13020260420WXYZ9999QRST8888",
                    presented_at=datetime(2026, 4, 20, tzinfo=UTC),
                ),
            ),
        },
        (_filed_130_observation_for_tests(),),
    )
    (row,) = rows
    assert row.modelo == "130"
    assert row.ejercicio == 2026
    assert row.period == "1T"
    assert row.raw_row_count == 2
    assert row.selected_count == 1
    assert row.superseded_count == 1
    assert row.held_more_than_one_filing is True


def test_a_single_filing_period_reports_no_supersession() -> None:
    rows = filed_period_selection_rows(
        {
            ("130", 2026): (
                _declaration_row(
                    modelo="130",
                    year=2026,
                    period="1T",
                    expediente_id="13020260420WXYZ9999QRST8888",
                    presented_at=datetime(2026, 4, 20, tzinfo=UTC),
                ),
            ),
        },
        (_filed_130_observation_for_tests(),),
    )
    (row,) = rows
    assert row.raw_row_count == 1
    assert row.selected_count == 1
    assert row.superseded_count == 0
    assert row.held_more_than_one_filing is False


def test_the_breakdown_keys_on_period_not_on_the_query_pair() -> None:
    """One query pair returns several periods, each with its own duplicate count.

    Keying on the pair would sum a duplicated 1T together with a clean 2T and
    report the pair as duplicated, hiding which period actually held two filings.
    """
    rows = filed_period_selection_rows(
        {
            ("130", 2026): (
                _declaration_row(
                    modelo="130",
                    year=2026,
                    period="1T",
                    expediente_id="13020260410ABCD1234EFGH5678",
                    presented_at=datetime(2026, 4, 10, tzinfo=UTC),
                ),
                _declaration_row(
                    modelo="130",
                    year=2026,
                    period="1T",
                    expediente_id="13020260420WXYZ9999QRST8888",
                    presented_at=datetime(2026, 4, 20, tzinfo=UTC),
                ),
                _declaration_row(
                    modelo="130",
                    year=2026,
                    period="2T",
                    expediente_id="13020260710MNOP5555IJKL4444",
                    presented_at=datetime(2026, 7, 10, tzinfo=UTC),
                ),
            ),
        },
        (_filed_130_observation_for_tests(),),
    )
    by_period = {row.period: row for row in rows}
    assert by_period["1T"].raw_row_count == 2
    assert by_period["1T"].held_more_than_one_filing is True
    assert by_period["1T"].superseded_count == 1
    assert by_period["2T"].raw_row_count == 1
    assert by_period["2T"].held_more_than_one_filing is False
    # 2T returned one row and captured none, which is NOT supersession: with no
    # winner nothing was displaced. It is an unaccounted row, reported as such so
    # the operator is never told a filing was superseded by one that never existed.
    assert by_period["2T"].superseded_count == 0
    assert by_period["2T"].rows_not_accounted_for == 1


# --------------------------------------------------- the re-capture divergence


def _stored_130_registry_observation(*, casilla_03: str):
    from ....core.casilla_id import validated_casilla_id
    from ....domain.calculations.registry.bindings import RegistryModeloObservation
    from ....tests.registry_observations import registry_grounded_observations

    return RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=2026,
            period="1T",
            casilla_values={validated_casilla_id("03"): Decimal(casilla_03)},
        ),
    )


def test_a_changed_casilla_value_is_reported_as_a_divergence() -> None:
    changed = casillas_a_recapture_would_change(
        _filed_130_observation_for_tests(),
        _stored_130_registry_observation(casilla_03="1200.00"),
    )
    assert changed == ("03",)


def test_an_unchanged_casilla_value_is_not_a_divergence() -> None:
    changed = casillas_a_recapture_would_change(
        _filed_130_observation_for_tests(),
        _stored_130_registry_observation(casilla_03="1500.00"),
    )
    assert changed == ()


def test_a_casilla_the_stored_revision_never_held_is_not_a_divergence() -> None:
    """A wider extraction is not a changed value.

    Comparing only the intersection is what stops the advisory firing on every
    extraction improvement -- a casilla newly READ is not a casilla AMENDED, and
    reporting it as one would train the operator to ignore the alert.
    """
    from ....core.casilla_id import validated_casilla_id
    from ....domain.calculations.registry.bindings import RegistryModeloObservation
    from ....tests.registry_observations import registry_grounded_observations

    stored_without_03 = RegistryModeloObservation(
        modelo="130",
        filing_year=2026,
        period="1T",
        observations=registry_grounded_observations(
            modelo="130",
            filing_year=2026,
            period="1T",
            casilla_values={validated_casilla_id("07"): Decimal("10.00")},
        ),
    )
    assert casillas_a_recapture_would_change(_filed_130_observation_for_tests(), stored_without_03) == ()


def test_a_change_within_the_registry_published_tolerance_is_absorbed() -> None:
    """A real registry-published tolerance -- not a hardcoded cent -- absorbs rounding noise.

    The fresh capture reads casilla 03 as ``1500.00``; the stored value differs
    by EXACTLY the modelo 130 2026 1T published tolerance (``0.01``), so it must
    not surface as a divergence when that tolerance is passed.
    """
    changed = casillas_a_recapture_would_change(
        _filed_130_observation_for_tests(),
        _stored_130_registry_observation(casilla_03="1499.99"),
        tolerance=Decimal("0.01"),
    )
    assert changed == ()


def test_a_change_beyond_the_registry_published_tolerance_still_fires() -> None:
    """A genuine divergence beyond the published tolerance is never silently absorbed."""
    changed = casillas_a_recapture_would_change(
        _filed_130_observation_for_tests(),
        _stored_130_registry_observation(casilla_03="1499.98"),
        tolerance=Decimal("0.01"),
    )
    assert changed == ("03",)


def test_recapture_divergence_notices_absorbs_a_within_tolerance_change_end_to_end(tmp_path: Path) -> None:
    """The real caller resolves and applies the registry tolerance, not just the pure function.

    Exercised through :func:`recapture_divergence_notices` itself -- the actual
    production entry point -- against a REAL persisted stored observation, so
    the proof is not confined to the pure comparator in isolation.
    """
    from ....domain.calculations.registry.bindings import RegistryModeloObservation
    from ....tests.registry_observations import registry_grounded_observations
    from ....tests.secure_sql import isolated_runtime_profile
    from ...calculations import CalculationObservationRepository

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="130",
                    filing_year=2026,
                    period="1T",
                    observations=registry_grounded_observations(
                        modelo="130",
                        filing_year=2026,
                        period="1T",
                        casilla_values={validated_casilla_id("03"): Decimal("1499.99")},
                    ),
                ),
                source_kind="app_filing",
            ),
        )

        notices = recapture_divergence_notices((_filed_130_observation_for_tests(),), repository=repo)

    assert notices == ()


def test_recapture_divergence_notices_fires_beyond_tolerance_end_to_end(tmp_path: Path) -> None:
    """The mutation-based counterpart: a genuine divergence still reaches the operator as a Notice."""
    from ....domain.calculations.registry.bindings import RegistryModeloObservation
    from ....tests.registry_observations import registry_grounded_observations
    from ....tests.secure_sql import isolated_runtime_profile
    from ...calculations import CalculationObservationRepository

    with isolated_runtime_profile(tmp_path=tmp_path):
        repo = CalculationObservationRepository()
        repo.save(
            repo.prepare_observation_envelope(
                RegistryModeloObservation(
                    modelo="130",
                    filing_year=2026,
                    period="1T",
                    observations=registry_grounded_observations(
                        modelo="130",
                        filing_year=2026,
                        period="1T",
                        casilla_values={validated_casilla_id("03"): Decimal("1499.98")},
                    ),
                ),
                source_kind="app_filing",
            ),
        )

        notices = recapture_divergence_notices((_filed_130_observation_for_tests(),), repository=repo)

    assert len(notices) == 1
    context = notices[0].context
    assert context is not None
    assert context["changed_casillas"] == "03"


def test_the_divergence_set_is_derived_from_the_captured_casillas_not_a_fixed_list() -> None:
    """A newly captured casilla is compared the moment it is captured.

    Pinned because the failure this function exists to prevent is a comparison
    that OMITS a casilla, and a hand-listed field set is exactly how that
    omission arrives.
    """
    import inspect

    source = inspect.getsource(casillas_a_recapture_would_change)
    assert "fresh.casillas" in source
    assert not re.search(r"[\"'](?:0\d|1\d{2})[\"']", source), "a literal casilla id appeared; the set must be derived"
