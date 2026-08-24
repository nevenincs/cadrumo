"""Tests for the committed Modelo 353 (IVA grupos agregado) registry foundation."""

from __future__ import annotations

from datetime import date

import pytest

from .....core import IvaDeductionFactKind
from .....core.resources import bundled_path
from ....iva import IvaLedgerObservationRole
from .. import (
    ModeloDefinition,
    RegistryCatalogues,
    RegistryValidator,
    build_snapshot,
    bundled_authority,
    previous_filing_source_reference,
    select_revision,
)
from ._ledger_iva_aggregation_support import _deduction_provenance
from ._registry_schema_support import _committed_modelo

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]


def _load_modelo_353() -> tuple[ModeloDefinition, RegistryCatalogues]:
    return _committed_modelo("353")


def test_modelo_353_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_353()
    assert modelo.id == "353"
    assert modelo.revisions, "353 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "353 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_353_metadata_matches_orden_eha_3434_2007() -> None:
    modelo, catalogues = _load_modelo_353()
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "monthly"
    assert "orden-eha-3434-2007:art-2" in modelo.legal_refs
    assert "orden-eha-3434-2007:art-8" in modelo.legal_refs
    assert "aeat-dr-353-2026" in modelo.source_refs
    assert catalogues.sources["aeat-modelo-353-procedure"].evidence_tier == "official_source_guidance"
    assert catalogues.sources["boe-modelo-353-2007-form"].evidence_tier == "layout_authority"


def test_modelo_353_revision_is_monthly_from_2008() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-2025"]
    assert revision.valid_from == date(2008, 1, 1)
    assert len(revision.period_selector.periods) == 12
    assert revision.orden_aplicabilidad == ("orden-eha-3434-2007:art-2",)


def test_modelo_353_january_deadline_uses_official_calendar_shift() -> None:
    modelo, _ = _load_modelo_353()
    # Each window is read from the revision that OWNS it. The former single
    # span was split at ejercicio 2026, so the 2026 January window belongs to
    # `2026-y-siguientes` while the 2025 one belongs to `2008-2025`; taking
    # both from one revision only worked while there was only one.
    windows = {w.id: w for w in modelo.revisions["2008-2025"].deadline_windows}
    later_windows = {w.id: w for w in modelo.revisions["2026-y-siguientes"].deadline_windows}
    jan_2025 = windows["modelo-353-2025-01"]
    assert jan_2025.opens_on == date(2025, 2, 1)
    assert jan_2025.closes_on == date(2025, 2, 28)

    jan_2026 = later_windows["modelo-353-2026-01"]
    assert jan_2026.opens_on == date(2026, 2, 1)
    assert jan_2026.closes_on == date(2026, 3, 2)
    assert jan_2026.payment_cutoff_on == date(2026, 2, 25)
    assert "aeat-modelo-353-procedure" in jan_2026.source_refs
    assert "aeat-calendario-contribuyente-2026-hasta-2-marzo" in jan_2026.source_refs
    assert "aeat-calendario-contribuyente-2026-domiciliacion" in jan_2026.source_refs


def test_modelo_353_other_months_close_at_30_days_following_month() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-2025"]
    windows = {w.id: w for w in revision.deadline_windows}
    jun = windows["modelo-353-2025-06"]
    assert jun.opens_on == date(2025, 7, 1)
    assert jun.closes_on == date(2025, 7, 30)


@pytest.mark.parametrize(
    ("filing_year", "expected"),
    [
        (
            2022,
            {
                "01": (
                    date.fromisoformat("2022-02-01"),
                    date.fromisoformat("2022-02-28"),
                    date.fromisoformat("2022-02-23"),
                ),
                "02": (
                    date.fromisoformat("2022-03-01"),
                    date.fromisoformat("2022-03-30"),
                    date.fromisoformat("2022-03-25"),
                ),
                "03": (
                    date.fromisoformat("2022-04-01"),
                    date.fromisoformat("2022-05-02"),
                    date.fromisoformat("2022-04-27"),
                ),
                "04": (
                    date.fromisoformat("2022-05-01"),
                    date.fromisoformat("2022-05-30"),
                    date.fromisoformat("2022-05-25"),
                ),
                "05": (
                    date.fromisoformat("2022-06-01"),
                    date.fromisoformat("2022-06-30"),
                    date.fromisoformat("2022-06-25"),
                ),
                "06": (
                    date.fromisoformat("2022-07-01"),
                    date.fromisoformat("2022-08-01"),
                    date.fromisoformat("2022-07-27"),
                ),
                "07": (
                    date.fromisoformat("2022-08-01"),
                    date.fromisoformat("2022-08-30"),
                    date.fromisoformat("2022-08-25"),
                ),
                "08": (
                    date.fromisoformat("2022-09-01"),
                    date.fromisoformat("2022-09-30"),
                    date.fromisoformat("2022-09-25"),
                ),
                "09": (
                    date.fromisoformat("2022-10-01"),
                    date.fromisoformat("2022-10-31"),
                    date.fromisoformat("2022-10-26"),
                ),
                "10": (
                    date.fromisoformat("2022-11-01"),
                    date.fromisoformat("2022-11-30"),
                    date.fromisoformat("2022-11-25"),
                ),
                "11": (
                    date.fromisoformat("2022-12-01"),
                    date.fromisoformat("2022-12-30"),
                    date.fromisoformat("2022-12-25"),
                ),
                "12": (
                    date.fromisoformat("2023-01-01"),
                    date.fromisoformat("2023-01-30"),
                    date.fromisoformat("2023-01-25"),
                ),
            },
        ),
        (
            2023,
            {
                "01": (
                    date.fromisoformat("2023-02-01"),
                    date.fromisoformat("2023-02-28"),
                    date.fromisoformat("2023-02-23"),
                ),
                "02": (
                    date.fromisoformat("2023-03-01"),
                    date.fromisoformat("2023-03-30"),
                    date.fromisoformat("2023-03-25"),
                ),
                "03": (
                    date.fromisoformat("2023-04-01"),
                    date.fromisoformat("2023-05-02"),
                    date.fromisoformat("2023-04-25"),
                ),
                "04": (
                    date.fromisoformat("2023-05-01"),
                    date.fromisoformat("2023-05-30"),
                    date.fromisoformat("2023-05-25"),
                ),
                "05": (
                    date.fromisoformat("2023-06-01"),
                    date.fromisoformat("2023-06-30"),
                    date.fromisoformat("2023-06-25"),
                ),
                "06": (
                    date.fromisoformat("2023-07-01"),
                    date.fromisoformat("2023-07-31"),
                    date.fromisoformat("2023-07-26"),
                ),
                "07": (
                    date.fromisoformat("2023-08-01"),
                    date.fromisoformat("2023-08-30"),
                    date.fromisoformat("2023-08-25"),
                ),
                "08": (
                    date.fromisoformat("2023-09-01"),
                    date.fromisoformat("2023-10-02"),
                    date.fromisoformat("2023-09-27"),
                ),
                "09": (
                    date.fromisoformat("2023-10-01"),
                    date.fromisoformat("2023-10-30"),
                    date.fromisoformat("2023-10-25"),
                ),
                "10": (
                    date.fromisoformat("2023-11-01"),
                    date.fromisoformat("2023-11-30"),
                    date.fromisoformat("2023-11-25"),
                ),
                "11": (
                    date.fromisoformat("2023-12-01"),
                    date.fromisoformat("2024-01-02"),
                    date.fromisoformat("2023-12-26"),
                ),
                "12": (
                    date.fromisoformat("2024-01-01"),
                    date.fromisoformat("2024-01-30"),
                    date.fromisoformat("2024-01-25"),
                ),
            },
        ),
        (
            2024,
            {
                "01": (
                    date.fromisoformat("2024-02-01"),
                    date.fromisoformat("2024-02-29"),
                    date.fromisoformat("2024-02-26"),
                ),
                "02": (
                    date.fromisoformat("2024-03-01"),
                    date.fromisoformat("2024-04-01"),
                    date.fromisoformat("2024-03-25"),
                ),
                "03": (
                    date.fromisoformat("2024-04-01"),
                    date.fromisoformat("2024-04-30"),
                    date.fromisoformat("2024-04-25"),
                ),
                "04": (
                    date.fromisoformat("2024-05-01"),
                    date.fromisoformat("2024-05-30"),
                    date.fromisoformat("2024-05-27"),
                ),
                "05": (
                    date.fromisoformat("2024-06-01"),
                    date.fromisoformat("2024-07-01"),
                    date.fromisoformat("2024-06-26"),
                ),
                "06": (
                    date.fromisoformat("2024-07-01"),
                    date.fromisoformat("2024-07-30"),
                    date.fromisoformat("2024-07-25"),
                ),
                "07": (
                    date.fromisoformat("2024-08-01"),
                    date.fromisoformat("2024-08-30"),
                    date.fromisoformat("2024-08-27"),
                ),
                "08": (
                    date.fromisoformat("2024-09-01"),
                    date.fromisoformat("2024-09-30"),
                    date.fromisoformat("2024-09-25"),
                ),
                "09": (
                    date.fromisoformat("2024-10-01"),
                    date.fromisoformat("2024-10-30"),
                    date.fromisoformat("2024-10-25"),
                ),
                "10": (
                    date.fromisoformat("2024-11-01"),
                    date.fromisoformat("2024-12-02"),
                    date.fromisoformat("2024-11-27"),
                ),
                "11": (
                    date.fromisoformat("2024-12-01"),
                    date.fromisoformat("2024-12-30"),
                    date.fromisoformat("2024-12-25"),
                ),
                "12": (
                    date.fromisoformat("2025-01-01"),
                    date.fromisoformat("2025-01-30"),
                    date.fromisoformat("2025-01-27"),
                ),
            },
        ),
    ],
)
def test_modelo_353_historical_deadlines_exactly_match_official_aeat_calendars(
    filing_year: int,
    expected: dict[str, tuple[date, date, date]],
) -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-2025"]
    windows = {
        window.period.registry_token: window
        for window in revision.deadline_windows
        if window.filing_year == filing_year
    }

    assert len(windows) == len(expected) == 12
    assert set(windows) == set(expected) == set(revision.period_selector.periods)
    for period, dates in expected.items():
        window = windows[period]
        assert window.id == f"modelo-353-{filing_year}-{period}"
        assert window.filing_year == window.period.filing_year == filing_year
        assert window.period_kind == "monthly"
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == dates
        physical_year = window.closes_on.year
        assert set(window.source_refs) == {
            "boe-modelo-353-2007-form",
            "aeat-modelo-353-procedure",
            f"aeat-calendario-contribuyente-{physical_year}",
        }


def test_modelo_353_2025_deadlines_exactly_match_the_official_aeat_calendars() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-2025"]
    windows = {window.period.registry_token: window for window in revision.deadline_windows}
    expected = {
        "01": (date(2025, 2, 1), date(2025, 2, 28), date(2025, 2, 25)),
        "02": (date(2025, 3, 1), date(2025, 3, 31), date(2025, 3, 26)),
        "03": (date(2025, 4, 1), date(2025, 4, 30), date(2025, 4, 25)),
        "04": (date(2025, 5, 1), date(2025, 5, 30), date(2025, 5, 27)),
        "05": (date(2025, 6, 1), date(2025, 6, 30), date(2025, 6, 25)),
        "06": (date(2025, 7, 1), date(2025, 7, 30), date(2025, 7, 25)),
        "07": (date(2025, 8, 1), date(2025, 9, 1), date(2025, 8, 27)),
        "08": (date(2025, 9, 1), date(2025, 9, 30), date(2025, 9, 25)),
        "09": (date(2025, 10, 1), date(2025, 10, 30), date(2025, 10, 27)),
        "10": (date(2025, 11, 1), date(2025, 12, 1), date(2025, 11, 26)),
        "11": (date(2025, 12, 1), date(2025, 12, 30), date(2025, 12, 25)),
        "12": (date(2026, 1, 1), date(2026, 1, 30), date(2026, 1, 27)),
    }

    assert len(windows) == len(expected) == 12
    assert set(windows) == set(expected) == set(revision.period_selector.periods)
    for period, dates in expected.items():
        window = windows[period]
        assert window.id == f"modelo-353-2025-{period}"
        assert window.filing_year == window.period.filing_year == 2025
        assert window.period_kind == "monthly"
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == dates
        calendar_source = (
            "aeat-calendario-contribuyente-2026-domiciliacion"
            if period == "12"
            else "aeat-calendario-contribuyente-2025"
        )
        assert set(window.source_refs) == {
            "boe-modelo-353-2007-form",
            "aeat-modelo-353-procedure",
            calendar_source,
        }


def test_modelo_353_2026_deadlines_stop_at_the_officially_published_calendar_horizon() -> None:
    """The 2026 AEAT table publishes 1M--11M; 12M awaits the 2027 calendar."""
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2026-y-siguientes"]
    windows = {window.period.registry_token: window for window in revision.deadline_windows}
    expected = {
        "01": (date(2026, 2, 1), date(2026, 3, 2), date(2026, 2, 25)),
        "02": (date(2026, 3, 1), date(2026, 3, 30), date(2026, 3, 25)),
        "03": (date(2026, 4, 1), date(2026, 4, 30), date(2026, 4, 27)),
        "04": (date(2026, 5, 1), date(2026, 6, 1), date(2026, 5, 27)),
        "05": (date(2026, 6, 1), date(2026, 6, 30), date(2026, 6, 25)),
        "06": (date(2026, 7, 1), date(2026, 7, 30), date(2026, 7, 27)),
        "07": (date(2026, 8, 1), date(2026, 8, 31), date(2026, 8, 26)),
        "08": (date(2026, 9, 1), date(2026, 9, 30), date(2026, 9, 25)),
        "09": (date(2026, 10, 1), date(2026, 10, 30), date(2026, 10, 27)),
        "10": (date(2026, 11, 1), date(2026, 11, 30), date(2026, 11, 25)),
        "11": (date(2026, 12, 1), date(2026, 12, 30), date(2026, 12, 24)),
    }

    assert len(windows) == len(expected) == 11
    assert set(windows) == set(expected)
    assert "12" in revision.period_selector.periods
    assert "12" not in windows
    for period, dates in expected.items():
        window = windows[period]
        assert window.id == f"modelo-353-2026-{period}"
        assert window.filing_year == window.period.filing_year == 2026
        assert window.period_kind == "monthly"
        assert (window.opens_on, window.closes_on, window.payment_cutoff_on) == dates
        assert "aeat-calendario-contribuyente-2026-domiciliacion" in window.source_refs


@pytest.mark.parametrize(
    ("filing_year", "revision_id", "expected_periods"),
    [
        (2022, "2008-2025", tuple(f"{month:02d}" for month in range(1, 13))),
        (2023, "2008-2025", tuple(f"{month:02d}" for month in range(1, 13))),
        (2024, "2008-2025", tuple(f"{month:02d}" for month in range(1, 13))),
        (2025, "2008-2025", tuple(f"{month:02d}" for month in range(1, 13))),
        (2026, "2026-y-siguientes", tuple(f"{month:02d}" for month in range(1, 12))),
    ],
)
def test_modelo_353_authored_deadlines_have_one_canonical_owner_and_projection(
    filing_year: int,
    revision_id: str,
    expected_periods: tuple[str, ...],
) -> None:
    modelo, _ = _load_modelo_353()

    for period in expected_periods:
        selected = select_revision(modelo, filing_year=filing_year, period=period)
        owners = [
            revision.id
            for revision in modelo.revisions.values()
            if any(
                window.filing_year == filing_year and window.period.registry_token == period
                for window in revision.deadline_windows
            )
        ]
        assert selected.id == revision_id
        assert owners == [selected.id]

    projected = bundled_authority().deadline_windows(filing_year, modelos=("353",))
    assert tuple(window.period.registry_token for _, _, window in projected) == expected_periods
    assert {revision.id for _, revision, _ in projected} == {revision_id}


def test_modelo_353_snapshot_builds_per_month() -> None:
    modelo, catalogues = _load_modelo_353()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="06")
    assert snapshot.revision.id == "2008-2025"
    assert snapshot.revision.orden_aplicabilidad == ("orden-eha-3434-2007:art-2",)
    assert "orden-eha-3434-2007:art-2" in snapshot.legal
    assert "aeat-modelo-353-procedure" in snapshot.sources
    assert "boe-modelo-353-2007-form" in snapshot.sources


def test_modelo_353_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-2025"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}
    filed_ref = cross_refs["modelo-353-filed-declarations-read"]
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True


def test_modelo_353_construct_links_workbook_parity() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-2025"]
    construct = next(c for c in revision.constructs if c.id == "modelo-353-iva-grupo-agregado")
    assert "modelo-353-dr-2026" in construct.workbook_parity_refs


def test_modelo_353_declares_iva_aggregation_bindings() -> None:
    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-2025"]
    iva_binding_ids = {binding.id for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert iva_binding_ids == {
        "modelo-353-iva-repercutido-general-cuota",
        "modelo-353-iva-repercutido-reducido-cuota",
        "modelo-353-iva-repercutido-super-reducido-cuota",
        "modelo-353-iva-soportado-interiores-cuota",
        "modelo-353-iva-autorepercutido-intracomunitaria-cuota",
    }


# Both halves of the ejercicio-2026 split declare this classification, and they
# differ only in which diseno they cite. Parametrising covers both and derives
# the design ref, where pinning one revision plus a literal `aeat-dr-353-2026`
# asserted the newer half's ref against whichever revision was named.
@pytest.mark.parametrize(
    ("revision_id", "design_ref"),
    [("2008-2025", "aeat-dr-353-2021-2025"), ("2026-y-siguientes", "aeat-dr-353-2026")],
)
def test_modelo_353_declares_322_group_settlement_treatment(revision_id: str, design_ref: str) -> None:
    modelo, catalogues = _load_modelo_353()
    revision = modelo.revisions[revision_id]
    classifications = {
        classification.source_modelo: classification for classification in revision.dependency_classifications
    }

    classification = classifications["322"]
    assert classification.id == "modelo-353-dep-322"
    assert classification.treatment == "direct_annual_settlement"
    assert classification.target_constructs == ("modelo-353-iva-grupo-agregado",)
    assert set(classification.legal_refs) == {
        "orden-eha-3434-2007:art-2",
        "ley-37-1992:art-163-quinquies",
        "ley-37-1992:art-163-sexies",
        "ley-37-1992:art-163-nonies",
        "ley-37-1992:art-88",
        "ley-37-1992:art-92",
        "rd-1624-1992:art-71",
    }
    assert set(classification.source_refs) == {
        "aeat-modelo-322-procedure",
        design_ref,
        "aeat-modelo-353-procedure",
        "boe-modelo-322-2007-form",
        "boe-modelo-353-2007-form",
    }
    assert set(classification.legal_refs) <= catalogues.legal.keys()
    assert set(classification.source_refs) <= catalogues.sources.keys()

    m322_carry_ids = {
        binding.id
        for binding in revision.bindings
        if binding.source == "previous_filing"
        and previous_filing_source_reference(binding).source_modelo == classification.source_modelo
    }
    assert m322_carry_ids == {
        "modelo-353-prev-322-cuota-devengada-total",
        "modelo-353-prev-322-cuota-deducible-total",
        "modelo-353-prev-322-resultado-regimen-general",
    }


def test_modelo_353_iva_bindings_resolve_against_substrate_observations() -> None:
    from decimal import Decimal

    from ....iva import IvaCategory, IvaFlowDirection, IvaRateKind
    from .. import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_353()
    revision = modelo.revisions["2008-2025"]
    observations = [
        IvaLedgerObservation(
            ledger_id="agg-rep-1",
            transaction_date=date(2025, 6, 1),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("8000"),
            iva_amount=Decimal("1680"),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
        IvaLedgerObservation(
            ledger_id="agg-sop-1",
            transaction_date=date(2025, 6, 5),
            category=IvaCategory.DOMESTIC_GENERAL,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("3000"),
            iva_amount=Decimal("630"),
            deduction_fact_kind=IvaDeductionFactKind.DOMESTIC_CURRENT,
            deduction_provenance=_deduction_provenance(
                IvaDeductionFactKind.DOMESTIC_CURRENT,
                source_locator="invoice:agg-sop-1",
            ),
            observation_role=IvaLedgerObservationRole.SETTLEMENT,
        ),
    ]
    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result["modelo-353-iva-repercutido-general-cuota"] == Decimal("1680")
    assert result["modelo-353-iva-soportado-interiores-cuota"] == Decimal("630")
