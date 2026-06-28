"""Tests for the committed Modelo 303 (IVA autoliquidacion) registry foundation."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from functools import lru_cache

import pytest

from .....core.resources import bundled_path
from .....tests.aeat_literal_fixtures import aeat_host
from .....tests.registry_observations import registry_grounded_modelo_observation
from .. import (
    CasillaId,
    ModeloDefinition,
    RegistryCatalogues,
    RegistryValidator,
    build_snapshot,
    load_registry_tree,
    validated_casilla_id,
)

pytestmark = [pytest.mark.unit, pytest.mark.hex_domain]
_WWW1_HOST = aeat_host("www1")
_WWW6_HOST = aeat_host("www6")


def _casilla_id(value: object) -> CasillaId:
    try:
        return validated_casilla_id(value, surface="test casilla id")
    except ValueError as exc:
        raise AssertionError(f"test fixture casilla key {value!r} is not a canonical casilla.id") from exc


_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA: CasillaId = _casilla_id(
    "iva.compensacion-pendiente-periodos-anteriores",
)
_M303_COMPENSACION_APLICADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-aplicada-periodo")
_M303_POSTERIOR_CASILLA: CasillaId = _casilla_id("iva.compensacion-pendiente-periodos-posteriores")
_M303_RESULTADO_CASILLA: CasillaId = _casilla_id("iva.resultado")
_M303_GENERADA_CASILLA: CasillaId = _casilla_id("iva.compensacion-generada-periodo")
_M303_DISPONIBLE_CASILLA: CasillaId = _casilla_id("iva.compensacion-disponible-fin-periodo")
_M303_AUTOCONSUMO_PROMOTOR_BASE_CASILLA: CasillaId = _casilla_id("iva.autoconsumo.promotor.base")
_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA: CasillaId = _casilla_id("iva.autoconsumo.promotor.cuota")
_M303_CUOTA_DEVENGADA_TOTAL_CASILLA: CasillaId = _casilla_id("iva.cuota-devengada-total")
_M303_PRORRATA_PORCENTAJE_CASILLA: CasillaId = _casilla_id("iva.prorrata-porcentaje")


@lru_cache(maxsize=1)
def _load_modelo_303() -> tuple[ModeloDefinition, RegistryCatalogues]:
    modelos, catalogues = load_registry_tree(bundled_path("registry", "aeat"))
    modelo = next(m for m in modelos if m.id == "303")
    return modelo, catalogues


def test_modelo_303_registry_validator_accepts_committed_definition() -> None:
    modelo, catalogues = _load_modelo_303()
    assert modelo.id == "303"
    assert modelo.revisions, "303 must declare at least one revision"
    assert any(rev.casillas for rev in modelo.revisions.values()), "303 must declare casillas"
    RegistryValidator(catalogues, source_root=bundled_path()).validate_modelo(modelo)


def test_modelo_303_metadata_matches_orden_eha_3786_2008() -> None:
    modelo, _ = _load_modelo_303()

    assert modelo.title == "IVA. Autoliquidación (trimestral)"
    assert modelo.tax_domain == "iva"
    assert modelo.cadence == "quarterly"
    assert modelo.jurisdiction == "ES-AEAT"
    assert "orden-eha-3786-2008:art-1" in modelo.legal_refs
    assert "orden-eha-3786-2008:art-7" in modelo.legal_refs
    assert "aeat-dr-303-2025" in modelo.source_refs
    assert "aeat-modelo-303-procedure" in modelo.source_refs


def test_modelo_303_revision_period_selectors_cover_2009_to_present() -> None:
    modelo, _ = _load_modelo_303()

    rev_old = modelo.revisions["2009-y-siguientes"]
    assert rev_old.valid_from == date(2009, 1, 1)
    assert rev_old.period_selector.year_from == 2009
    assert rev_old.period_selector.year_to == 2022
    assert rev_old.period_selector.periods == ("1T", "2T", "3T", "4T")

    rev_new = modelo.revisions["2023-y-siguientes"]
    assert rev_new.valid_from == date(2023, 1, 1)
    assert rev_new.period_selector.year_from == 2023
    assert rev_new.period_selector.year_to is None
    # contract: 2023+ revision accepts both quarterly (standard) and monthly (SII-enrolled)
    assert "1T" in rev_new.period_selector.periods
    assert "4T" in rev_new.period_selector.periods
    assert "01" in rev_new.period_selector.periods
    assert "12" in rev_new.period_selector.periods


def test_modelo_303_snapshot_builds_for_each_quarter() -> None:
    modelo, catalogues = _load_modelo_303()

    for period in ("1T", "2T", "3T", "4T"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period=period,
        )
        assert snapshot.revision.id == "2023-y-siguientes"

    for period in ("1T", "2T", "3T", "4T"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2021,
            period=period,
        )
        assert snapshot.revision.id == "2009-y-siguientes"


def test_modelo_303_snapshot_carries_legal_authority_and_record_design() -> None:
    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    assert "orden-eha-3786-2008:art-1" in snapshot.legal
    assert "orden-eha-3786-2008:art-7" in snapshot.legal
    assert snapshot.legal["orden-eha-3786-2008:art-7"].article == "7"
    assert "aeat-dr-303-2025" in snapshot.sources
    assert "aeat-modelo-303-procedure" in snapshot.sources
    assert "boe-modelo-303-2008-form" in snapshot.sources


def test_modelo_303_quarterly_deadlines_match_orden_eha_3786_2008_art_7() -> None:
    """1T-3T close on day 20; 4T closes on day 30 of January following."""
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2023-y-siguientes"]
    windows = {w.id: w for w in revision.deadline_windows}

    expected = {
        "modelo-303-2025-1t": (date(2025, 4, 1), date(2025, 4, 21)),
        "modelo-303-2025-2t": (date(2025, 7, 1), date(2025, 7, 21)),
        "modelo-303-2025-3t": (date(2025, 10, 1), date(2025, 10, 20)),
        "modelo-303-2025-4t": (date(2026, 1, 1), date(2026, 1, 30)),
        "modelo-303-2026-1t": (date(2026, 4, 1), date(2026, 4, 20)),
        "modelo-303-2026-2t": (date(2026, 7, 1), date(2026, 7, 20)),
        "modelo-303-2026-3t": (date(2026, 10, 1), date(2026, 10, 20)),
        "modelo-303-2026-4t": (date(2027, 1, 1), date(2027, 1, 30)),
    }

    for window_id, (opens, closes) in expected.items():
        assert windows[window_id].opens_on == opens
        assert windows[window_id].closes_on == closes


def test_modelo_303_live_cross_references_forbid_writes() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    cross_refs = {ref.id: ref for ref in revision.live_cross_references}

    static_ref = cross_refs["modelo-303-static-documentation"]
    assert static_ref.surface == "static_official_documentation"
    assert static_ref.requires_authentication is False

    filed_ref = cross_refs["modelo-303-filed-declarations-read"]
    assert filed_ref.surface == "authenticated_read_surface"
    assert filed_ref.requires_authentication is True
    assert filed_ref.requires_aeat_authorization is True
    assert set(filed_ref.allowed_methods) == {"GET", "HEAD", "OPTIONS"}
    assert set(filed_ref.allowed_hosts) == {
        _WWW1_HOST,
        _WWW6_HOST,
    }
    forbidden = set(filed_ref.forbidden_actions)
    assert {
        "presentation",
        "signing",
        "amendment",
        "payment",
        "cancellation",
        "declaration-submission",
        "document-submission",
        "server-side-save",
    }.issubset(forbidden)


def test_modelo_303_construct_links_filing_extractor_verification() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")

    assert "modelo-303-filing" in construct.application_links
    assert "modelo-303-extractor" in construct.application_links
    assert "modelo-303-verification" in construct.application_links
    assert "modelo-303-deadline" in construct.application_links
    assert construct.filing_schedules == ("modelo-303-trimestral",)
    assert "modelo-303-dr-2025" in construct.workbook_parity_refs


def test_modelo_303_declares_iva_repercutido_soportado_autorepercutido_bindings() -> None:
    """Modelo 303 must declare ledger_iva_aggregation bindings for the
    three IVA flow directions so the runtime can resolve cuota
    devengada / cuota deducible / INVERSION_SUJETO_PASIVO cross-modelo."""
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]

    iva_bindings = {binding.id: binding for binding in revision.bindings if binding.source == "ledger_iva_aggregation"}
    assert "modelo-303-iva-repercutido-general-cuota" in iva_bindings
    assert "modelo-303-iva-repercutido-reducido-cuota" in iva_bindings
    assert "modelo-303-iva-repercutido-super-reducido-cuota" in iva_bindings
    assert "modelo-303-iva-soportado-interiores-cuota" in iva_bindings
    assert "modelo-303-iva-autorepercutido-intracomunitaria-cuota" in iva_bindings


def test_modelo_303_iva_bindings_resolve_end_to_end_with_substrate_observations() -> None:
    """End-to-end: a small ledger of substrate-classified observations
    aggregates to the expected per-binding totals via the
    ledger_iva_aggregation runtime resolver."""
    from decimal import Decimal

    from ....iva import (
        IvaCategory,
        IvaFlowDirection,
        IvaRateKind,
    )
    from .. import (
        IvaLedgerObservation,
        resolve_ledger_iva_aggregation_binding_values,
    )

    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]

    observations = [
        IvaLedgerObservation(
            ledger_id="rep-general-1",
            transaction_date=date(2025, 6, 1),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("1000"),
            iva_amount=Decimal("210"),
        ),
        IvaLedgerObservation(
            ledger_id="rep-reducido-1",
            transaction_date=date(2025, 6, 3),
            category=IvaCategory.DOMESTIC_REDUCED_10,
            rate_kind=IvaRateKind.REDUCED,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("200"),
            iva_amount=Decimal("20"),
        ),
        IvaLedgerObservation(
            ledger_id="rep-super-1",
            transaction_date=date(2025, 6, 4),
            category=IvaCategory.DOMESTIC_SUPER_REDUCED_4,
            rate_kind=IvaRateKind.SUPER_REDUCED,
            flow_direction=IvaFlowDirection.REPERCUTIDO,
            base_amount=Decimal("100"),
            iva_amount=Decimal("4"),
        ),
        IvaLedgerObservation(
            ledger_id="sop-interior-1",
            transaction_date=date(2025, 6, 5),
            category=IvaCategory.DOMESTIC_GENERAL_21,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.SOPORTADO,
            base_amount=Decimal("300"),
            iva_amount=Decimal("63"),
        ),
        IvaLedgerObservation(
            ledger_id="auto-ica-1",
            transaction_date=date(2025, 6, 6),
            category=IvaCategory.INTRA_COMMUNITY_ACQUISITION_REVERSE_CHARGE,
            rate_kind=IvaRateKind.GENERAL,
            flow_direction=IvaFlowDirection.INVERSION_SUJETO_PASIVO,
            base_amount=Decimal("400"),
            iva_amount=Decimal("84"),
        ),
    ]

    result = resolve_ledger_iva_aggregation_binding_values(revision, observations)
    assert result == {
        "modelo-303-iva-repercutido-general-base": Decimal("1000"),
        "modelo-303-iva-repercutido-general-cuota": Decimal("210"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("200"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("20"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("100"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("4"),
        "modelo-303-iva-soportado-interiores-base": Decimal("300"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("63"),
        # This fixture has no recargo-charged repercutido rows, so the
        # recargo-equivalencia tier bindings resolve to zero.
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        # The reverse-charge AIC row is not an intra-community supply, and this
        # fixture has no export rows, so casillas 59/60 resolve to zero.
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        # No third-country import rows in this observation set, so the import
        # deducible binding resolves to zero.
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("84"),
        # The AIC official-box parity bindings select the same AIC inversión row
        # as the semantic intracomunitaria binding, so they resolve to the same
        # self-assessed cuota (net-zero across the devengado/deducible pair).
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("84"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("84"),
        # No domestic inversión del sujeto pasivo rows in this observation
        # set, so both interior reverse-charge bindings resolve to zero.
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0"),
    }


def test_modelo_303_construct_includes_iva_bindings() -> None:
    """The Modelo 303 construct must list each ledger_iva_aggregation
    binding so downstream consumers see a complete construct envelope."""
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    construct = next(c for c in revision.constructs if c.id == "modelo-303-iva-autoliquidacion")
    assert "modelo-303-iva-repercutido-general-cuota" in construct.bindings
    assert "modelo-303-iva-repercutido-reducido-cuota" in construct.bindings
    assert "modelo-303-iva-repercutido-super-reducido-cuota" in construct.bindings
    assert "modelo-303-iva-soportado-interiores-cuota" in construct.bindings
    assert "modelo-303-iva-autorepercutido-intracomunitaria-cuota" in construct.bindings


def test_modelo_303_compensation_chain_uses_current_record_design_casillas() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    casillas = {casilla.id: casilla for casilla in revision.casillas}
    relation = next(item for item in revision.relations if item.id == "modelo-303-rel-self-compensacion-anteriores")

    assert casillas[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA].number == "110"
    assert casillas[_M303_COMPENSACION_APLICADA_CASILLA].number == "78"
    assert casillas[_M303_POSTERIOR_CASILLA].number == "87"
    assert casillas[_M303_RESULTADO_CASILLA].number == "69"
    assert relation.target_periods == ("1T", "2T", "3T", "4T")
    assert relation.source_period_offset_from_target == -1
    assert relation.source_periods == ()
    assert relation.target_binding == "modelo-303-compensacion-pendiente-anteriores"


def test_modelo_303_previous_quarter_compensation_binding_resolves_from_source_casilla_id() -> None:
    from .. import (
        materialize_relation_binding_values,
        previous_filing_observation_requirements,
        relation_source_requirements,
        resolve_previous_filing_binding_values,
        resolve_relation_values_from_observations,
    )

    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    observations = (
        registry_grounded_modelo_observation(
            modelo="303",
            filing_year=2025,
            period="1T",
            casilla_values={_M303_DISPONIBLE_CASILLA: Decimal("1200.00")},
        ),
    )

    binding_requirements = previous_filing_observation_requirements(revision, filing_year=2025, period="2T")
    assert [(item.periods, item.source_casilla_ids) for item in binding_requirements] == [
        (("1T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    relation_requirements = relation_source_requirements(revision, filing_year=2025, period="2T")
    assert [(item.periods, item.source_casilla_ids) for item in relation_requirements] == [
        (("1T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    assert resolve_previous_filing_binding_values(
        revision,
        observations,
        filing_year=2025,
        period="2T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}
    assert resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2025,
        period="2T",
    ) == {"modelo-303-rel-self-compensacion-anteriores": Decimal("1200.00")}
    assert materialize_relation_binding_values(
        revision,
        {"modelo-303-rel-self-compensacion-anteriores": Decimal("1200.00")},
        period="2T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00")}


def test_modelo_303_first_quarter_compensation_resolves_from_previous_year_fourth_quarter() -> None:
    from .. import (
        materialize_relation_binding_values,
        previous_filing_observation_requirements,
        relation_source_requirements,
        resolve_previous_filing_binding_values,
        resolve_relation_values_from_observations,
    )

    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    observations = (
        registry_grounded_modelo_observation(
            modelo="303",
            filing_year=2025,
            period="4T",
            casilla_values={_M303_DISPONIBLE_CASILLA: Decimal("450.00")},
        ),
    )

    binding_requirements = previous_filing_observation_requirements(revision, filing_year=2026, period="1T")
    assert [(item.filing_year, item.periods, item.source_casilla_ids) for item in binding_requirements] == [
        (2025, ("4T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    relation_requirements = relation_source_requirements(revision, filing_year=2026, period="1T")
    assert [(item.filing_year, item.periods, item.source_casilla_ids) for item in relation_requirements] == [
        (2025, ("4T",), (_M303_DISPONIBLE_CASILLA,)),
    ]

    assert resolve_previous_filing_binding_values(
        revision,
        observations,
        filing_year=2026,
        period="1T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}
    assert resolve_relation_values_from_observations(
        revision,
        observations,
        filing_year=2026,
        period="1T",
    ) == {"modelo-303-rel-self-compensacion-anteriores": Decimal("450.00")}
    assert materialize_relation_binding_values(
        revision,
        {"modelo-303-rel-self-compensacion-anteriores": Decimal("450.00")},
        period="1T",
    ) == {"modelo-303-compensacion-pendiente-anteriores": Decimal("450.00")}


def test_modelo_303_compensation_calculation_applies_available_balance_and_carries_remainder() -> None:
    from .. import calculate_registry_snapshot, resolve_bound_inputs_by_casilla_id

    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="2T")

    binding_values = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("1000.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("1200.00"),
        # No autoconsumo promotor in this period; zero disables the formula path.
        "modelo-303-autoconsumo-promotor-base": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }
    bound_inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=bound_inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 6, 30)},
    )

    # Structural wiring: all compensation casillas must be present in the result.
    compensation_casillas = {
        _M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA,
        _M303_COMPENSACION_APLICADA_CASILLA,
        _M303_POSTERIOR_CASILLA,
        _M303_RESULTADO_CASILLA,
        _M303_GENERADA_CASILLA,
        _M303_DISPONIBLE_CASILLA,
    }
    for casilla_id in compensation_casillas:
        assert casilla_id in result.values, f"{casilla_id!r} must be computed by the compensation chain"

    # Compensation balance constraint: applied + remainder must equal the incoming balance.
    # This is a structural invariant of the compensation mechanism, not a hand-computed value.
    pendiente_anteriores = result.values[_M303_COMPENSACION_PENDIENTE_ANTERIORES_CASILLA]
    aplicada = result.values[_M303_COMPENSACION_APLICADA_CASILLA]
    pendiente_posteriores = result.values[_M303_POSTERIOR_CASILLA]
    assert aplicada + pendiente_posteriores == pendiente_anteriores, "applied + remainder must equal incoming balance"

    # When compensation exceeds IVA output, resultado must be zero (no tax due).
    # The binding carries compensacion_pendiente_anteriores=1200 > repercutido=1000,
    # so the full repercutido is absorbed and resultado must be 0.
    assert result.values[_M303_RESULTADO_CASILLA] == Decimal("0.00"), (
        "resultado must be zero when compensation balance exceeds IVA output"
    )

    # Applied amount must not exceed the IVA output for this period.
    assert aplicada <= binding_values["modelo-303-iva-repercutido-general-cuota"]

    # Disponible at end of period equals the remainder carried forward.
    assert result.values[_M303_DISPONIBLE_CASILLA] == pendiente_posteriores


def test_modelo_303_sii_monthly_snapshot_resolves_for_each_period() -> None:
    """contract regression: SII-enrolled taxpayers file M303 monthly (Art. 62.6
    RD 1624/1992). The 2023-y-siguientes revision must accept periods 01-12
    via select_revision so ``bindings list --period 01`` resolves without a
    RegistrySnapshotError."""
    modelo, catalogues = _load_modelo_303()

    for period in ("01", "06", "12"):
        snapshot = build_snapshot(
            modelo,
            catalogues,
            source_root=bundled_path(),
            filing_year=2025,
            period=period,
        )
        assert snapshot.revision.id == "2023-y-siguientes"
        schedule_ids = {s.id for s in snapshot.revision.filing_schedules}
        assert "modelo-303-mensual-sii" in schedule_ids, f"monthly SII schedule absent for period {period}"


def test_modelo_303_sii_monthly_filing_schedule_matches_sii_enrolled_profiles() -> None:
    """The monthly schedule must fire for SII-enrolled profiles and be excluded
    for standard quarterly profiles."""
    from ....deadlines._models import IVARegime, ModeloIVAProfile, TaxpayerProfile
    from .. import applicable_filing_schedules

    modelo, _catalogues = _load_modelo_303()
    revision = modelo.revisions["2023-y-siguientes"]

    sii_profile = TaxpayerProfile(
        tax_id="A12345678",
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(sii_enrolled=True),
    )
    quarterly_profile = TaxpayerProfile(
        tax_id="B98765432",
        iva_regime=IVARegime.GENERAL,
        iva=ModeloIVAProfile(sii_enrolled=False),
    )

    sii_schedules = applicable_filing_schedules(revision, sii_profile)
    sii_ids = {s.id for s in sii_schedules}
    assert "modelo-303-mensual-sii" in sii_ids, "monthly SII schedule must match SII-enrolled profile"
    assert "modelo-303-trimestral" not in sii_ids, "quarterly schedule must NOT match SII-enrolled profile"

    quarterly_schedules = applicable_filing_schedules(revision, quarterly_profile)
    quarterly_ids = {s.id for s in quarterly_schedules}
    assert "modelo-303-trimestral" in quarterly_ids, "quarterly schedule must match standard quarterly profile"
    assert "modelo-303-mensual-sii" not in quarterly_ids, (
        "monthly SII schedule must NOT match standard quarterly profile"
    )


def test_modelo_303_autoconsumo_promotor_art9_oracle_1400k_base_yields_294k_cuota() -> None:
    """Oracle: Ramón has construction cost €1,400,000 and converts the building
    to his rental estate.  Art. 9.1.c LISIVA triggers the autoconsumo; Art. 79.4
    LISIVA sets the base at cost; Art. 90 LISIVA sets the tipo at 21%.

    Expected cuota = 1,400,000 x 0.21 = 294,000.00.

    The expected value is derived from the statutory formula (Art. 90 LISIVA:
    tipo general = 21%), NOT from the registry implementation under test; this
    test would fail if the formula were mis-wired or the tipo were wrong.
    """
    from .. import calculate_registry_snapshot, resolve_bound_inputs_by_casilla_id

    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    binding_values = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-autoconsumo-promotor-base": Decimal("1400000"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }
    bound_inputs = resolve_bound_inputs_by_casilla_id(snapshot.revision, binding_values)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=bound_inputs,
        binding_values=binding_values,
        date_context={"filing_period": date(2025, 3, 31)},
    )

    # Art. 90 LISIVA tipo general 21%: 1,400,000 x 0.21 = 294,000.00
    assert result.values[_M303_AUTOCONSUMO_PROMOTOR_BASE_CASILLA] == Decimal("1400000"), (
        "base casilla must carry the supplied construction cost"
    )
    assert result.values[_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA] == Decimal("294000.00"), (
        "cuota must equal 1,400,000 x 21% = 294,000.00 per Art. 90 LISIVA"
    )
    # The autoconsumo cuota must also flow into the total devengada.
    cuota_devengada_total = result.values[_M303_CUOTA_DEVENGADA_TOTAL_CASILLA]
    assert cuota_devengada_total == Decimal("294000.00"), (
        "cuota-devengada-total must include the autoconsumo promotor cuota"
    )


def test_modelo_303_autoconsumo_promotor_cuota_proportional_to_base() -> None:
    """Anti-tautology: halving the construction base must halve the cuota.

    The assertion is derived from the statutory multiplication (Art. 90 LISIVA
    tipo 21%), not from a second call to the same formula.  If the formula
    constant were changed to, say, 0.10, this test would catch it immediately.
    """
    from .. import calculate_registry_snapshot, resolve_bound_inputs_by_casilla_id

    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")

    zero_bindings: dict[str, Decimal] = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
    }

    def _run(base: Decimal) -> Decimal:
        bv = {**zero_bindings, "modelo-303-autoconsumo-promotor-base": base}
        bound = resolve_bound_inputs_by_casilla_id(snapshot.revision, bv)
        r = calculate_registry_snapshot(
            snapshot,
            inputs=bound,
            binding_values=bv,
            date_context={"filing_period": date(2025, 3, 31)},
        )
        return r.values[_M303_AUTOCONSUMO_PROMOTOR_CUOTA_CASILLA]

    # Statutory expectation from Art. 90 LISIVA (tipo general 21%):
    #   700,000 x 0.21 = 147,000.00
    assert _run(Decimal("700000")) == Decimal("147000.00")
    # Cross-check: result at 1,400,000 is exactly double — if the registry formula
    # were wrong the ratio would differ.
    assert _run(Decimal("1400000")) == Decimal("2") * _run(Decimal("700000"))


def test_modelo_303_workbook_parity_ref_anchors_record_design_layout() -> None:
    modelo, _ = _load_modelo_303()
    revision = modelo.revisions["2009-y-siguientes"]
    parity = next(p for p in revision.workbook_parity_refs if p.id == "modelo-303-dr-2025")

    assert parity.workbook_source == "aeat-dr-303-2025"
    assert parity.formula_coverage == "record_design_layout"
    assert parity.fixture_id == "modelo-303-2025-record-design-layout"


def test_modelo_303_prorrata_defaults_to_100_when_no_volume_data() -> None:
    """Regression for defect C2: prorrata-porcentaje defaults to 100, never 0.

    A fully-taxable trader who declares no prorrata-volume data (volumen-total = 0)
    has no exempt-without-right operation limiting deduction, so the LIVA art. 94
    full right to deduct applies and the percentage is 100. The previous else-0
    default zeroed every deduction and blocked the filing. The expected value is
    derived from the regulated full-deduction default, not from re-running the
    formula under test.
    """
    from .. import calculate_registry_snapshot, resolve_bound_inputs_by_casilla_id

    modelo, catalogues = _load_modelo_303()
    snapshot = build_snapshot(modelo, catalogues, source_root=bundled_path(), filing_year=2025, period="1T")
    zero_bindings: dict[str, Decimal] = {
        "modelo-303-iva-repercutido-general-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-repercutido-super-reducido-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-interiores-cuota": Decimal("0.00"),
        "modelo-303-iva-soportado-importaciones-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-intracomunitaria-deducible-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-devengado-cuota": Decimal("0.00"),
        "modelo-303-iva-autorepercutido-interior-deducible-cuota": Decimal("0.00"),
        "modelo-303-casilla-59-entregas-intracomunitarias-base": Decimal("0"),
        "modelo-303-casilla-60-exportaciones-base": Decimal("0"),
        "modelo-303-iva-repercutido-general-base": Decimal("0"),
        "modelo-303-iva-repercutido-reducido-base": Decimal("0"),
        "modelo-303-iva-repercutido-super-reducido-base": Decimal("0"),
        "modelo-303-iva-soportado-interiores-base": Decimal("0"),
        "modelo-303-recargo-equivalencia-general-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-reducido-cuota": Decimal("0"),
        "modelo-303-recargo-equivalencia-super-reducido-cuota": Decimal("0"),
        "modelo-303-compensacion-pendiente-anteriores": Decimal("0.00"),
        "modelo-303-profile-state-attribution-ratio": Decimal("100"),
        "modelo-303-autoconsumo-promotor-base": Decimal("0"),
    }
    bound = resolve_bound_inputs_by_casilla_id(snapshot.revision, zero_bindings)
    result = calculate_registry_snapshot(
        snapshot,
        inputs=bound,
        binding_values=zero_bindings,
        date_context={"filing_period": date(2025, 3, 31)},
    )
    assert result.values[_M303_PRORRATA_PORCENTAJE_CASILLA] == Decimal("100")
