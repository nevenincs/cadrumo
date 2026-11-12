"""Modelo 190 registry behaviour for the declarante totals, deadlines and live reads."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

import pytest

from cadrumo.core.casilla_id import CasillaId, validated_casilla_id
from cadrumo.core.period import Period
from cadrumo.core.resources.bundled_data import bundled_path
from cadrumo.domain.calculations.registry.authority import bundled_indexed_authority
from cadrumo.domain.calculations.registry.bindings import resolve_available_bound_inputs_by_casilla_id
from cadrumo.domain.calculations.registry.formula_runtime import calculate_registry_snapshot
from cadrumo.domain.calculations.registry.relations import (
    relation_prefill_bindings_for_period,
)
from cadrumo.domain.calculations.registry.retencion_clave_catalogue import resolve_retencion_clave
from cadrumo.domain.calculations.registry.tests.authored_editions import filing_year_envelope, newest_authored_editions
from cadrumo.domain.calculations.registry.tests.snapshot_support import build_snapshot
from cadrumo.domain.calculations.registry.withholding_bindings import (
    WithholdingObservation,
    resolve_withholding_binding_values,
)
from cadrumo.domain.deadlines.errors import DeadlineValidationError
from cadrumo.domain.deadlines.festivos import shift_deadline
from cadrumo.tests.aeat_literal_fixtures import aeat_host
from dev.registry.compiler.authority import compiled_bundled_authority

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]

_WWW6_HOST = aeat_host("www6")
_DECL_TOTAL_PERCEPCIONES_CASILLA: CasillaId = validated_casilla_id(
    "decl.total-percepciones",
    surface="_DECL_TOTAL_PERCEPCIONES_CASILLA",
)
_DECL_PERCEPCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.percepciones-total",
    surface="_DECL_PERCEPCIONES_TOTAL_CASILLA",
)
_DECL_RETENCIONES_TOTAL_CASILLA: CasillaId = validated_casilla_id(
    "decl.retenciones-total",
    surface="_DECL_RETENCIONES_TOTAL_CASILLA",
)


def test_modelo_190_guidance_and_layout_sources_are_separated() -> None:
    authority = compiled_bundled_authority()
    modelo, catalogues = authority.modelo("190"), authority.catalogues
    instructions = catalogues.sources["aeat-modelo-190-instructions-2025"]

    assert "aeat-modelo-190-instructions-2025" in modelo.source_refs
    assert instructions.evidence_tier == "official_source_guidance"
    assert instructions.authority == "aeat"
    assert instructions.kind == "manual_pdf"
    assert (bundled_path() / instructions.corpus_path).is_file()
    assert catalogues.sources["aeat-dr-190-2025"].evidence_tier == "layout_authority"
    assert catalogues.sources["boe-modelo-190-2025-form"].evidence_tier == "layout_authority"
    assert catalogues.sources["boe-modelo-190-2025-amendment"].evidence_tier == "layout_authority"
    # Every revision, rather than one named id. The id pinned here stopped
    # existing when modelo 190's span was split into "2024" and
    # "2025-y-siguientes", and the lookup raised before reaching any assertion --
    # so the separation this test exists to prove went unchecked in BOTH.
    checked = 0
    for revision in modelo.revisions.values():
        for formula in revision.formulas:
            for citation in formula.source_citations:
                assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
                checked += 1
        for binding in revision.bindings:
            for citation in binding.source_citations:
                assert catalogues.sources[citation.source_ref].evidence_tier == "official_source_guidance"
                checked += 1
    assert checked, "no formula or binding citation was checked, so this proves nothing"


def test_modelo_190_validates_and_gates_workflow_surfaces_through_snapshot() -> None:
    authority = compiled_bundled_authority()
    modelo, catalogues = authority.modelo("190"), authority.catalogues

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=filing_year_envelope().horizon,
        period="0A",
    )

    assert snapshot.revision.orden_aplicabilidad == (
        "orden-eha-3127-2009:art-1",
        "orden-hac-1431-2025:art-2",
    )
    construct = snapshot.revision.constructs[0]
    linked_surfaces = {
        link.surface for link in snapshot.revision.application_links if link.id in construct.application_links
    }
    # "verification" is deliberately absent. It is NOT a member of
    # ApplicationLink.surface -- the Literal admits calculation, filing, review,
    # approval, reconciliation, export, deadline, portal, extractor, workflow,
    # communication and payer_delivery -- so no registry data can declare it,
    # and none does: zero across every bundled modelo. Asserting it here was not
    # a data gap waiting to be filled but an expectation the schema forbids, and
    # it could never have passed. If a verification surface is wanted, that is a
    # schema decision with its own grounding, not something this test can imply.
    assert {
        "calculation",
        "filing",
        "deadline",
        "review",
        "approval",
        "reconciliation",
        "extractor",
        "portal",
        "workflow",
    } <= linked_surfaces


def _assert_190_deadline_construct_and_sources(revision, catalogues, window_id: str, form_source: str) -> None:
    construct = revision.constructs[0]
    schedule = next(item for item in revision.filing_schedules if item.id == "modelo-190-anual")
    deadline_link = next(item for item in revision.application_links if item.id == "modelo-190-deadline")

    assert deadline_link.surface == "deadline"
    assert deadline_link.consumer == "cadrumo.domain.deadlines"
    assert deadline_link.requires_snapshot is True
    assert catalogues.legal["rd-439-2007:art-108"].evidence_tier == "legal_authority"
    assert catalogues.legal["orden-eha-3127-2009:art-5"].evidence_tier == "legal_authority"
    assert catalogues.sources["aeat-modelo-190-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources[form_source].evidence_tier == "layout_authority"

    assert construct.deadline_windows == (window_id,)
    assert construct.filing_schedules == ("modelo-190-anual",)
    assert schedule.period_kind == "annual"
    assert schedule.periods == ("0A",)
    assert schedule.legal_refs == ("rd-439-2007:art-108", "orden-eha-3127-2009:art-1")
    assert schedule.source_refs == ("aeat-modelo-190-procedure", form_source)


def _assert_190_window_dates_and_grounding(
    window,
    expected: tuple[int, str, date, date],
    expected_legal_refs: tuple[str, ...],
    form_source: str,
) -> None:
    expected_filing_year, expected_period, opens_on, closes_on = expected
    assert window.filing_year == expected_filing_year
    assert str(window.period) == expected_period
    assert window.period_kind == "annual"
    assert window.opens_on == opens_on
    assert window.closes_on == closes_on
    assert window.legal_refs == expected_legal_refs
    assert {"aeat-modelo-190-procedure", form_source} <= set(window.source_refs)


def _assert_190_deadline_shift_and_calendar_citation(window, expected_shift: tuple[date, bool, str]) -> None:
    with bundled_indexed_authority().operation() as operation:
        shift = shift_deadline(window.closes_on, modelo="190", operation=operation)
        assert (shift.adjusted_close_date, shift.shifted, shift.shift_reason) == expected_shift
        # The horizon exercise closes in the year after it; the year past that has no
        # published calendar and still refuses rather than guessing.
        unpublished = filing_year_envelope().horizon + 2
        with pytest.raises(
            DeadlineValidationError,
            match=f"holiday calendar publication for {unpublished} could not be resolved",
        ):
            shift_deadline(date(unpublished, 1, 28), modelo="190", operation=operation)
    # A close date that is NOT the statutory month-end has been moved off a
    # non-working day, and the only sanctioned reason to move it is AEAT's own
    # published calendar -- so such a window must cite the calendar it was read
    # from. Pinning the ref tuple instead reddened when the 2026 window was
    # corrected from Saturday 31 January to Monday 2 February.
    moved = window.closes_on.day not in {31, 30, 28, 29}
    cites_calendar = any("calendario-contribuyente" in ref for ref in window.source_refs)
    assert cites_calendar == moved, (
        f"{window.id}: closes_on {window.closes_on} and calendar citation must agree -- "
        f"a moved deadline names the calendar, an unmoved one does not need it"
    )


# Each of the two newest editions' ejercicio takes the form source of the orden that governs it:
# Orden HAC/1432/2024 for the earlier, the consolidated form from the later. Both windows store the
# NOMINAL statutory close, the month-end the plazo names, and never AEAT's published operational date.
# When the month-end falls on a Saturday the operational date is the following Monday, but that is
# derived on read by shift_deadline, not stored. Storing the shifted date would report
# shifted=False / business_day, which says no shift occurred and discards the statutory date; both
# halves are asserted below because the two storage forms are indistinguishable on the
# operator-facing date alone. The later window is also grounded on art. 5, the article that
# establishes the plazo, rather than art. 1, which approves the modelo.
_EDITION_GROUNDING = (
    (("rd-439-2007:art-108", "orden-eha-3127-2009:art-5"), "boe-modelo-190-2024-amendment"),
    (("orden-eha-3127-2009:art-5",), "boe-modelo-190-2025-form"),
)


def _published_shift(closes_on: date) -> tuple[date, bool, str]:
    """Return the working-day shift AEAT's calendar applies to a close that falls on a weekend."""
    weekend = {5: ("sabado", 2), 6: ("domingo", 1)}.get(closes_on.weekday())
    if weekend is None:
        return closes_on, False, "business_day"
    reason, days = weekend
    return closes_on + timedelta(days=days), True, reason


@pytest.mark.parametrize(
    ("ejercicio", "expected_legal_refs", "form_source"),
    [
        (ejercicio, *grounding)
        for ejercicio, grounding in zip(newest_authored_editions("190", 2), _EDITION_GROUNDING, strict=True)
    ],
)
def test_modelo_190_annual_deadline_is_grounded_to_current_revision(
    ejercicio: int,
    expected_legal_refs: tuple[str, ...],
    form_source: str,
) -> None:
    """Each filing year resolves the revision that declares ITS deadline window.

    Written when modelo 190 held both windows in one revision, this asserted a
    construct referencing both and a revision declaring both. The span was later
    split into "2024" and "2025-y-siguientes", which moved each window into the
    revision it governs -- the windows did not change, and neither did their
    dates, but the single-revision expectation could no longer hold.

    Parametrising over the two filing years keeps every window, date and
    grounding reference asserted while letting the registry declare each where
    it belongs. A future split moves a window between revisions without making
    this test wrong.
    """
    window_id = f"modelo-190-{ejercicio}-0a"
    expected = (
        ejercicio,
        str(Period.from_year_and_code(ejercicio, "0A")),
        date(ejercicio + 1, 1, 1),
        date(ejercicio + 1, 1, 31),
    )
    authority = compiled_bundled_authority()
    modelo, catalogues = authority.modelo("190"), authority.catalogues

    snapshot = build_snapshot(
        modelo,
        catalogues,
        source_root=bundled_path(),
        filing_year=ejercicio,
        period="0A",
    )
    revision = snapshot.revision
    windows = {window.id: window for window in revision.deadline_windows}
    _assert_190_deadline_construct_and_sources(revision, catalogues, window_id, form_source)

    # The edition spans every supported year from 2025 onward and declares one
    # window per year, so the requested year's window is asserted rather than
    # the edition holding exactly one.
    assert window_id in windows
    assert len({window.filing_year for window in windows.values()}) == len(windows)
    window = windows[window_id]
    _assert_190_window_dates_and_grounding(window, expected, expected_legal_refs, form_source)
    _assert_190_deadline_shift_and_calendar_citation(window, _published_shift(expected[3]))


def test_modelo_190_filed_declarations_read_allows_live_register_host() -> None:
    authority = compiled_bundled_authority()
    modelo = authority.modelo("190")
    declared = [
        ref
        for revision in modelo.revisions.values()
        for ref in revision.live_cross_references
        if ref.id == "modelo-190-filed-declarations-read"
    ]

    assert declared, "no revision declares the filed-declarations read surface"
    for filed_read in declared:
        assert filed_read.surface == "authenticated_read_surface"
        assert filed_read.requires_authentication is True
        assert filed_read.requires_aeat_authorization is True
        assert filed_read.synthetic_data_allowed is False
        assert _WWW6_HOST in filed_read.allowed_hosts
        assert set(filed_read.allowed_methods) <= {"GET", "HEAD", "OPTIONS"}


_M190_RECORD_TOTAL_BINDINGS = frozenset(
    {
        "modelo-190-perceptor-rows-percepcion-dineraria-total",
        "modelo-190-perceptor-rows-percepcion-especie-total",
        "modelo-190-perceptor-rows-incapacidad-dineraria-total",
        "modelo-190-perceptor-rows-incapacidad-especie-total",
        "modelo-190-perceptor-rows-retencion-practicada-total",
        "modelo-190-perceptor-rows-ingreso-a-cuenta-total",
        "modelo-190-perceptor-rows-incapacidad-retencion-total",
        "modelo-190-perceptor-rows-incapacidad-ingreso-a-cuenta-total",
    }
)


def _supported_years() -> range:
    support = compiled_bundled_authority().catalogues.require_supported_filing_years()
    return range(support.floor, support.horizon + 1)


def test_modelo_190_totals_sum_the_type_2_records_in_every_supported_exercise() -> None:
    """Positions 136-144, 145-160 and 161-175 total the declaration's own type-2 records in every exercise.

    Every record design from the 2020 edition onward, and the 2025 instrucciones
    for casillas 01 to 03, define the three declarante totals over the type-2
    records of the same declaration and none defines them from Modelo 111, so no
    exercise takes a Modelo 111 relation or dependency.
    """
    authority = compiled_bundled_authority()
    record_years: list[int] = []
    for year in _supported_years():
        snapshot = authority.snapshot("190", filing_year=year, period="0A")
        assert not relation_prefill_bindings_for_period(snapshot.revision, period="0A"), year
        assert not snapshot.revision.dependency_classifications, year
        record_years.append(year)
        with bundled_indexed_authority().operation() as operation:
            observations = tuple(
                WithholdingObservation(
                    source_id=f"m190-{year}-{index}",
                    perceptor_tax_id=nif,
                    transaction_date=date(year, 6, 1),
                    clave=resolve_retencion_clave(clave, date(year, 6, 1), modelo="190", authority=operation),
                    percibido_dinerario=Decimal(percibido),
                    retencion_practicada=Decimal(retencion),
                    incapacity_cash_perception=Decimal("0"),
                    incapacity_cash_withholding=Decimal("0"),
                    incapacity_kind_value=Decimal("0"),
                    incapacity_kind_ingreso_a_cuenta=Decimal("0"),
                    incapacity_kind_repercutido=Decimal("0"),
                    foral_retention_estatal=Decimal("0"),
                    foral_retention_navarra=Decimal("0"),
                    foral_retention_araba=Decimal("0"),
                    foral_retention_gipuzkoa=Decimal("0"),
                    foral_retention_bizkaia=Decimal("0"),
                    base_retenciones=Decimal(percibido),
                )
                for index, (nif, clave, percibido, retencion) in enumerate(
                    (
                        ("00001500M", "A", "1000.00", "150.00"),
                        ("00001500M", "G", "2500.50", "375.08"),
                        ("00001501Y", "A", "730.25", "109.54"),
                    )
                )
            )
        binding_values = resolve_withholding_binding_values(snapshot.revision, observations)
        result = calculate_registry_snapshot(
            snapshot,
            inputs=resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values),
            date_context={"filing_period": date(year + 1, 1, 31)},
            binding_values=binding_values,
            relation_values={},
        )

        entries = {entry.target_casilla_id: entry for entry in result.entries}
        assert result.values[_DECL_PERCEPCIONES_TOTAL_CASILLA] == Decimal("4230.75"), year
        assert result.values[_DECL_RETENCIONES_TOTAL_CASILLA] == Decimal("634.62"), year
        for casilla_id in (_DECL_PERCEPCIONES_TOTAL_CASILLA, _DECL_RETENCIONES_TOTAL_CASILLA):
            assert set(entries[casilla_id].operand_refs) <= _M190_RECORD_TOTAL_BINDINGS, (year, casilla_id)
    assert record_years == list(_supported_years())
