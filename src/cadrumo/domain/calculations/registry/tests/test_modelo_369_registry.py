"""Tests for the committed Modelo 369 OSS/IOSS registry foundation."""

from __future__ import annotations

import warnings
from calendar import monthrange
from datetime import date
from functools import lru_cache

import pytest

from .....core.period import Period
from .....core.casilla_id import CasillaId, validated_casilla_id
from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .._validate import RegistryValidator
from ..authority import bundled_authority
from ..bindings import resolve_available_bound_inputs_by_casilla_id
from ..ids import LegalRefId
from ..ledger_bindings import (
    OssIossLedgerObservation,
    resolve_ledger_oss_aggregation_binding_values,
)
from ..record_design import extract_record_design
from ..schema import ModeloDefinition, RegistryCatalogues
from ._registry_schema_support import _committed_modelo, _committed_snapshot

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


_M369_EXTERIOR_DE_SERVICES_CUOTA_CASILLA: CasillaId = validated_casilla_id("iva.exterior.de.services-cuota")
_M369_EXTERIOR_CUOTA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.exterior.cuota-total")
_M369_UNION_DE_SERVICES_CUOTA_CASILLA: CasillaId = validated_casilla_id("iva.union.de.services-cuota")
_M369_UNION_FR_SERVICES_CUOTA_CASILLA: CasillaId = validated_casilla_id("iva.union.fr.services-cuota")
_M369_UNION_DE_GOODS_DISTANCE_CUOTA_CASILLA: CasillaId = validated_casilla_id("iva.union.de.goods-distance-cuota")
_M369_UNION_CUOTA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.union.cuota-total")
_M369_IMPORTACION_DE_LOW_VALUE_CUOTA_CASILLA: CasillaId = validated_casilla_id("iva.importacion.de.low-value-cuota")
_M369_IMPORTACION_CUOTA_TOTAL_CASILLA: CasillaId = validated_casilla_id("iva.importacion.cuota-total")
_M369_EXTERIOR_SCHEME_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-37-1992:art-163-octiesdecies",
    "ley-37-1992:art-163-noniesdecies",
    "ley-37-1992:art-163-vicies",
)
_M369_UNION_SCHEME_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-37-1992:art-163-unvicies",
    "ley-37-1992:art-163-duovicies",
    "ley-37-1992:art-163-tervicies",
    "ley-37-1992:art-163-quatervicies",
)
_M369_IMPORTACION_SCHEME_LEGAL_REFS: tuple[LegalRefId, ...] = (
    "ley-37-1992:art-163-quinvicies",
    "ley-37-1992:art-163-sexvicies",
    "ley-37-1992:art-163-septvicies",
    "ley-37-1992:art-163-octovicies",
)
_M369_SCHEME_LEGAL_REFS_BY_REVISION = {
    "esquema-exterior": _M369_EXTERIOR_SCHEME_LEGAL_REFS,
    "esquema-union": _M369_UNION_SCHEME_LEGAL_REFS,
    "esquema-importacion": _M369_IMPORTACION_SCHEME_LEGAL_REFS,
}
_M369_SCHEME_CASES = (
    ("EXT-1T", "esquema-exterior", _M369_EXTERIOR_SCHEME_LEGAL_REFS),
    ("1T", "esquema-union", _M369_UNION_SCHEME_LEGAL_REFS),
    ("01", "esquema-importacion", _M369_IMPORTACION_SCHEME_LEGAL_REFS),
)
_M369_DEADLINE_WINDOW_CASES = (
    (
        "esquema-exterior",
        "modelo-369-exterior-2025-ext-1t",
        Period.from_year_and_code(2025, "EXT-1T"),
        date(2025, 4, 1),
        date(2025, 4, 30),
    ),
    (
        "esquema-exterior",
        "modelo-369-exterior-2025-ext-4t",
        Period.from_year_and_code(2025, "EXT-4T"),
        date(2026, 1, 1),
        date(2026, 1, 31),
    ),
    (
        "esquema-union",
        "modelo-369-union-2025-1t",
        Period.from_year_and_code(2025, "1T"),
        date(2025, 4, 1),
        date(2025, 4, 30),
    ),
    (
        "esquema-union",
        "modelo-369-union-2025-4t",
        Period.from_year_and_code(2025, "4T"),
        date(2026, 1, 1),
        date(2026, 1, 31),
    ),
    (
        "esquema-importacion",
        "modelo-369-importacion-2025-01",
        Period.from_year_and_code(2025, "01"),
        date(2025, 2, 1),
        date(2025, 2, 28),
    ),
    (
        "esquema-importacion",
        "modelo-369-importacion-2025-12",
        Period.from_year_and_code(2025, "12"),
        date(2026, 1, 1),
        date(2026, 1, 31),
    ),
    (
        "esquema-importacion",
        "modelo-369-importacion-2026-01",
        Period.from_year_and_code(2026, "01"),
        date(2026, 2, 1),
        date(2026, 2, 28),
    ),
)
_M369_RESULT_CASILLA_CASES = (
    (
        "esquema-exterior",
        (_M369_EXTERIOR_DE_SERVICES_CUOTA_CASILLA,),
        _M369_EXTERIOR_CUOTA_TOTAL_CASILLA,
        "modelo-369-exterior-cuota-total",
        "modelo-369-exterior-calculation",
    ),
    (
        "esquema-union",
        (
            _M369_UNION_DE_SERVICES_CUOTA_CASILLA,
            _M369_UNION_FR_SERVICES_CUOTA_CASILLA,
            _M369_UNION_DE_GOODS_DISTANCE_CUOTA_CASILLA,
        ),
        _M369_UNION_CUOTA_TOTAL_CASILLA,
        "modelo-369-union-cuota-total",
        "modelo-369-union-calculation",
    ),
    (
        "esquema-importacion",
        (_M369_IMPORTACION_DE_LOW_VALUE_CUOTA_CASILLA,),
        _M369_IMPORTACION_CUOTA_TOTAL_CASILLA,
        "modelo-369-importacion-cuota-total",
        "modelo-369-importacion-calculation",
    ),
)


_FORBIDDEN_REMOTE_ACTIONS = frozenset(
    [
        "server-side-save",
        "signing",
        "presentation",
        "payment",
        "amendment",
        "cancellation",
        "document-submission",
        "declaration-submission",
    ],
)


@lru_cache
def _load_modelo_369() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("369")


def test_modelo_369_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_369()
    assert modelo.id == "369"
    assert modelo.revisions, "369 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "369 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_369_metadata_matches_hac_610_2021() -> None:
    modelo, _ = _load_modelo_369()

    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "ad_hoc"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-hac-610-2021:art-1" in modelo.legal_refs
    assert "orden-hac-610-2021:art-2" in modelo.legal_refs
    assert "orden-hac-610-2021:art-3" in modelo.legal_refs
    for scheme_refs in _M369_SCHEME_LEGAL_REFS_BY_REVISION.values():
        assert set(scheme_refs).issubset(modelo.legal_refs)
    assert "aeat-dr-369-2021" in modelo.source_refs
    assert "aeat-modelo-369-procedure" in modelo.source_refs


def test_modelo_369_revisions_split_exterior_union_importacion_periods() -> None:
    modelo, _ = _load_modelo_369()

    exterior = modelo.revisions["esquema-exterior"]
    union = modelo.revisions["esquema-union"]
    importacion = modelo.revisions["esquema-importacion"]

    assert exterior.valid_from == date(2021, 7, 1)
    assert exterior.period_selector.year_from == 2021
    assert exterior.period_selector.periods == ("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T")

    assert union.valid_from == date(2021, 7, 1)
    assert union.period_selector.year_from == 2021
    assert union.period_selector.periods == ("1T", "2T", "3T", "4T")

    assert importacion.valid_from == date(2021, 7, 1)
    assert importacion.period_selector.year_from == 2021
    assert importacion.period_selector.periods == (
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "07",
        "08",
        "09",
        "10",
        "11",
        "12",
    )


def test_modelo_369_snapshots_select_scheme_and_carry_authority() -> None:
    _, catalogues = _load_modelo_369()

    for period, revision_id, expected_legal_refs in _M369_SCHEME_CASES:
        snapshot = _committed_snapshot("369", 2025, period)

        assert snapshot.revision.id == revision_id, period
        assert "orden-hac-610-2021:art-1" in snapshot.legal
        assert "orden-hac-610-2021:art-2" in snapshot.legal
        assert "orden-hac-610-2021:art-3" in snapshot.legal
        for legal_ref in expected_legal_refs:
            assert legal_ref in snapshot.legal, revision_id
        assert "aeat-dr-369-2021" in snapshot.sources
        assert "aeat-modelo-369-procedure" in snapshot.sources
        assert "boe-modelo-369-2021-form" in snapshot.sources
        assert catalogues.sources["aeat-modelo-369-procedure"].evidence_tier == "official_source_guidance"
        assert catalogues.sources["boe-modelo-369-2021-form"].evidence_tier == "layout_authority"


def test_modelo_369_filing_schedules_match_scheme_period_selectors() -> None:
    modelo, _ = _load_modelo_369()

    expected = {
        "esquema-exterior": ("quarterly", ("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T")),
        "esquema-union": ("quarterly", ("1T", "2T", "3T", "4T")),
        "esquema-importacion": (
            "monthly",
            ("01", "02", "03", "04", "05", "06", "07", "08", "09", "10", "11", "12"),
        ),
    }

    for revision_id, (period_kind, periods) in expected.items():
        revision = modelo.revisions[revision_id]
        assert len(revision.filing_schedules) == 1
        schedule = revision.filing_schedules[0]
        assert schedule.period_kind == period_kind
        assert schedule.periods == periods
        assert schedule.periods == revision.period_selector.periods
        assert "orden-hac-610-2021:art-2" in schedule.legal_refs
        assert "orden-hac-610-2021:art-3" in schedule.legal_refs


def test_modelo_369_filing_schedule_explains_b2c_scope_not_b2b() -> None:
    """Every Esquema's filing-schedule condition must disambiguate that the OSS/IOSS
    ventanilla unica covers B2C operations to final consumers (destinatarios que no
    tengan la condicion de sujetos pasivos), never B2B operations between taxable
    persons — so an operator does not misuse Modelo 369 for reverse-charge B2B flows.

    Grounded against the modelo official_name ("...que presten servicios a personas que
    no tengan la condicion de sujetos pasivos...") and the OSS regime (LIVA arts.
    163 octiesdecies-octovicies; HAC/610/2021). The note is asserted on the built
    snapshot projection, the surface an operator-facing consumer reads.
    """
    for period, revision_id, _expected_legal_refs in _M369_SCHEME_CASES:
        snapshot = _committed_snapshot("369", 2025, period)

        schedules = tuple(snapshot.filing_schedules.values())
        assert len(schedules) == 1
        conditions = schedules[0].profile_conditions
        assert conditions, f"{revision_id} filing schedule must declare a profile condition"
        explanation = conditions[0].explanation.lower()

        assert "b2c" in explanation
        assert "b2b" in explanation
        # The B2C scope is grounded in the "no sujetos pasivos" / final-consumer wording.
        assert "no tengan la condicion de sujetos pasivos" in explanation
        assert "consumidores finales" in explanation
        # The Union scheme additionally routes B2B intra-community flows to 303/349.
        if revision_id == "esquema-union":
            assert "inversion del sujeto pasivo" in explanation
            assert "303" in explanation
            assert "349" in explanation


def test_modelo_369_deadline_windows_close_last_day_next_natural_month() -> None:
    modelo, _ = _load_modelo_369()
    for revision_id, window_id, period, opens_on, closes_on in _M369_DEADLINE_WINDOW_CASES:
        revision = modelo.revisions[revision_id]
        windows = {w.id: w for w in revision.deadline_windows}

        window = windows[window_id]
        assert window.period == period, window_id
        assert window.opens_on == opens_on, window_id
        assert window.closes_on == closes_on, window_id
        assert "orden-hac-610-2021:art-3" in window.legal_refs


def test_modelo_369_deadline_coordinates_are_complete_exact_and_canonically_owned() -> None:
    """Every supported 2022-2026 OSS/IOSS period has one law-selected row.

    HAC/610/2021 article 3 fixes the window as the natural month following
    the return period.  This assertion covers all three scheme vocabularies,
    every coordinate, both boundary dates, exact provenance, and the public
    authority's canonical owner projection.
    """
    expected_periods = {
        "esquema-exterior": ("EXT-1T", "EXT-2T", "EXT-3T", "EXT-4T"),
        "esquema-union": ("1T", "2T", "3T", "4T"),
        "esquema-importacion": tuple(f"{month:02d}" for month in range(1, 13)),
    }
    authority = bundled_authority()

    for filing_year in range(2022, 2027):
        projected = authority.deadline_windows(filing_year, modelos=("369",))
        assert len(projected) == 20
        projected_by_coordinate = {
            (revision.id, window.period.registry_token): window
            for modelo, revision, window in projected
            if modelo == "369"
        }

        for revision_id, periods in expected_periods.items():
            assert {period for owner, period in projected_by_coordinate if owner == revision_id} == set(periods)
            for period in periods:
                window = projected_by_coordinate[(revision_id, period)]
                if period.endswith("T"):
                    quarter = int(period[-2])
                    filing_month = quarter * 3 + 1
                else:
                    filing_month = int(period) + 1
                filing_calendar_year = filing_year + (filing_month == 13)
                filing_month = 1 if filing_month == 13 else filing_month
                expected_open = date(filing_calendar_year, filing_month, 1)
                expected_close = date(
                    filing_calendar_year,
                    filing_month,
                    monthrange(filing_calendar_year, filing_month)[1],
                )

                assert window.filing_year == window.period.filing_year == filing_year
                assert (window.opens_on, window.closes_on) == (expected_open, expected_close)
                assert set(window.legal_refs) == {"orden-hac-610-2021:art-3"}
                assert set(window.source_refs) == {
                    "boe-modelo-369-2021-form",
                    "aeat-modelo-369-procedure",
                }


def test_modelo_369_deadlines_do_not_shift_weekend_month_ends() -> None:
    """AEAT expressly excludes Modelo 369 from non-working-day extensions."""
    authority = bundled_authority()
    windows = {
        (revision.id, window.period.registry_token): window.closes_on
        for _modelo, revision, window in authority.deadline_windows(2025, modelos=("369",))
    }

    assert windows[("esquema-importacion", "04")] == date(2025, 5, 31)  # Saturday
    assert windows[("esquema-importacion", "07")] == date(2025, 8, 31)  # Sunday

    historical_windows = {
        (revision.id, window.period.registry_token): window.closes_on
        for _modelo, revision, window in authority.deadline_windows(2022, modelos=("369",))
    }
    assert historical_windows[("esquema-importacion", "03")] == date(2022, 4, 30)  # Saturday
    assert historical_windows[("esquema-importacion", "06")] == date(2022, 7, 31)  # Sunday


def test_modelo_369_deadline_materialisation_has_no_unpublished_filing_year() -> None:
    """Materialisation stops at the shared presently supported filing-year edge."""
    modelo, _ = _load_modelo_369()
    assert {
        window.filing_year for revision in modelo.revisions.values() for window in revision.deadline_windows
    } == set(range(2022, 2027))


def test_modelo_369_live_cross_references_are_read_only() -> None:
    modelo, _ = _load_modelo_369()

    for revision in modelo.revisions.values():
        cross_refs = {ref.surface: ref for ref in revision.live_cross_references}

        static_ref = cross_refs["static_official_documentation"]
        assert static_ref.requires_authentication is False
        assert static_ref.synthetic_data_allowed is False
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(static_ref.forbidden_actions)

        filed_ref = cross_refs["authenticated_read_surface"]
        assert filed_ref.requires_authentication is True
        assert filed_ref.requires_aeat_authorization is True
        assert filed_ref.synthetic_data_allowed is False
        assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
        assert set(filed_ref.allowed_hosts) == {
            _WWW1_HOST,
            _WWW6_HOST,
        }
        assert _FORBIDDEN_REMOTE_ACTIONS.issubset(filed_ref.forbidden_actions)


def test_modelo_369_workbook_parity_refs_resolve_to_official_record_design() -> None:
    modelo, catalogues = _load_modelo_369()

    for revision in modelo.revisions.values():
        assert len(revision.workbook_parity_refs) == 1
        ref = revision.workbook_parity_refs[0]
        source = catalogues.sources[ref.workbook_source]

        assert ref.workbook_source == "aeat-dr-369-2021"
        assert ref.formula_coverage == "record_design_layout"
        assert ref.runner_required is False
        assert source.evidence_tier == "layout_authority"
        assert (bundled_path() / source.corpus_path).is_file()


def test_modelo_369_official_record_design_workbook_is_parseable() -> None:
    _, catalogues = _load_modelo_369()
    source = catalogues.sources["aeat-dr-369-2021"]

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        sheets = extract_record_design(bundled_path() / source.corpus_path).accept_partial()
    by_name = {sheet.name: sheet for sheet in sheets}

    assert len(sheets) == 14
    assert sum(len(sheet.fields) for sheet in sheets) == 1515
    assert by_name["T3690 Estruc. gral"].fields[0].offset == 1
    assert by_name["T3690 Estruc. gral"].fields[0].length == 2
    assert by_name["T3690 Estruc. gral"].fields[0].content == 'Constante "<T"'
    assert by_name["T36900 Info Adicional"].total_positions == 110
    assert by_name["T36901 Ext"].total_positions == 1422
    assert by_name["T36904 Un"].fields[4].description == "Régimen"
    assert by_name["T36910 Imp"].fields[4].content == '"IMPO"'


def test_modelo_369_constructs_close_over_revision_members() -> None:
    modelo, _ = _load_modelo_369()

    for revision in modelo.revisions.values():
        assert len(revision.constructs) == 1
        construct = revision.constructs[0]

        assert construct.casilla_ids == tuple(c.id for c in revision.casillas)
        assert construct.workbook_parity_refs == tuple(w.id for w in revision.workbook_parity_refs)
        assert construct.live_cross_references == tuple(r.id for r in revision.live_cross_references)
        assert construct.application_links == tuple(link.id for link in revision.application_links)
        assert construct.deadline_windows == tuple(w.id for w in revision.deadline_windows)
        assert construct.filing_schedules == tuple(s.id for s in revision.filing_schedules)


def test_modelo_369_revision_envelopes_carry_full_liva_scheme_ranges() -> None:
    modelo, _ = _load_modelo_369()

    for revision_id, expected_refs in _M369_SCHEME_LEGAL_REFS_BY_REVISION.items():
        revision = modelo.revisions[revision_id]
        expected = set(expected_refs)
        construct = revision.constructs[0]
        manifest = revision.completeness_manifest
        formula = revision.formulas[0]
        total_casilla = next(casilla for casilla in revision.casillas if casilla.id == formula.target_casilla_id)
        calculation_link = next(link for link in revision.application_links if link.surface == "calculation")

        assert expected.issubset(revision.legal_refs)
        assert expected.issubset(revision.verification_expectations[0].legal_refs)
        assert expected.issubset(construct.legal_refs)
        assert manifest is not None
        assert expected.issubset(manifest.legal_refs)
        assert expected.issubset(total_casilla.legal_refs)
        assert expected.issubset(formula.legal_refs)
        assert expected.issubset(calculation_link.legal_refs)


def test_modelo_369_each_revision_declares_at_least_one_oss_aggregation_binding() -> None:
    """Each Esquema revision must carry at least one ledger_oss_aggregation
    binding so the calculation chain has a substrate-grounded source for
    its destination-MS aggregations."""
    modelo, _ = _load_modelo_369()
    expected_revisions = ("esquema-exterior", "esquema-union", "esquema-importacion")
    checked = 0
    for revision_id in expected_revisions:
        revision = modelo.revisions[revision_id]
        oss_bindings = [binding for binding in revision.bindings if binding.source == "ledger_oss_aggregation"]
        assert len(oss_bindings) >= 1, f"{revision_id} declares no ledger_oss_aggregation bindings"
        checked += 1
    assert checked == len(expected_revisions)


def test_modelo_369_esquema_union_demonstrator_bindings_resolve_end_to_end() -> None:
    """End-to-end smoke test: the runtime resolver returns the expected
    per-binding totals for a small ledger of substrate-classified
    Esquema Unión observations."""
    from decimal import Decimal

    from ....iva.classification import InvoiceKind, TransactionKind
    from ....iva.oss import OssIossRegime
    from ....iva.schema import EUMemberState, IvaRateKind

    modelo, _ = _load_modelo_369()
    revision = modelo.revisions["esquema-union"]

    observations = [
        OssIossLedgerObservation(
            ledger_id="inv-de-services",
            transaction_date=date(2025, 6, 15),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("1000"),
            iva_amount=Decimal("190"),
        ),
        OssIossLedgerObservation(
            ledger_id="inv-fr-services",
            transaction_date=date(2025, 6, 20),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.FR,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("500"),
            iva_amount=Decimal("100"),
        ),
        OssIossLedgerObservation(
            ledger_id="inv-de-goods",
            transaction_date=date(2025, 7, 1),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
            base_amount=Decimal("200"),
            iva_amount=Decimal("38"),
        ),
    ]

    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-369-union-de-services-21pct": Decimal("190"),
        "modelo-369-union-fr-services-21pct": Decimal("100"),
        "modelo-369-union-de-goods-distance-21pct": Decimal("38"),
    }


def test_modelo_369_esquema_importacion_ioss_binding_resolves_low_value_sale() -> None:
    """End-to-end smoke test for the IOSS Importación binding.

    Asserts that the binding resolver populates the expected key and
    that the resolved value equals the sum of iva_amounts from the
    supplied observations — derived programmatically from the test's
    own input data, not hand-computed.
    """
    from decimal import Decimal

    from ....iva.classification import InvoiceKind, TransactionKind
    from ....iva.oss import OssIossRegime
    from ....iva.schema import EUMemberState, IvaRateKind

    modelo, _ = _load_modelo_369()
    revision = modelo.revisions["esquema-importacion"]

    iva_amounts = [Decimal("15.20"), Decimal("22.80")]
    observations = [
        OssIossLedgerObservation(
            ledger_id=f"ioss-de-{idx}",
            transaction_date=date(2025, 6, idx),
            regime=OssIossRegime.IMPORT_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.IOSS_DISTANCE_SALE_LOW_VALUE,
            base_amount=base,
            iva_amount=iva,
        )
        for idx, (base, iva) in enumerate(
            [
                (Decimal("80"), iva_amounts[0]),
                (Decimal("120"), iva_amounts[1]),
            ],
            start=1,
        )
    ]

    result = resolve_ledger_oss_aggregation_binding_values(revision, observations)

    # Assert structural wiring: the expected binding key must be present.
    expected_binding_key = "modelo-369-importacion-de-low-value-21pct"
    assert expected_binding_key in result, f"{expected_binding_key!r} must be resolved by the IOSS binding"

    # The binding aggregates iva_amount via sum — the resolved value must equal
    # the sum of the iva_amounts from the observations provided to the resolver.
    expected_total = sum(iva_amounts, Decimal("0"))
    assert result[expected_binding_key] == expected_total


def test_modelo_369_esquema_union_constructs_link_oss_bindings() -> None:
    """The Esquema Unión construct must include each ledger_oss_aggregation
    binding so downstream consumers see a complete construct envelope."""
    modelo, _ = _load_modelo_369()
    union = modelo.revisions["esquema-union"]
    construct = next(c for c in union.constructs if c.id == "modelo-369-esquema-union")
    assert "modelo-369-union-de-services-21pct" in construct.bindings
    assert "modelo-369-union-fr-services-21pct" in construct.bindings
    assert "modelo-369-union-de-goods-distance-21pct" in construct.bindings


# ---------------------------------------------------------------------------
# Per-Esquema bound + computed result casillas
# ---------------------------------------------------------------------------


def test_modelo_369_per_esquema_result_casillas_present() -> None:
    modelo, _ = _load_modelo_369()
    for revision_id, bound_casilla_ids, total_casilla_id, formula_id, app_link_id in _M369_RESULT_CASILLA_CASES:
        revision = modelo.revisions[revision_id]
        casilla_ids = {c.id for c in revision.casillas}
        formula_ids = {f.id for f in revision.formulas}
        app_link_ids = {link.id for link in revision.application_links}

        for bound_id in bound_casilla_ids:
            assert bound_id in casilla_ids, revision_id
        assert total_casilla_id in casilla_ids, revision_id
        assert formula_id in formula_ids, revision_id
        assert app_link_id in app_link_ids, revision_id


def test_modelo_369_esquema_union_cuota_total_resolves_end_to_end() -> None:
    """Full chain: ledger observations → ledger_oss_aggregation bindings →
    bound casillas → cuota-total formula sum."""
    from decimal import Decimal

    from ....iva.classification import InvoiceKind, TransactionKind
    from ....iva.oss import OssIossRegime
    from ....iva.schema import EUMemberState, IvaRateKind
    from ..formula_runtime import calculate_registry_snapshot

    modelo, _ = _load_modelo_369()
    revision = modelo.revisions["esquema-union"]

    observations = [
        OssIossLedgerObservation(
            ledger_id="inv-de-services",
            transaction_date=date(2025, 6, 15),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("1000"),
            iva_amount=Decimal("190"),
        ),
        OssIossLedgerObservation(
            ledger_id="inv-fr-services",
            transaction_date=date(2025, 6, 20),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.FR,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_SERVICES,
            base_amount=Decimal("500"),
            iva_amount=Decimal("100"),
        ),
        OssIossLedgerObservation(
            ledger_id="inv-de-goods",
            transaction_date=date(2025, 7, 1),
            regime=OssIossRegime.UNION_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.OSS_UNION_GOODS_DISTANCE_SALE,
            base_amount=Decimal("200"),
            iva_amount=Decimal("38"),
        ),
    ]

    binding_values = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    snapshot = _committed_snapshot("369", 2025, "1T")
    casilla_inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=casilla_inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 4, 15)},
    )

    # Identity threading: each bound casilla equals its binding fact value.
    # The cuota-total formula is verified structurally (operands present);
    # the arithmetic itself stays bound to workbook-parity / oracle replays.
    assert result.values[_M369_UNION_DE_SERVICES_CUOTA_CASILLA] == binding_values["modelo-369-union-de-services-21pct"]
    assert result.values[_M369_UNION_FR_SERVICES_CUOTA_CASILLA] == binding_values["modelo-369-union-fr-services-21pct"]
    assert (
        result.values[_M369_UNION_DE_GOODS_DISTANCE_CUOTA_CASILLA]
        == binding_values["modelo-369-union-de-goods-distance-21pct"]
    )
    assert _M369_UNION_CUOTA_TOTAL_CASILLA in result.values
    union_total_entry = next(e for e in result.entries if e.target_casilla_id == _M369_UNION_CUOTA_TOTAL_CASILLA)
    assert set(union_total_entry.operand_refs) == {
        _M369_UNION_DE_SERVICES_CUOTA_CASILLA,
        _M369_UNION_FR_SERVICES_CUOTA_CASILLA,
        _M369_UNION_DE_GOODS_DISTANCE_CUOTA_CASILLA,
    }


def test_modelo_369_esquema_importacion_cuota_total_resolves_end_to_end() -> None:
    from decimal import Decimal

    from ....iva.classification import InvoiceKind, TransactionKind
    from ....iva.oss import OssIossRegime
    from ....iva.schema import EUMemberState, IvaRateKind
    from ..formula_runtime import calculate_registry_snapshot

    modelo, _ = _load_modelo_369()
    revision = modelo.revisions["esquema-importacion"]

    observations = [
        OssIossLedgerObservation(
            ledger_id="ioss-de-1",
            transaction_date=date(2025, 6, 1),
            regime=OssIossRegime.IMPORT_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.IOSS_DISTANCE_SALE_LOW_VALUE,
            base_amount=Decimal("80"),
            iva_amount=Decimal("15.20"),
        ),
        OssIossLedgerObservation(
            ledger_id="ioss-de-2",
            transaction_date=date(2025, 6, 2),
            regime=OssIossRegime.IMPORT_SCHEME,
            destination_member_state=EUMemberState.DE,
            rate_kind=IvaRateKind.GENERAL,
            invoice_direction=InvoiceKind.ISSUED,
            transaction_kind=TransactionKind.IOSS_DISTANCE_SALE_LOW_VALUE,
            base_amount=Decimal("120"),
            iva_amount=Decimal("22.80"),
        ),
    ]

    binding_values = resolve_ledger_oss_aggregation_binding_values(revision, observations)
    snapshot = _committed_snapshot("369", 2025, "01")
    casilla_inputs = resolve_available_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=casilla_inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 2, 15)},
    )

    # The Esquema Importación registers a single destination/rate construct
    # (DE low-value 21%), so the registry cuota-total formula is an `add` over
    # exactly one operand. The two ledger observations above (80 + 120 base,
    # 15.20 + 22.80 IVA) exercise genuine resolver aggregation INTO that single
    # bound casilla, so a broken aggregation surfaces in the bound input.
    expected_cuota = binding_values["modelo-369-importacion-de-low-value-21pct"]
    assert result.values[_M369_IMPORTACION_DE_LOW_VALUE_CUOTA_CASILLA] == expected_cuota
    assert result.values[_M369_IMPORTACION_CUOTA_TOTAL_CASILLA] == expected_cuota

    # Mirror the union companion test: verify the cuota-total formula
    # structurally. Asserting the formula entry's operand_refs defends the
    # wiring — a registry edit that drops or mis-points the operand fails
    # here even though the single-operand arithmetic stays an identity.
    importacion_total_entry = next(
        e for e in result.entries if e.target_casilla_id == _M369_IMPORTACION_CUOTA_TOTAL_CASILLA
    )
    assert importacion_total_entry.op == "add"
    assert set(importacion_total_entry.operand_refs) == {_M369_IMPORTACION_DE_LOW_VALUE_CUOTA_CASILLA}


def test_modelo_369_constructs_link_calculation_application_link() -> None:
    """Each Esquema construct must reference its own calculation app link."""
    modelo, _ = _load_modelo_369()
    expected = {
        "esquema-exterior": "modelo-369-exterior-calculation",
        "esquema-union": "modelo-369-union-calculation",
        "esquema-importacion": "modelo-369-importacion-calculation",
    }
    for revision_id, calc_link_id in expected.items():
        revision = modelo.revisions[revision_id]
        construct = revision.constructs[0]
        assert calc_link_id in construct.application_links
